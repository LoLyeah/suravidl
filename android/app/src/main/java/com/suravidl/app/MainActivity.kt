package com.suravidl.app

import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.provider.Settings
import android.util.Log
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/** Kiosk for the engine's web UI (same UI as desktop — served at 127.0.0.1:8787). */
class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView

    /** Set once the engine's UI is on screen: a shared link can only be handed
     *  to a page that exists yet. */
    private var pageLoaded = false

    /** A link shared from another app, waiting for the UI to be ready. */
    private var pendingSharedUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Android 15+ always draws edge-to-edge. Apply the system bar insets
        // ourselves so no UI ever hides behind the status/navigation bars.
        WindowCompat.setDecorFitsSystemWindows(window, false)

        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                pageLoaded = true
                deliverSharedUrl()      // a link shared while the UI was loading
            }

            /** This WebView carries the JS bridge, so it must never leave the
             *  engine: a stray link or redirect would hand the bridge to a
             *  stranger's page. Everything else opens in the real browser
             *  (v0.21.1 audit). */
            override fun shouldOverrideUrlLoading(
                view: WebView?, request: WebResourceRequest?
            ): Boolean {
                val target = request?.url?.toString() ?: return true
                if (target.startsWith(engineOrigin())) return false
                if (target.startsWith("https://")) {
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target)))
                    } catch (_: Throwable) {
                    }
                }
                return true
            }
        }
        webView.setBackgroundColor(BG_DARK)
        webView.addJavascriptInterface(HostBridge(), "AndroidHost")
        pendingSharedUrl = sharedUrlFrom(intent)
            ?: savedInstanceState?.getString(STATE_SHARED_URL)

        val root = FrameLayout(this)
        root.setBackgroundColor(BG_DARK)
        root.addView(webView, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        setContentView(root)

        // The UI is modern JS (optional chaining, replaceChildren, …). Android
        // 7.0 ships a 2016 WebView that cannot run it — and WebView updates
        // come from the Play Store independently of the OS, so the honest
        // thing is to look at the engine we actually got and say what to do
        // instead of painting a blank page (UI/Android review).
        val ua = try {
            WebSettings.getDefaultUserAgent(this)
        } catch (_: Throwable) {
            ""
        }
        if (!webViewCanRunTheUi(ua)) {
            webView.loadData(
                "<div style='font-family:sans-serif;padding:18px;color:#ccc'>" +
                "<h3>update Android System WebView</h3>" +
                "<p>This phone's WebView is too old to run the suravidl UI. " +
                "The engine underneath is fine — open Play Store → " +
                "<b>Android System WebView</b> → Update, then reopen " +
                "suravidl.</p></div>", "text/html", "utf-8")
            return
        }

        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars()
                    or WindowInsetsCompat.Type.displayCutout()
                    or WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        ViewCompat.requestApplyInsets(root)

        ContextCompat.startForegroundService(this, Intent(this, EngineService::class.java))
        if (Build.VERSION.SDK_INT >= 33) {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        waitAndLoad(root)
    }

    private fun engineOrigin(): String =
        "http://127.0.0.1:${EngineService.ENGINE_PORT}/"

    /** Chrome 80 is where optional chaining and `replaceChildren` arrive —
     *  below it the UI's own JS cannot even parse. A UA with no Chrome/
     *  version (a WebView we do not recognise) is given the benefit of the
     *  doubt: a wrong refusal would be worse than a UI that might work. */
    private fun webViewCanRunTheUi(ua: String): Boolean {
        val ver = Regex("Chrome/(\\d+)").find(ua)?.groupValues?.get(1)
            ?: return true
        return (ver.toIntOrNull() ?: return true) >= 80
    }

    /** The engine page, with the shell's key: without it the engine answers 401
     *  (any app on the device can reach the loopback port, and that page
     *  carries the API token — v0.21.1 audit). */
    private fun engineUiUrl(): String {
        val key = EngineService.pageKeyOf(this)
        return if (key.isEmpty()) engineOrigin() else engineOrigin() + "?k=" + key
    }

    private fun engineToken(): String =
        getSharedPreferences("engine", MODE_PRIVATE).getString("token", "") ?: ""

    private fun writeLogQuietly(prefix: String, t: Throwable) {
        try {
            LogStore.write(this, "$prefix-${System.currentTimeMillis()}.txt",
                           t.stackTraceToString())
        } catch (_: Throwable) {
        }
    }

    /**
     * Load the engine UI — but only once the responder has proved it is our
     * engine. The port is a fixed constant and a failed bind never reaches
     * Kotlin, so an app that squatted 8787 would otherwise be handed this
     * WebView and its JS bridge. The page inlines our token; only our engine
     * knows it (v0.21.1 audit).
     */
    private fun loadEngineUi() {
        val base = engineOrigin()
        val body = try {
            val c = URL(engineUiUrl()).openConnection() as HttpURLConnection
            try {
                c.connectTimeout = 4000
                c.readTimeout = 10_000
                if (c.responseCode == 200) {
                    c.inputStream.bufferedReader().readText()
                } else null
            } finally {
                c.disconnect()
            }
        } catch (_: Throwable) {
            null
        }
        val token = engineToken()
        if (body == null || token.isEmpty() || !body.contains(token)) {
            runOnUiThread {
                webView.loadData(
                    "<div style='font-family:sans-serif;padding:16px'>" +
                    "<h3>could not load the suravidl UI</h3>" +
                    "<p style='color:#888'>Something else is answering on port " +
                    "${EngineService.ENGINE_PORT} — close it, then reopen " +
                    "suravidl.</p></div>",
                    "text/html", "utf-8")
            }
            return
        }
        runOnUiThread {
            webView.loadDataWithBaseURL(base, body, "text/html", "utf-8", null)
        }
    }

    private fun waitAndLoad(root: FrameLayout) {
        thread {
            repeat(120) {  // 60 s — Python bootstrap can be slow on first run
                try {
                    val c = URL("http://127.0.0.1:${EngineService.ENGINE_PORT}/health")
                        .openConnection() as HttpURLConnection
                    try {
                        c.connectTimeout = 2000
                        if (c.responseCode == 200) {
                            val color = themeBackground()
                            runOnUiThread {
                                root.setBackgroundColor(color)
                                webView.setBackgroundColor(color)
                            }
                            // the cookie session is a nicety, not part of the
                            // boot: a damaged or foreign vault used to throw
                            // inside this loop, which reloaded the whole UI
                            // ~120 times and then showed "engine did not
                            // start" while it was running (v0.21.1 audit)
                            try {
                                restoreCookieSession()
                            } catch (t: Throwable) {
                                Log.w(SuravidlApp.TAG, "cookie restore failed", t)
                                writeLogQuietly("cookie-restore-error", t)
                                // the one failure a user can act on (re-import
                                // cookies.txt) should not be log-only
                                val msg = t.message ?: "could not restore cookies"
                                runOnUiThread {
                                    Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
                                }
                            }
                            loadEngineUi()
                            return@thread
                        }
                    } finally {
                        c.disconnect()
                    }
                } catch (_: Throwable) {
                }
                Thread.sleep(500)
            }
            runOnUiThread {
                val logs = LogStore.readAll(this).replace("&", "&amp;")
                    .replace("<", "&lt;").replace(">", "&gt;")
                val body = if (logs.isEmpty()) {
                    "<p style='color:#888'>No log recorded. A copy would be at " +
                    "Android/media/com.suravidl.app/logs/</p>"
                } else {
                    "<p style='color:#888'>Log (also saved at " +
                    "Android/media/com.suravidl.app/logs/ — please share it):</p>" +
                    "<pre style='white-space:pre-wrap;font-size:11px'>$logs</pre>"
                }
                webView.loadData(
                    "<div style='font-family:sans-serif;padding:16px'>" +
                    "<h3>suravidl engine did not start</h3>$body</div>",
                    "text/html", "utf-8")
            }
        }
    }

    /** Colour of the strip behind the system bars, matched to the saved theme. */
    private fun themeBackground(): Int = try {
        val token = getSharedPreferences("engine", MODE_PRIVATE)
            .getString("token", "") ?: ""
        val c = URL("http://127.0.0.1:${EngineService.ENGINE_PORT}/settings")
            .openConnection() as HttpURLConnection
        c.setRequestProperty("Authorization", "Bearer $token")
        c.connectTimeout = 2000
        when (JSONObject(c.inputStream.bufferedReader().readText())
                .optString("theme", "dark")) {
            "light" -> BG_LIGHT
            "amoled" -> BG_AMOLED
            else -> BG_DARK
        }
    } catch (_: Throwable) {
        BG_DARK
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    /** A link shared while the engine is still starting lives only in a field,
     *  so a rotation or a low-memory kill dropped it and the user's share went
     *  nowhere. Found in the UI/Android review. */
    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        pendingSharedUrl?.let { outState.putString(STATE_SHARED_URL, it) }
    }

    /**
     * A second share while the app already runs arrives here (the activity is
     * singleTask: sharing brings the existing window forward instead of
     * starting a second engine).
     */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val shared = sharedUrlFrom(intent) ?: return
        pendingSharedUrl = shared
        deliverSharedUrl()
    }

    /**
     * Hand a shared link to the UI, which prefills the URL box and probes it —
     * the user still picks the format, exactly as with a pasted link. Waits
     * for the page: giving the URL to a WebView that has no page would drop
     * it on the floor.
     */
    private fun deliverSharedUrl() {
        val url = pendingSharedUrl ?: return
        if (!pageLoaded) return
        pendingSharedUrl = null
        // a real event worth a line in the log: "why didn't my share arrive?"
        // — the host only, because this log lives in Android/media, which any
        // file manager can read (a private or tokenised link must not sit
        // there in the clear — v0.21.1 audit)
        val host = try {
            Uri.parse(url).host ?: "link"
        } catch (_: Throwable) {
            "link"
        }
        LogStore.write(this, "share.log", "shared link from: $host")
        // The full link stays useful for "why didn't my share arrive?" — but
        // the media-dir copy of every log is world-readable, so the URL goes to
        // the app-private dir only (v0.21.1 audit).
        try {
            val priv = File(getExternalFilesDir(null) ?: filesDir, "logs")
                .apply { mkdirs() }
            File(priv, "share-detail.log").appendText("shared link: $url\n")
        } catch (_: Throwable) {
        }
        runOnUiThread {
            webView.evaluateJavascript(
                "window.suravidlShared && window.suravidlShared(${JSONObject.quote(url)})",
                null)
        }
    }

    /** JS bridge: window.AndroidHost.{quit,openBatterySettings,pickCookiesFile,openUrl,
     *  openFile,shareFile,cookiesStatus,deleteCookies,deleteMediaCopies,deleteMediaNamed,
     *  galleryExport}. */
    inner class HostBridge {
        /**
         * Does a finished download also get a Gallery/Music copy?
         *
         * Below API 29 there is no scoped storage, so the app's own folder is
         * already reachable by file managers and `MediaImporter` skips the
         * import (it returns null). The UI must not promise a copy that was
         * never made — it asks this instead of guessing from a user agent.
         */
        @JavascriptInterface
        fun galleryExport(): Boolean = Build.VERSION.SDK_INT >= 29

        @JavascriptInterface
        fun quit() {
            runOnUiThread { quitCompletely() }
        }

        @JavascriptInterface
        fun openBatterySettings() {
            runOnUiThread { openBatterySettingsScreen() }
        }

        @JavascriptInterface
        fun pickCookiesFile() {
            runOnUiThread { openCookiePicker() }
        }

        /** Open a link (e.g. a release page) in the real browser: the in-app
         *  WebView has no tabs and target=_blank goes nowhere. */
        @JavascriptInterface
        fun openUrl(url: String) {
            if (!url.startsWith("https://")) return
            runOnUiThread {
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                } catch (_: Throwable) {
                }
            }
        }

        /**
         * Open the in-app browser on a page, so its streams can be sniffed.
         *
         * The entry point for "this site has no extractor but it does have a
         * player" (v0.24.1, M2 of the capture plan). An empty address is fine:
         * the browser shows its own "type an address" start page.
         */
        @JavascriptInterface
        fun openBrowser(url: String?) {
            val target = url?.trim().orEmpty()
            if (target.isNotEmpty() && !target.startsWith("http://") &&
                !target.startsWith("https://")) return
            runOnUiThread {
                try {
                    // CLEAR_TOP | SINGLE_TOP is not decoration: an identical
                    // singleTask launch is treated as a no-op on some Android
                    // versions — API 30 was one, with the same code passing on
                    // API 36 — so a second "open this in the browser" never
                    // reached the activity and the user kept scanning the
                    // previous page. With CLEAR_TOP the existing instance is
                    // brought forward and the new Intent is delivered to it
                    // (BrowserActivity.onNewIntent does the rest).
                    startActivity(Intent(this@MainActivity, BrowserActivity::class.java)
                        .putExtra(BrowserActivity.EXTRA_URL, target)
                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or
                                  Intent.FLAG_ACTIVITY_SINGLE_TOP))
                } catch (t: Throwable) {
                    LogStore.write(this@MainActivity, "browser-open.log",
                                   "browser failed to open: ${t.message}")
                    toast("could not open the browser")
                }
            }
        }

        /** Play a finished download: Android/data is invisible to file
         *  managers, but a provider grant lets the video player read it. */
        @JavascriptInterface
        fun openFile(path: String) {
            runOnUiThread { handOffFile(path, share = false) }
        }

        @JavascriptInterface
        fun shareFile(path: String) {
            runOnUiThread { handOffFile(path, share = true) }
        }

        @JavascriptInterface
        fun cookiesStatus(): String = CookieVault.status(this@MainActivity)

        @JavascriptInterface
        fun deleteCookies() {
            CookieVault.delete(this@MainActivity)
        }

        /** Gallery/Music copies of finished downloads (Settings → storage wipe). */
        @JavascriptInterface
        fun deleteMediaCopies(): Int =
            MediaLibrary.deleteOwnCopies(this@MainActivity)

        /** The trash button on one row: only that download's library copy. */
        @JavascriptInterface
        fun deleteMediaNamed(name: String?): Int =
            MediaLibrary.deleteOwnCopiesNamed(this@MainActivity, name)
    }

    private fun toast(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    /** Hand a file to another app (player / share sheet) via our FileProvider. */
    private fun handOffFile(path: String, share: Boolean) {
        val f = File(path)
        if (f.isDirectory) {
            // A playlist row reports the download folder: there is no single
            // file to hand to another app (v0.21.2 audit).
            toast("this row is a folder — open a file's own row instead")
            return
        }
        if (!f.exists()) {
            toast("file is gone")
            return
        }
        val mime = when (f.extension.lowercase()) {
            "mp4", "webm", "mkv", "mov", "3gp" -> "video/*"
            "m4a", "mp3", "opus", "ogg", "wav", "aac", "flac" -> "audio/*"
            "srt", "vtt" -> "text/plain"
            else -> "*/*"
        }
        try {
            val uri = FileProvider.getUriForFile(
                this, "$packageName.fileprovider", f)
            val intent = if (share) {
                Intent(Intent.ACTION_SEND).apply {
                    type = mime
                    putExtra(Intent.EXTRA_STREAM, uri)
                    // The platform migrates EXTRA_STREAM into clipData on the
                    // way out, so the read grant normally survives anyway —
                    // this states it instead of trusting that, because a
                    // chooser entry that loses the grant surfaces to the user
                    // as "suravidl crashed" (UI/Android review).
                    clipData = ClipData.newRawUri(null, uri)
                }
            } else {
                Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(uri, mime)
                }
            }
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            startActivity(
                if (share) Intent.createChooser(intent, "Share") else intent)
        } catch (e: Throwable) {
            LogStore.write(this, "open-file.log", "open failed: ${e.message}")
            toast("no app can open this file")
        }
    }

    /** SAF picker: copy the chosen cookies.txt into the app dir, hand the path to the UI. */
    private fun openCookiePicker() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
        }
        try {
            startActivityForResult(intent, REQUEST_COOKIES)
        } catch (_: Throwable) {
            notifyCookiesPicked(null)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_COOKIES) return
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            notifyCookiesPicked(null)
            return
        }
        try {
            val bytes = contentResolver.openInputStream(uri)!!.use { it.readBytes() }
            CookieVault.save(this, bytes)          // encrypted; plaintext dropped
            val session = CookieVault.unlockForSession(this)
            notifyCookiesPicked(session?.absolutePath)
        } catch (e: Throwable) {
            LogStore.write(this@MainActivity, "cookies-import.log",
                           "cookie import failed: ${e.message}")
            notifyCookiesPicked(null)
        }
    }

    /** Point the engine at the decrypted session copy (stable path, recreated
     *  on every start); with nothing stored, clear any stale setting. */
    private fun restoreCookieSession() {
        CookieVault.lockSession(this)               // stale copy from a crash
        CookieVault.migrateLegacy(this)             // encrypt pre-vault imports
        val f = CookieVault.unlockForSession(this)
        pushCookiesSetting(if (f != null) f.absolutePath else "")
    }

    private fun pushCookiesSetting(path: String) {
        try {
            val token = getSharedPreferences("engine", MODE_PRIVATE)
                .getString("token", "") ?: ""
            val c = URL("http://127.0.0.1:${EngineService.ENGINE_PORT}/settings")
                .openConnection() as HttpURLConnection
            c.requestMethod = "POST"
            c.setRequestProperty("Authorization", "Bearer $token")
            c.setRequestProperty("Content-Type", "application/json")
            c.connectTimeout = 3000
            c.doOutput = true
            val body = JSONObject().put("cookies_file", path).toString()
            c.outputStream.use { it.write(body.toByteArray()) }
            c.responseCode
        } catch (e: Throwable) {
            LogStore.write(this, "cookies-session.log",
                           "cookie session: ${e.message}")
        }
    }

    private fun notifyCookiesPicked(path: String?) {
        val arg = if (path == null) "null" else JSONObject.quote(path)
        runOnUiThread {
            webView.evaluateJavascript(
                "window.onCookiesPicked && window.onCookiesPicked($arg)", null)
        }
    }

    /** Full shutdown: stop the engine service, remove the task, free the RAM. */
    private fun quitCompletely() {
        CookieVault.lockSession(this)               // no readable copy at rest
        try {
            stopService(Intent(this, EngineService::class.java))
        } catch (_: Throwable) {
        }
        finishAndRemoveTask()
        Process.killProcess(Process.myPid())
    }

    private fun openBatterySettingsScreen() {
        val candidates = listOf(
            Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS),
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                   Uri.parse("package:$packageName")),
        )
        for (intent in candidates) {
            try {
                startActivity(intent)
                return
            } catch (_: Throwable) {
            }
        }
    }

    companion object {
        const val BG_DARK = 0xFF06080F.toInt()
        const val BG_LIGHT = 0xFFEEF1F7.toInt()
        const val BG_AMOLED = 0xFF000000.toInt()
        private const val REQUEST_COOKIES = 4101

        /** Where a not-yet-delivered shared link waits out a config change. */
        private const val STATE_SHARED_URL = "pending_shared_url"

        /** "https://…" / "http://…", the leading scheme is optional. */
        private val URL_RE = Regex("""https?://[^\s<>"']+""", RegexOption.IGNORE_CASE)

        /** A bare host with a TLD, e.g. youtu.be/x or www.example.com/a?b=c —
         *  the trailing label may carry digits so "clip.mp4" is matched WHOLE
         *  and can then be rejected as a file name rather than a host. */
        private val BARE_HOST_RE = Regex(
            """(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z](?:[a-z0-9-]*[a-z0-9])?(?::\d+)?(?:/[^\s<>"']*)?""",
            RegexOption.IGNORE_CASE)

        /** Trailing punctuation that belongs to the sentence, not the URL. */
        private const val TRAILING = ".,;:!?)]}\u00bb\"'"

        /** How much of a share we look at: a link is short, and the bare-host
         *  pattern is quadratic on long text (v0.21.1 audit — ANR fix). */
        private const val SHARE_MAX = 4096

        /** File extensions that look like a TLD but are not one ("clip.mp4"). */
        private val FILE_EXT = setOf(
            "mp4", "mp3", "m4a", "m4v", "webm", "mkv", "mov", "avi", "pdf", "jpg",
            "jpeg", "png", "gif", "webp", "txt", "zip", "rar", "apk", "csv",
        )

        /**
         * The link inside a text shared from another app, or null.
         *
         * Shares arrive wrapped: "Title – https://…", "Try this https://… !",
         * sometimes just "youtu.be/xyz". Pure on purpose, so a test can point
         * every shape at it without an engine or a UI.
         */
        fun sharedUrlFrom(intent: Intent?): String? {
            if (intent == null || intent.action != Intent.ACTION_SEND) return null
            val text = intent.getStringExtra(Intent.EXTRA_TEXT)?.trim().orEmpty()
            // a share is handled once: the framework replays the intent on every
            // recreation (rotation, dark mode, "don't keep activities") and
            // would otherwise re-fill the URL box behind the user's back
            // (v0.21.1 audit)
            intent.removeExtra(Intent.EXTRA_TEXT)
            if (text.isEmpty()) return null
            return firstUrlIn(text)
        }

        fun firstUrlIn(text: String): String? {
            // A share can carry up to a megabyte (Binder's limit) and the
            // bare-host pattern backtracks quadratically on text without dots:
            // one such share blocked the UI thread for minutes (an ANR, on
            // launch and on every recreation). Bound the input first — a link
            // is nowhere near this long (v0.21.1 audit).
            val bounded = if (text.length > SHARE_MAX) text.take(SHARE_MAX) else text
            URL_RE.find(bounded)?.let { return clean(it.value) }
            // No scheme: accept a bare host, but only a plausible one — not a
            // word inside an e-mail address or a file name.
            for (match in BARE_HOST_RE.findAll(bounded)) {
                val before = bounded.getOrNull(match.range.first - 1)
                if (before != null &&
                    (before == '@' || before.isLetterOrDigit() || before == '-' ||
                     before == '.')) continue
                val candidate = clean(match.value)
                val host = candidate.substringBefore('/').substringBefore(':')
                val tld = host.substringAfterLast('.').lowercase()
                if (!host.contains('.') || host.startsWith('.') || host.endsWith('.')) continue
                if (tld in FILE_EXT) continue
                return "https://$candidate"
            }
            return null
        }

        private fun clean(raw: String): String =
            raw.trimEnd { it in TRAILING }
    }
}
