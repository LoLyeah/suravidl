package com.suravidl.app

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

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

    private fun bySuffix(items: List<Sniffed>, suffix: String) =
        items.firstOrNull { it.url.endsWith(suffix) }

    private fun dump(items: List<Sniffed>): String =
        items.joinToString(" | ") { "${it.via}:${it.url}@${it.frame}" }
}
