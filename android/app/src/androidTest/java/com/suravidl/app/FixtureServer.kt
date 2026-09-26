package com.suravidl.app

import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.concurrent.thread

/**
 * A tiny HTTP/1.1 server for tests, on loopback, inside the test process.
 *
 * Running it here rather than on the CI host means every test that uses it needs
 * nothing but the emulator: a real WebView, real HTTP, no `10.0.2.2`, no runner
 * networking.
 *
 * The fixture page behaves like a real one: a plain `<video src>`, a script
 * `fetch`, an MSE player (started on a short delay, the way a page waits for the
 * user to press play), and a same-origin child frame. `/guarded.mp4` is the
 * handoff fixture — it answers 403 unless the request carries the Cookie the
 * browser holds *and* a Referer from the page that embedded it, which is exactly
 * what "the captured headers reached yt-dlp" means.
 */
class FixtureServer {
    private val server = ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"))
    private var running = true

    /** Every request served: its path and the headers it arrived with. */
    val seen = CopyOnWriteArrayList<Pair<String, Map<String, String>>>()

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

    fun url(path: String): String = "http://127.0.0.1:$port$path"

    private fun serve(sock: Socket) {
        try {
            sock.use {
                val reader = BufferedReader(InputStreamReader(sock.getInputStream()))
                val request = reader.readLine() ?: return
                val headers = LinkedHashMap<String, String>()
                var lines = 0
                while (lines < 60) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                    val at = line.indexOf(':')
                    if (at > 0) {
                        headers[line.substring(0, at).trim().lowercase()] =
                            line.substring(at + 1).trim()
                    }
                    lines++
                }
                val path = request.split(" ").getOrNull(1)?.substringBefore('?') ?: "/"
                seen.add(path to headers)
                val hit = bodyFor(path, headers)
                val out = sock.getOutputStream()
                if (hit == null) {
                    out.write(("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n" +
                        "Connection: close\r\n\r\n").toByteArray())
                } else {
                    val (code, type, body) = hit
                    val reason = if (code == 200) "OK" else "Forbidden"
                    out.write(("HTTP/1.1 $code $reason\r\nContent-Type: $type\r\n" +
                        "Content-Length: ${body.size}\r\nConnection: close\r\n\r\n")
                        .toByteArray())
                    out.write(body)
                }
                out.flush()
            }
        } catch (_: Throwable) {
        }
    }

    /** a small mp4-shaped body: enough bytes that a download can be asserted on */
    private fun media(): ByteArray = ByteArray(4096)

    private fun bodyFor(
        path: String, headers: Map<String, String>
    ): Triple<Int, String, ByteArray>? = when (path) {
        "/", "/page.html" -> Triple(200, "text/html", PAGE.toByteArray())
        "/inner.html" -> Triple(200, "text/html", INNER.toByteArray())
        "/guarded.html" -> Triple(200, "text/html", GUARDED_PAGE.toByteArray())
        "/noext.html" -> Triple(200, "text/html", NOEXT_PAGE.toByteArray())
        "/noext-inner.html" -> Triple(200, "text/html", NOEXT_INNER.toByteArray())
        "/second.html" -> Triple(200, "text/html", SECOND_PAGE.toByteArray())
        "/fixture.m3u8" -> Triple(200, "application/vnd.apple.mpegurl",
                                  MANIFEST.toByteArray())
        "/bare.mp4", "/inner.mp4" -> Triple(200, "video/mp4", media())
        "/second.mp4" -> Triple(200, "video/mp4", media())
        "/media/plainid1234" -> Triple(200, "video/mp4", media())
        "/guarded.mp4" -> if (guardAllows(headers)) {
            Triple(200, "video/mp4", media())
        } else {
            Triple(403, "text/plain", "cookie and referer required".toByteArray())
        }
        else -> null
    }

    /** The gate the handoff has to beat: the browser's cookie, and a referer
     *  from the page that embedded the file. */
    private fun guardAllows(headers: Map<String, String>): Boolean {
        val cookie = headers["cookie"].orEmpty()
        val referer = headers["referer"].orEmpty()
        return cookie.contains("sv=ok") && referer.contains("/guarded.html")
    }

    companion object {
        /** The shapes the live test met in the wild: an element source, a script
         *  fetch, an MSE player — plus a child frame.
         *
         *  The player starts on a short delay on purpose: that is what a real
         *  page does (nothing is requested until the user presses play), and it
         *  is the shape the plan's UX assumes — "press play for a second, then
         *  tap Scan". An immediate `fetch` at parse time would be measuring the
         *  one race the script layers cannot win by design. */
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

        /** A page whose stream is behind the guard above. */
        private val GUARDED_PAGE = """
            <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
            <body style="margin:0;background:#000"><video src="/guarded.mp4" muted></video></body>
        """.trimIndent()

        /** The shape a real site served (vidmonstr, 2026-09-26): the player sits
         *  in a *same-origin* child frame and points at a stream with no media
         *  extension, on another host. No URL pattern can recognise that — a
         *  miss there costs a real video — so the player's own element is the
         *  only honest evidence there is. */
        private val NOEXT_PAGE = """
            <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
            <body style="margin:0;background:#000">
            <iframe src="/noext-inner.html" style="width:320px;height:180px"></iframe>
            </body>
        """.trimIndent()

        private val NOEXT_INNER = """
            <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
            <body style="margin:0;background:#111"><video src="/media/plainid1234" muted></video></body>
        """.trimIndent()

        /** A second page with one find of its own, for the "another link" test. */
        private val SECOND_PAGE = """
            <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
            <body style="margin:0;background:#000"><video src="/second.mp4" muted></video></body>
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
