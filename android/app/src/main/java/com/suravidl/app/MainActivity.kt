package com.suravidl.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.provider.Settings
import android.view.ViewGroup
import android.webkit.JavascriptInterface
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Android 15+ always draws edge-to-edge. Apply the system bar insets
        // ourselves so no UI ever hides behind the status/navigation bars.
        WindowCompat.setDecorFitsSystemWindows(window, false)

        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()
        webView.setBackgroundColor(BG_DARK)
        webView.addJavascriptInterface(HostBridge(), "AndroidHost")

        val root = FrameLayout(this)
        root.setBackgroundColor(BG_DARK)
        root.addView(webView, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        setContentView(root)

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

    private fun waitAndLoad(root: FrameLayout) {
        thread {
            repeat(120) {  // 60 s — Python bootstrap can be slow on first run
                try {
                    val c = URL("http://127.0.0.1:${EngineService.ENGINE_PORT}/health")
                        .openConnection() as HttpURLConnection
                    c.connectTimeout = 2000
                    if (c.responseCode == 200) {
                        val color = themeBackground()
                        runOnUiThread {
                            root.setBackgroundColor(color)
                            webView.setBackgroundColor(color)
                            webView.loadUrl("http://127.0.0.1:${EngineService.ENGINE_PORT}/")
                        }
                        restoreCookieSession()
                        return@thread
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

    /** JS bridge: window.AndroidHost.{quit,openBatterySettings,pickCookiesFile,openUrl}. */
    inner class HostBridge {
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
    }

    private fun toast(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    /** Hand a file to another app (player / share sheet) via our FileProvider. */
    private fun handOffFile(path: String, share: Boolean) {
        val f = File(path)
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
    }
}
