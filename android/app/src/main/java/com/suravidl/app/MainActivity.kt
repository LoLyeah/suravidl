package com.suravidl.app

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/** Kiosk for the engine's web UI (same UI as desktop — served at 127.0.0.1:8787). */
class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()
        setContentView(webView)

        ContextCompat.startForegroundService(this, Intent(this, EngineService::class.java))
        if (Build.VERSION.SDK_INT >= 33) {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        waitAndLoad()
    }

    private fun waitAndLoad() {
        thread {
            repeat(60) {
                try {
                    val c = URL("http://127.0.0.1:${EngineService.ENGINE_PORT}/health")
                        .openConnection() as HttpURLConnection
                    c.connectTimeout = 2000
                    if (c.responseCode == 200) {
                        runOnUiThread {
                            webView.loadUrl("http://127.0.0.1:${EngineService.ENGINE_PORT}/")
                        }
                        return@thread
                    }
                } catch (_: Exception) {
                }
                Thread.sleep(500)
            }
            runOnUiThread {
                webView.loadData(
                    "<h3 style='font-family:sans-serif'>suravidl engine did not start</h3>",
                    "text/html", "utf-8")
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}