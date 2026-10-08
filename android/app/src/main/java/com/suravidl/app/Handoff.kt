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

    /**
     * Queue a find like [download], but wait for an engine that is still
     * starting. The phone's engine boots on a background thread (chaquopy
     * warm-up, module import, DB load) while the in-app browser is already
     * usable by design — so a tap made seconds after a sniff could hit a
     * port that was not listening yet and read as "the engine refused it"
     * (2026-10-08 field report: the toast "literally seconds after"
     * sniffing). A failure that happened BEFORE anything was written can
     * only be the engine's door being shut: the request never arrived, so
     * retrying cannot double-queue. A request already on the wire is never
     * retried — its outcome is unknown, and a surprise second copy of the
     * job would be worse than a rare "try again".
     */
    fun downloadWhenReady(
        base: String, token: String, url: String, headers: Map<String, String>,
        attempts: Int = 24, delayMs: Long = 1500
    ): String? {
        repeat(attempts) { i ->
            val (resp, retryable) = postOutcome(
                base, token, "/jobs",
                JSONObject().put("url", url).put("headers", JSONObject(headers)))
            if (resp != null) return resp.optString("id").ifEmpty { null }
            if (!retryable) return null
            if (i < attempts - 1) {
                try {
                    Thread.sleep(delayMs)
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    return null
                }
            }
        }
        return null
    }

    private fun post(
        base: String, token: String, path: String, body: JSONObject
    ): JSONObject? = postOutcome(base, token, path, body).first

    /**
     * [post], but honest about whether a retry is safe: the boolean is
     * `true` only when the failure happened before the request body was
     * written — the engine was not listening and nothing ever reached it.
     */
    private fun postOutcome(
        base: String, token: String, path: String, body: JSONObject
    ): Pair<JSONObject?, Boolean> {
        val conn = try {
            URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        } catch (_: Throwable) {
            return null to false
        }
        var sent = false
        return try {
            conn.requestMethod = "POST"
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.connectTimeout = 4000
            // /classify fetches the URL itself and yt-dlp may probe: give it room
            conn.readTimeout = 30_000
            conn.doOutput = true
            conn.outputStream.use {
                it.write(body.toString().toByteArray())
                sent = true
            }
            if (conn.responseCode !in 200..299) {
                null to false
            } else {
                JSONObject(conn.inputStream.bufferedReader().readText()) to false
            }
        } catch (_: Throwable) {
            null to !sent
        } finally {
            try {
                conn.disconnect()
            } catch (_: Throwable) {
            }
        }
    }
}
