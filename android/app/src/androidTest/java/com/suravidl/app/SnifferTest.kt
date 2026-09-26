package com.suravidl.app

import android.content.Intent
import android.view.View
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * The sniffer's real path: a real WebView loading a real page over real HTTP.
 *
 * The fixture server (`FixtureServer`, loopback, in this process) means the test
 * needs nothing but the emulator itself — no host server, no network. What it
 * pins is the reason the four capture layers exist: a plain `<video src>`, a
 * file fetched by script, and a stream fed by JavaScript (which the network
 * layer can never see), each attributed to the frame it lived in.
 *
 * Launches the activity fire-and-forget, like the other tests here: what
 * matters is the capture, not the activity's lifecycle state.
 *
 * The download path is covered from here too: this class proves a found row
 * carries a Download button for its URL, and `HandoffTest` proves a handoff
 * with the browser's own cookies + referer satisfies a guarded server. What
 * is *not* covered end-to-end is the click itself (the button's own
 * listener) — a downloaded job through the tap needs the engine running in
 * the same process, which the queue tests already exercise directly.
 */
@RunWith(AndroidJUnit4::class)
class SnifferTest {

    @Test(timeout = 240_000)
    fun theBrowserCapturesScriptedAndPlainMediaAndNamesTheFrame() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val server = FixtureServer().start()
        SniffLog.clear()
        try {
            ctx.startActivity(Intent(ctx, BrowserActivity::class.java)
                .putExtra(BrowserActivity.EXTRA_URL, server.url("/page.html"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))

            val deadline = System.currentTimeMillis() + 120_000
            while (System.currentTimeMillis() < deadline) {
                val seen = SniffLog.snapshot()
                if (bySuffix(seen, "/fixture.m3u8") != null &&
                    bySuffix(seen, "/bare.mp4") != null &&
                    bySuffix(seen, "/inner.mp4") != null &&
                    seen.any { it.via == "mse" }) break
                Thread.sleep(1000)
            }

            val items = SniffLog.snapshot()
            val manifest = bySuffix(items, "/fixture.m3u8")
            assertNotNull("the manifest the page fetched by script was missed: " + dump(items),
                          manifest)
            assertEquals("the fetch hook never fired — only the network layer saw it: " +
                         dump(items), "fetch", manifest!!.via)
            assertNotNull("the video element in the page was missed: " + dump(items),
                          bySuffix(items, "/bare.mp4"))
            val inner = bySuffix(items, "/inner.mp4")
            assertNotNull("the video inside the child frame was missed: " + dump(items), inner)
            assertTrue("the child frame's stream was not attributed to its frame: " + dump(items),
                       inner!!.frame.contains("/inner.html"))
            assertTrue("a JavaScript-fed (MSE) stream was not seen — script layers exist " +
                       "precisely for that: " + dump(items), items.any { it.via == "mse" })
            assertTrue("HTML leaked into the candidate list: " + dump(items),
                       items.none { it.url.endsWith(".html") })
        } finally {
            server.stop()
        }
    }

    @Test(timeout = 60_000)
    fun theLogKeepsCandidatesDropsJunkAndRemembersTheBestSighting() {
        SniffLog.clear()
        val manifest = "https://cdn.example/hls/master.m3u8"
        assertTrue(SniffLog.add(manifest, "request", "", false))
        // same URL, weaker mechanism: no new row …
        assertTrue(!SniffLog.add(manifest, "load", "", false))
        // … and a stronger sighting upgrades it, frame included
        assertTrue(SniffLog.add(manifest, "player", "https://cdn.example/player.html", true))
        val one = SniffLog.snapshot().first { it.url == manifest }
        assertEquals("player", one.via)
        assertEquals("https://cdn.example/player.html", one.frame)

        for (bad in listOf("javascript:alert(1)", "data:text/html,x", "file:///etc/passwd",
                           "intent://x", "chrome://settings", "")) {
            assertTrue("junk got in: $bad", !SniffLog.add(bad, "hook", "", false))
        }
        assertTrue("an absurdly long URL got in",
                   !SniffLog.add("https://cdn.example/" + "a".repeat(5000), "hook", "", false))

        // the prefilter: media looks like media, an HTML page does not
        assertTrue(SniffPatterns.matches("https://cdn.example/hls/master.m3u8?token=1"))
        assertTrue(SniffPatterns.matches("https://cdn.example/videoplayback?id=9"))
        assertTrue(!SniffPatterns.matches("https://cdn.example/page.html"))

        SniffLog.clear()
        repeat(SniffLog.MAX + 5) {
            SniffLog.add("https://cdn.example/f$it.mp4", "request", "", false)
        }
        assertEquals("the list must stay bounded", SniffLog.MAX, SniffLog.snapshot().size)
        SniffLog.clear()
    }

    @Test(timeout = 60_000)
    fun theLogSurvivesThreadsAddingAtOnce() {
        SniffLog.clear()
        val same = "https://cdn.example/clip.mp4"
        val pool = Executors.newFixedThreadPool(8)
        try {
            val jobs = (0 until 8).map { i ->
                pool.submit {
                    repeat(40) { n ->
                        SniffLog.add(same, "request", "https://page.example/$i", false)
                        SniffLog.add("https://cdn.example/seg-$i-$n.ts", "request", "", false)
                    }
                }
            }
            jobs.forEach { it.get(30, TimeUnit.SECONDS) }
        } finally {
            pool.shutdown()
        }
        val items = SniffLog.snapshot()
        // add() is called from the WebView handler thread, the JS bridge and the
        // UI thread at once; without one critical section the same URL lands
        // twice and the bounded list can overshoot. Both were audit findings.
        assertEquals("one URL, one row: " + items.count { it.url == same }, 1,
                     items.count { it.url == same })
        assertEquals("the list must stay bounded under concurrency: " + items.size,
                     SniffLog.MAX, items.size)
        SniffLog.clear()
    }

    @Test(timeout = 150_000)
    fun theFoundRowCarriesADownloadButtonForItsUrl() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val server = FixtureServer().start()
        SniffLog.clear()
        try {
            ctx.startActivity(Intent(ctx, BrowserActivity::class.java)
                .putExtra(BrowserActivity.EXTRA_URL, server.url("/page.html"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))

            // The static tests prove the chip *code* exists; this proves the row
            // for a find actually carries one, tagged with that find's URL —
            // which is the half a mutation can delete without anyone noticing.
            var tagged: String? = null
            val deadline = System.currentTimeMillis() + 120_000
            while (System.currentTimeMillis() < deadline && tagged == null) {
                val found = SniffLog.snapshot().firstOrNull { it.url.endsWith("/fixture.m3u8") }
                if (found != null && viewWithTag("download:" + found.url) != null) {
                    tagged = found.url
                } else {
                    Thread.sleep(1000)
                }
            }
            assertNotNull("no live row offered a Download button for the find: " +
                          dump(SniffLog.snapshot()), tagged)
        } finally {
            server.stop()
        }
    }

    @Test(timeout = 180_000)
    fun thePlayersOwnSourceIsAFindEvenWithoutAMediaExtension() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val server = FixtureServer().start()
        SniffLog.clear()
        try {
            ctx.startActivity(Intent(ctx, BrowserActivity::class.java)
                .putExtra(BrowserActivity.EXTRA_URL, server.url("/noext.html"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))

            var found: Sniffed? = null
            val deadline = System.currentTimeMillis() + 120_000
            while (System.currentTimeMillis() < deadline) {
                found = SniffLog.snapshot().firstOrNull { it.url.endsWith("/media/plainid1234") }
                if (found != null) break
                Thread.sleep(1000)
            }
            assertNotNull("an extension-less stream the player itself points at was missed " +
                          "— the real site served /1Vvp1Q5ixT-GxZcW4IToe with no extension " +
                          "at all: " + dump(SniffLog.snapshot()), found)
            assertEquals("the player's own source is a 'player' find", "player", found!!.via)
            assertTrue("the frame the stream lives in must be recorded — it becomes the " +
                       "referer: " + found!!.frame, found!!.frame.contains("/noext-inner.html"))
        } finally {
            server.stop()
        }
    }

    @Test(timeout = 240_000)
    fun aSecondLinkReachesTheBrowserThatIsAlreadyOpen() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val server = FixtureServer().start()
        SniffLog.clear()
        try {
            wakeScreen()
            ctx.startActivity(Intent(ctx, BrowserActivity::class.java)
                .putExtra(BrowserActivity.EXTRA_URL, server.url("/page.html"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            var deadline = System.currentTimeMillis() + 90_000
            while (System.currentTimeMillis() < deadline &&
                   SniffLog.snapshot().none { it.url.endsWith("/bare.mp4") }) {
                Thread.sleep(1000)
            }
            assertTrue("the first page never loaded: " + dump(SniffLog.snapshot()),
                       SniffLog.snapshot().any { it.url.endsWith("/bare.mp4") })

            // Exactly what "Open in the browser ↗" does for a second link — the
            // activity is singleTask, so this arrives as onNewIntent. The flags
            // are mirrored from MainActivity.openBrowser on purpose: an
            // identical launch without CLEAR_TOP is a no-op on API 30.
            wakeScreen()
            ctx.startActivity(Intent(ctx, BrowserActivity::class.java)
                .putExtra(BrowserActivity.EXTRA_URL, server.url("/second.html"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or
                          Intent.FLAG_ACTIVITY_CLEAR_TOP or
                          Intent.FLAG_ACTIVITY_SINGLE_TOP))

            deadline = System.currentTimeMillis() + 120_000
            while (System.currentTimeMillis() < deadline &&
                   SniffLog.snapshot().none { it.url.endsWith("/second.mp4") }) {
                Thread.sleep(1000)
            }
            assertTrue("a second link never reached the browser that was already open — " +
                       "singleTask without onNewIntent drops it silently, so the user keeps " +
                       "scanning the previous page. Browser: " + browserState() + " | finds: " +
                       dump(SniffLog.snapshot()),
                       SniffLog.snapshot().any { it.url.endsWith("/second.mp4") })
        } finally {
            server.stop()
        }
    }

    /**
     * A stopped activity is only handed a new intent when it comes back to the
     * foreground, and an emulator with its screen off resumes nothing: this test
     * failed on API 30 while the 16 KB API 36 image passed, and the difference
     * was the screen, not the fix. A user looking at the phone is awake.
     */
    private fun wakeScreen() {
        val inst = InstrumentationRegistry.getInstrumentation()
        for (cmd in listOf("input keyevent KEYCODE_WAKEUP", "wm dismiss-keyguard")) {
            try {
                inst.uiAutomation.executeShellCommand(cmd).close()
            } catch (_: Throwable) {
            }
        }
    }

    /** lifecycle stage + the page the live browser is showing — without this a
     *  failure says only "nothing arrived", not whether it was delivered. */
    private fun browserState(): String {
        val inst = InstrumentationRegistry.getInstrumentation()
        var out = "no BrowserActivity"
        inst.runOnMainSync {
            for (stage in listOf(Stage.RESUMED, Stage.STARTED, Stage.PAUSED)) {
                val acts = ActivityLifecycleMonitorRegistry.getInstance()
                    .getActivitiesInStage(stage).filterIsInstance<BrowserActivity>()
                if (acts.isNotEmpty()) {
                    out = "$stage url=" + (findWebView(acts.first().window.decorView)?.url
                                           ?: "(no webview)")
                    break
                }
            }
        }
        return out
    }

    private fun findWebView(v: View): android.webkit.WebView? {
        if (v is android.webkit.WebView) return v
        if (v is android.view.ViewGroup) {
            for (i in 0 until v.childCount) {
                findWebView(v.getChildAt(i))?.let { return it }
            }
        }
        return null
    }

    /** Looks the tag up in the running BrowserActivity's view tree, on main. */
    private fun viewWithTag(tag: String): View? {
        val inst = InstrumentationRegistry.getInstrumentation()
        var found: View? = null
        inst.runOnMainSync {
            ActivityLifecycleMonitorRegistry.getInstance()
                .getActivitiesInStage(Stage.RESUMED)
                .filterIsInstance<BrowserActivity>()
                .forEach { act -> found = act.window.decorView.findViewWithTag(tag) }
        }
        return found
    }

    private fun bySuffix(items: List<Sniffed>, suffix: String) =
        items.firstOrNull { it.url.endsWith(suffix) }

    private fun dump(items: List<Sniffed>): String =
        items.joinToString(" | ") { "${it.via}:${it.url}@${it.frame}" }
}
