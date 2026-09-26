package com.suravidl.app

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Handing a sniffed URL to the engine — the step that turns "found" into
 * "downloaded" (M3 of the capture plan).
 *
 * The engine already speaks this language: the extension on the desktop posts
 * the same shape (`{url, headers}` to `/jobs`), and `jobs.py` forwards only the
 * headers a browser actually captured — cookie, user-agent, referer, origin,
 * accept, accept-language. Sending anything else would be dropped silently, so
 * [headersFor] sticks to those.
 *
 * Two rules from the plan are encoded here:
 *   - **frame-first referer**: a signed media URL's referer is usually the
 *     player iframe, not the page in the address bar;
 *   - **the browser's own jar**: the cookies come from this WebView's
 *     CookieManager, so the request the engine makes is the request the player
 *     made.
 */
object Handoff {

    /** Markers are proof, not downloads: `blob:`/`mse:` never reach the engine. */
    fun isHandoffable(url: String): Boolean {
        val u = url.lowercase()
        return u.startsWith("http://") || u.startsWith("https://")
    }

    /** The headers a guarded URL needs, in the engine's own vocabulary. */
    fun headersFor(frame: String, ua: String, cookie: String): Map<String, String> {
        val out = LinkedHashMap<String, String>()
        if (ua.isNotEmpty()) out["User-Agent"] = ua
        if (frame.isNotEmpty()) out["Referer"] = frame
        if (cookie.isNotEmpty()) out["Cookie"] = cookie
        return out
    }

    /**
     * Best-effort "what is this?" — the engine judges. The headers go along so a
     * URL that needs a session can still be looked at.
     */
    fun classify(
        base: String, token: String, url: String, headers: Map<String, String>
    ): JSONObject? = post(base, token, "/classify",
                          JSONObject().put("url", url).put("headers", JSONObject(headers)))

    /** Queue the download. Returns the job id the engine assigned, or null. */
    fun download(
        base: String, token: String, url: String, headers: Map<String, String>
    ): String? = post(base, token, "/jobs",
                      JSONObject().put("url", url).put("headers", JSONObject(headers)))
        ?.optString("id")?.ifEmpty { null }

    /**
     * Which of these finds is worth showing? The engine's shape rule — a
     * playlist over its fragments — asked once for each new list, so the phone
     * and the desktop hide the same rows for the same reason. Null when it
     * cannot answer, and the browser then shows everything: a shell never hides
     * something on a guess.
     */
    fun rank(base: String, token: String, urls: List<String>): JSONObject? {
        val arr = JSONArray()
        for (u in urls) arr.put(u)
        return post(base, token, "/sniff/rank", JSONObject().put("urls", arr))
    }

    private fun post(
        base: String, token: String, path: String, body: JSONObject
    ): JSONObject? {
        val conn = try {
            URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        } catch (_: Throwable) {
            return null
        }
        return try {
            conn.requestMethod = "POST"
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.connectTimeout = 4000
            // /classify fetches the URL itself and yt-dlp may probe: give it room
            conn.readTimeout = 30_000
            conn.doOutput = true
            conn.outputStream.use { it.write(body.toString().toByteArray()) }
            if (conn.responseCode !in 200..299) {
                null
            } else {
                JSONObject(conn.inputStream.bufferedReader().readText())
            }
        } catch (_: Throwable) {
            null
        } finally {
            try {
                conn.disconnect()
            } catch (_: Throwable) {
            }
        }
    }
}
