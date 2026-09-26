package com.suravidl.app

import android.content.Context
import android.content.Intent
import android.webkit.CookieManager
import android.webkit.WebSettings
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * The handoff, end to end and on the device: the browser finds a stream that is
 * *guarded*, the engine downloads it with the browser's own cookie and the
 * frame it came from as the referer, and the file lands.
 *
 * The fixture is what makes this a real test rather than a smoke test:
 * `/guarded.mp4` answers **403** unless the request carries `Cookie: sv=ok`
 * *and* a `Referer` from the page that embedded it. Nothing else in the app can
 * satisfy that, so a green run means the captured headers genuinely reached
 * yt-dlp — the same promise the desktop extension keeps.
 */
@RunWith(AndroidJUnit4::class)
class HandoffTest {

    @Test(timeout = 300_000)
    fun aGuardedStreamIsDownloadedWithTheBrowsersOwnHeaders() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val engine = "http://127.0.0.1:8787"

        // the engine, through the real app path (MainActivity → EngineService)
        assertEquals("engine never came up", true, bootEngine(ctx, engine))
        val token = ctx.getSharedPreferences("engine", Context.MODE_PRIVATE)
            .getString("token", "").orEmpty()
        assertTrue("no engine token reached shared prefs", token.isNotEmpty())

        val server = FixtureServer().start()
        try {
            val pageUrl = server.url("/guarded.html")
            val mediaUrl = server.url("/guarded.mp4")

            // 1. the guard is real: without the browser's own headers it refuses
            val bare = URL(mediaUrl).openConnection() as HttpURLConnection
            try {
                bare.connectTimeout = 5000
                assertEquals("the fixture's guard is not guarding anything",
                             403, bare.responseCode)
            } finally {
                bare.disconnect()
            }

            // 2. the browser reads a page whose stream is behind that guard
            CookieManager.getInstance().setCookie(pageUrl, "sv=ok")
            SniffLog.clear()
            ctx.startActivity(Intent(ctx, BrowserActivity::class.java)
                .putExtra(BrowserActivity.EXTRA_URL, pageUrl)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))

            var found: Sniffed? = null
            val findDeadline = System.currentTimeMillis() + 90_000
            while (System.currentTimeMillis() < findDeadline) {
                found = SniffLog.snapshot().firstOrNull { it.url.endsWith("/guarded.mp4") }
                if (found != null) break
                Thread.sleep(1000)
            }
            assertNotNull("the browser never saw the guarded stream", found)

            // 3. hand it over with this WebView's cookie jar and its UA
            val cookie = CookieManager.getInstance().getCookie(mediaUrl).orEmpty()
            assertTrue("the WebView holds no cookie for the media URL: '$cookie'",
                       cookie.contains("sv=ok"))
            val headers = Handoff.headersFor(
                frame = found!!.frame.ifEmpty { pageUrl },
                ua = WebSettings.getDefaultUserAgent(ctx),
                cookie = cookie)
            assertTrue("the handoff is not carrying a referer: $headers",
                       headers["Referer"].orEmpty().contains("/guarded.html"))

            val jobId = Handoff.download(engine, token, found.url, headers)
            assertNotNull("the engine refused the handoff", jobId)

            // 4. it downloads — which could only happen with those headers
            var status = ""
            var files = emptyList<String>()
            val done = System.currentTimeMillis() + 180_000
            while (System.currentTimeMillis() < done) {
                val job = getJson("$engine/jobs/$jobId", token)
                status = job?.optString("status").orEmpty()
                files = filesOf(job)
                if (status == "completed" || status == "error") break
                Thread.sleep(2000)
            }
            assertEquals("the job ended as '$status' (files: $files)", "completed", status)
            assertTrue("the job recorded no file", files.isNotEmpty())
            val file = File(files.first())
            assertTrue("the downloaded file is missing or empty: $file",
                       file.exists() && file.length() > 0)
        } finally {
            server.stop()
        }
    }

    @Test(timeout = 30_000)
    fun theHeadersStayInsideTheEnginesAllowList() {
        val h = Handoff.headersFor("https://cdn.example/player.html", "UA/1.0", "a=1")
        assertEquals("UA/1.0", h["User-Agent"])
        assertEquals("https://cdn.example/player.html", h["Referer"])
        assertEquals("a=1", h["Cookie"])
        // an empty frame means "the page itself" — and then no referer is invented
        assertEquals(setOf("User-Agent"), Handoff.headersFor("", "UA/1.0", "").keys)

        // jobs.py forwards only these; anything else would be dropped silently
        val allowed = setOf("cookie", "user-agent", "referer", "origin", "accept",
                            "accept-language")
        for (key in h.keys) {
            assertTrue("the engine would drop this header: $key", key.lowercase() in allowed)
        }
        // markers are proof, never downloads
        assertTrue(!Handoff.isHandoffable("blob:https://x/abc"))
        assertTrue(!Handoff.isHandoffable("mse:video/mp4"))
        assertTrue(Handoff.isHandoffable("https://cdn.example/a.mp4"))
    }

    private fun bootEngine(ctx: Context, engine: String): Boolean {
        ctx.startActivity(Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        val deadline = System.currentTimeMillis() + 200_000
        while (System.currentTimeMillis() < deadline) {
            if (getJson("$engine/health", "") != null) return true
            Thread.sleep(1000)
        }
        return false
    }

    private fun getJson(url: String, token: String): JSONObject? {
        val conn = try {
            URL(url).openConnection() as HttpURLConnection
        } catch (_: Throwable) {
            return null
        }
        return try {
            if (token.isNotEmpty()) conn.setRequestProperty("Authorization", "Bearer $token")
            conn.connectTimeout = 3000
            conn.readTimeout = 15_000
            if (conn.responseCode != 200) null
            else JSONObject(conn.inputStream.bufferedReader().readText())
        } catch (_: Throwable) {
            null
        } finally {
            try {
                conn.disconnect()
            } catch (_: Throwable) {
            }
        }
    }

    private fun filesOf(job: JSONObject?): List<String> {
        if (job == null) return emptyList()
        val arr = job.optJSONArray("files")
        val list = if (arr == null) emptyList()
        else (0 until arr.length()).map { arr.optString(it) }
        return list.ifEmpty { listOfNotNull(job.optString("filepath", "").ifEmpty { null }) }
    }
}
