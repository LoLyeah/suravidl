package com.suravidl.app

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

/**
 * The sniffer's real path: a real WebView loading a real page over real HTTP.
 *
 * The fixture server runs inside this test process, on loopback, so the test
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
                .putExtra(BrowserActivity.EXTRA_URL,
                          "http://127.0.0.1:${server.port}/page.html")
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

/**
 * A tiny HTTP/1.1 server for one test: a page whose player behaves like the
 * real thing — an element `src`, a `fetch`, an iframe, and a MediaSource fed
 * over JavaScript — plus the files it asks for. Loopback only, closed in a
 * `finally`.
 */
private class FixtureServer {
    private val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
    private var running = true

    val port: Int get() = server.localPort

    fun start(): FixtureServer {
        thread(name = "fixture-server") {
            while (running) {
                try {
                    val sock = server.accept()
                    thread { serve(sock) }
                } catch (_: Throwable) {
                    // socket closed by stop(): the loop ends here
                }
            }
        }
        return this
    }

    fun stop() {
        running = false
        try {
            server.close()
        } catch (_: Throwable) {
        }
    }

    private fun serve(sock: Socket) {
        try {
            sock.use {
                val reader = BufferedReader(InputStreamReader(sock.getInputStream()))
                val request = reader.readLine() ?: return
                // drain the headers; a client that still has unread bytes in
                // flight can see a reset instead of our response
                var lines = 0
                while (lines < 50) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                    lines++
                }
                val path = request.split(" ").getOrNull(1)?.substringBefore('?') ?: "/"
                val hit = bodyFor(path)
                val out = sock.getOutputStream()
                if (hit == null) {
                    out.write(("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n" +
                        "Connection: close\r\n\r\n").toByteArray())
                } else {
                    val (type, body) = hit
                    out.write(("HTTP/1.1 200 OK\r\nContent-Type: $type\r\n" +
                        "Content-Length: ${body.size}\r\nConnection: close\r\n\r\n")
                        .toByteArray())
                    out.write(body)
                }
                out.flush()
            }
        } catch (_: Throwable) {
        }
    }

    private fun bodyFor(path: String): Pair<String, ByteArray>? = when (path) {
        "/page.html", "/" -> "text/html" to PAGE.toByteArray()
        "/inner.html" -> "text/html" to INNER.toByteArray()
        "/fixture.m3u8" -> "application/vnd.apple.mpegurl" to MANIFEST.toByteArray()
        "/bare.mp4", "/inner.mp4" -> "video/mp4" to ByteArray(4096)
        else -> null
    }

    companion object {
        /** The same three shapes the live test met in the wild: an element
         *  source, a script fetch, and an MSE player — plus a child frame.
         *
         *  The player starts on a short delay on purpose: that is how a real
         *  page behaves (nothing is requested until the user presses play), and
         *  it is the shape the plan's UX assumes — "press play for a second,
         *  then tap Scan". An immediate `fetch` at parse time would be
         *  measuring the one race the script layers cannot win by design. */
        private val PAGE = """
            <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
            <body style="margin:0;background:#000">
            <video id="v" src="/bare.mp4" muted></video>
            <iframe src="/inner.html" style="width:320px;height:180px"></iframe>
            <script>
              setTimeout(function () {
                fetch('/fixture.m3u8').then(function (r) { return r.text(); });
                try {
                  var ms = new MediaSource();
                  ms.addSourceBuffer('video/mp4; codecs="avc1.42E01E"');
                  document.getElementById('v').src = URL.createObjectURL(ms);
                } catch (e) {}
              }, 1500);
            </script>
            </body>
        """.trimIndent()

        private val INNER = """
            <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
            <body style="margin:0;background:#111"><video src="/inner.mp4" muted></video></body>
        """.trimIndent()

        private val MANIFEST = """
            #EXTM3U
            #EXT-X-VERSION:3
            #EXT-X-TARGETDURATION:2
            #EXTINF:2.0,
            seg1.ts
            #EXT-X-ENDLIST
        """.trimIndent()
    }
}
