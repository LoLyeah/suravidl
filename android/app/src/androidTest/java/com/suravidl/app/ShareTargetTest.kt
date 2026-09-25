package com.suravidl.app

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Share target: "Share → suravidl" hands a link from another app to the
 * download box.
 *
 * The extractor is pure, so every shape the share sheet produces is hammered
 * here without a UI. The delivery path is then exercised for real by launching
 * the activity with ACTION_SEND and reading the line it writes — intent →
 * activity → page → JS — the same way AppStartupTest proves the engine boots.
 */
@RunWith(AndroidJUnit4::class)
class ShareTargetTest {

    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext

    @Test(timeout = 30_000)
    fun aLinkIsFoundInWhateverTheShareSheetSends() {
        // the plain cases: app-shared links arrive with and without a scheme
        assertEquals("https://youtu.be/xyz", MainActivity.firstUrlIn("https://youtu.be/xyz"))
        assertEquals("https://youtu.be/xyz",
            MainActivity.firstUrlIn("Look at this: https://youtu.be/xyz"))
        assertEquals("https://www.youtube.com/watch?v=abc123&t=30",
            MainActivity.firstUrlIn(
                "\u201cGreat set\u201d — https://www.youtube.com/watch?v=abc123&t=30"))
        // plenty of apps share the link without a scheme at all
        assertEquals("https://youtu.be/xyz", MainActivity.firstUrlIn("youtu.be/xyz"))
        assertEquals("https://www.example.com/watch?v=1",
            MainActivity.firstUrlIn("www.example.com/watch?v=1"))
        // trailing punctuation is the sentence's, not the URL's
        assertEquals("https://example.com/a.mp4",
            MainActivity.firstUrlIn("see https://example.com/a.mp4, nice!"))
        assertEquals("https://example.com/a",
            MainActivity.firstUrlIn("\"https://example.com/a\""))
        assertEquals("https://example.com/a",
            MainActivity.firstUrlIn("(https://example.com/a)"))

        assertEquals("https://bit.ly/3xYz", MainActivity.firstUrlIn("bit.ly/3xYz"))
        assertEquals("https://example.co.uk/a?b=1",
            MainActivity.firstUrlIn("Check example.co.uk/a?b=1 out"))

        // nothing to download: prose, an address, a file name, an empty share
        assertNull(MainActivity.firstUrlIn("just a sentence, no link here"))
        assertNull(MainActivity.firstUrlIn("mail me at handi@example.com"))
        assertNull(MainActivity.firstUrlIn("the file clip.mp4 is big"))
        assertNull(MainActivity.firstUrlIn("v1.2 is out"))
        assertNull(MainActivity.firstUrlIn(""))
        assertNull(MainActivity.firstUrlIn("   "))
    }

    @Test(timeout = 30_000)
    fun onlyASendIntentCarriesALink() {
        val plain = Intent(ctx, MainActivity::class.java)
        assertNull("a launch intent must not look like a share",
            MainActivity.sharedUrlFrom(plain))

        val share = Intent(Intent.ACTION_SEND).setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT, "https://example.com/x")
        assertEquals("https://example.com/x", MainActivity.sharedUrlFrom(share))

        val empty = Intent(Intent.ACTION_SEND).setType("text/plain")
        assertNull(MainActivity.sharedUrlFrom(empty))
        assertNull(MainActivity.sharedUrlFrom(null))
    }

    @Test(timeout = 300_000)
    fun aSharedLinkReachesTheDownloadBox() {
        val logs = File(ctx.getExternalFilesDir(null), "logs")
        File(logs, "share.log").delete()
        logs.listFiles()?.filter { it.name.startsWith("crash-") }?.forEach { it.delete() }

        // fire-and-forget: the real launch path starts the engine, then the
        // page, and only then can the link be handed over
        val intent = Intent(ctx, MainActivity::class.java)
            .setAction(Intent.ACTION_SEND)
            .setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT, "Watch this: http://10.0.2.2:8801/tiny.mp4, great")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(intent)

        val log = File(logs, "share.log")
        var seen = ""
        val deadline = System.currentTimeMillis() + 240_000
        while (System.currentTimeMillis() < deadline) {
            if (log.exists()) {
                seen = log.readText()
                if (seen.contains("tiny.mp4")) break
            }
            Thread.sleep(1000)
        }
        assertTrue(
            "a shared link never reached the UI (share.log: '${seen.take(200)}')",
            seen.contains("shared link: http://10.0.2.2:8801/tiny.mp4"))
        // the punctuation around it must have been dropped, not carried over
        assertTrue("the sentence's comma went along: '$seen'",
            !seen.contains("tiny.mp4,"))

        val crashes = logs.listFiles()?.filter { it.name.startsWith("crash-") }
            ?: emptyList()
        assertTrue("app crashed while handling the share: " +
            crashes.joinToString(" | ") { it.name }, crashes.isEmpty())
    }
}
