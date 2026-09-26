package com.suravidl.app

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.CopyOnWriteArrayList

/**
 * One media URL the in-app browser saw, how it was seen, and where it lived.
 *
 * `via` is the *mechanism*, never a verdict: a network capture, a script-made
 * request, the player's own src, or a JavaScript-fed (MSE) stream. Deciding
 * what a URL actually *is* stays the engine's job (`POST /classify`, v0.24.0) —
 * the browser only reports what it saw. Ranking by confidence, not by
 * prettiness, is what keeps an ad creative from outranking the film.
 */
data class Sniffed(
    val url: String,
    val via: String,
    val frame: String,
    val mainFrame: Boolean,
    val at: Long,
)

/**
 * Where the browser's finds land.
 *
 * Thread-safe on purpose: layer 1 (`shouldInterceptRequest`) runs on a WebView
 * handler thread, the JS bridge on another, and the list on the UI thread.
 * A test reads this directly, which is how the sniffer is verified without a
 * UI: real WebView, real HTTP, no screen.
 */
object SniffLog {
    /** Enough to cover a page's worth of noise without becoming a wall. */
    const val MAX = 30
    private const val MAX_URL = 4000

    private val items = CopyOnWriteArrayList<Sniffed>()

    /** Bumped on every change so a poller (or a test) can skip the cheap case. */
    @Volatile
    var version: Int = 0
        private set

    /**
     * Strongest signal wins. A player's own `src`, or an MSE stream, explains
     * a URL better than the network request that happened to fetch it first —
     * so a later, better sighting *upgrades* the row instead of being ignored
     * as a duplicate.
     */
    private val RANK = mapOf(
        "scan" to 1, "load" to 2, "request" to 3, "fetch" to 4, "xhr" to 4,
        "player" to 5, "mse" to 6)

    fun add(url: String, via: String, frame: String, mainFrame: Boolean): Boolean {
        val clean = url.trim()
        if (!acceptable(clean)) return false
        val index = items.indexOfFirst { it.url == clean }
        if (index >= 0) {
            val old = items[index]
            if ((RANK[via] ?: 0) <= (RANK[old.via] ?: 0)) return false
            items[index] = old.copy(via = via, frame = frame.ifEmpty { old.frame })
            version++
            return true
        }
        if (items.size >= MAX) items.removeAt(0)
        items.add(Sniffed(clean, via, frame, mainFrame, System.currentTimeMillis()))
        version++
        return true
    }

    fun snapshot(): List<Sniffed> = items.toList()

    fun clear() {
        if (items.isEmpty()) return
        items.clear()
        version++
    }

    /**
     * http(s) is a candidate. `blob:` and `mse:` are *markers*: they carry no
     * bytes anyone can download, but they prove the player is fed by
     * JavaScript — which is precisely what a network capture cannot see, and
     * why the script layers exist at all.
     */
    internal fun acceptable(url: String): Boolean {
        if (url.isEmpty() || url.length > MAX_URL) return false
        val u = url.lowercase(Locale.ROOT)
        return u.startsWith("http://") || u.startsWith("https://") ||
            u.startsWith("blob:") || u.startsWith("mse:")
    }
}

/**
 * The media-pattern list: baked in, but the engine owns the truth.
 *
 * The same list exists three times by design — the engine's `/sniff/patterns`
 * (source of truth), the extension's copy (until M4 moves it), and this one.
 * A test keeps both shells' lists a *subset* of the engine's, so a shell can
 * only ever prefilter fewer URLs than the engine can name: a miss costs a
 * candidate, never a wrong one. The engine's list is fetched at browser start
 * and the copy below stands in whenever it is not answering.
 */
object SniffPatterns {
    val FALLBACK_EXT = listOf(
        "mp4", "m4v", "webm", "mov", "mkv", "avi", "flv", "wmv", "ogv",
        "m3u8", "mpd", "ts", "m4s",
        "mp3", "m4a", "aac", "ogg", "opus", "wav", "flac")
    val FALLBACK_HINTS = listOf(
        "manifest", "playlist", "master.m3u8", "/hls/", "/dash/",
        "videoplayback", "format=m3u8", "type=m3u8")

    private val lock = Any()
    private var ext: List<String> = FALLBACK_EXT
    private var hints: List<String> = FALLBACK_HINTS
    private var re: Regex = regexFor(FALLBACK_EXT)

    fun extList(): List<String> = synchronized(lock) { ext }
    fun hintList(): List<String> = synchronized(lock) { hints }

    /**
     * Does this URL look like media? A prefilter only — it decides what gets
     * *looked at*, never what gets *shown* (that is the engine's `/classify`).
     */
    fun matches(url: String): Boolean {
        val u = url.substringBefore('#').lowercase(Locale.ROOT)
        val (r, h) = synchronized(lock) { re to hints }
        if (r.containsMatchIn(u)) return true
        for (hint in h) if (u.contains(hint)) return true
        return false
    }

    /** Install the engine's list. Returns whether it was used. */
    fun fetchFromEngine(base: String, token: String): Boolean {
        val conn = try {
            URL(base.trimEnd('/') + "/sniff/patterns").openConnection() as HttpURLConnection
        } catch (_: Throwable) {
            return false
        }
        return try {
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.connectTimeout = 1500
            conn.readTimeout = 2500
            if (conn.responseCode != 200) {
                false
            } else {
                val o = JSONObject(conn.inputStream.bufferedReader().readText())
                val newExt = o.optJSONArray("ext")?.strings() ?: emptyList()
                val newHints = o.optJSONArray("hints")?.strings()
                    ?.map { it.lowercase(Locale.ROOT) } ?: emptyList()
                if (newExt.isEmpty()) {
                    false
                } else {
                    synchronized(lock) {
                        ext = newExt
                        hints = newHints
                        re = regexFor(newExt)
                    }
                    true
                }
            }
        } catch (_: Throwable) {
            false
        } finally {
            try {
                conn.disconnect()
            } catch (_: Throwable) {
            }
        }
    }

    /** Back to the baked-in copy (tests, and a settings reset path). */
    fun reset() {
        synchronized(lock) {
            ext = FALLBACK_EXT
            hints = FALLBACK_HINTS
            re = regexFor(FALLBACK_EXT)
        }
    }

    private fun regexFor(ext: List<String>): Regex =
        Regex("""\.(""" + ext.joinToString("|") { Regex.escape(it) } +
            """)(\?|${'$'})""", RegexOption.IGNORE_CASE)

    private fun JSONArray.strings(): List<String> =
        (0 until length()).mapNotNull { optString(it, "").ifEmpty { null } }
}
