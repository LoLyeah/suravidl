package com.suravidl.app

import android.graphics.Bitmap
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * The capture layers that live in the WebView client.
 *
 * Layer 1 — `shouldInterceptRequest`: every request the WebView makes, in every
 * frame, including XHR/fetch. Chromium never calls it for `blob:` (by design,
 * verified while planning), which is exactly why the script layers exist.
 * It runs on a WebView handler thread, so everything it touches is
 * thread-safe.
 *
 * Layer 2 — `onLoadResource`: the older, narrower callback, kept because some
 * WebView builds route media-element loads through it and not through layer 1.
 *
 * Layers 3 and 4 are scripts (`SniffScript`), injected at page start and page
 * finish; the finish pass is idempotent and sweeps up what the start pass ran
 * too late to see.
 */
class SnifferWebViewClient(
    private val pageUrl: () -> String,
    private val onPageStart: (String) -> Unit,
) : WebViewClient() {

    override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
        url?.let { onPageStart(it) }
        inject(view)
    }

    override fun onPageFinished(view: WebView?, url: String?) {
        inject(view)
        view?.evaluateJavascript(SniffScript.scan(), null)
    }

    override fun shouldInterceptRequest(
        view: WebView?, request: WebResourceRequest?
    ): WebResourceResponse? {
        val u = request?.url?.toString() ?: return null
        if (SniffPatterns.matches(u)) {
            SniffLog.add(u, "request", pageUrl(), request.isForMainFrame)
        }
        return null
    }

    @Deprecated("kept as a capture layer: it sees loads layer 1 misses on some builds")
    override fun onLoadResource(view: WebView?, url: String?) {
        val u = url ?: return
        if (SniffPatterns.matches(u)) SniffLog.add(u, "load", pageUrl(), false)
    }

    private fun inject(view: WebView?) {
        view?.evaluateJavascript(SniffScript.js(), null)
    }
}
