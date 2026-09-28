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
    /** A refused non-web navigation — the browser says so on screen. */
    private val onAppLinkBlocked: (String) -> Unit,
) : WebViewClient() {

    override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
        url?.let { onPageStart(it) }
        inject(view)
    }

    override fun onPageFinished(view: WebView?, url: String?) {
        inject(view)
        view?.evaluateJavascript(SniffScript.scan(), null)
    }

    /**
     * Refuse what is not a web page. TikTok's mobile pages (and others) fire
     * `snssdk1180://aweme/…` / `intent://…` at the browser to bounce you into
     * their app; letting one through left the load dead half-way with the
     * scheme URL stuck in the address bar and the find list wiped — the
     * 2026-09-28 screenshot. Refused up front, and said out loud instead:
     * the page stays, the finds stay, the user is told why nothing moved.
     */
    override fun shouldOverrideUrlLoading(
        view: WebView?, request: WebResourceRequest?
    ): Boolean {
        val u = request?.url?.toString() ?: return false
        if (isWebUrl(u)) return false
        onAppLinkBlocked(u)
        return true
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

/** What this browser is for. Top-level on purpose: BrowserActivity's load()
 *  and its Go button refuse the same set, so no door (a popup, a new intent,
 *  the address bar) lets a non-web scheme in. */
internal fun isWebUrl(url: String?): Boolean =
    url != null && (url.startsWith("http://") || url.startsWith("https://"))
