package com.suravidl.app

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Message
import android.text.InputType
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.concurrent.thread

/**
 * A plain browser with a sniffer attached — the answer to a site yt-dlp cannot
 * extract and whose player builds its stream in JavaScript. (Desktop does this
 * with the extension; the phone has no extensions, so the browser comes in.)
 *
 * It is *not* a downloader: it shows what the page asked for, strongest signal
 * first, and copying a URL is as far as it goes today. Handing a candidate to
 * the engine — with this WebView's cookies, referer and User-Agent — is M3.
 *
 * Honest UX, per the plan: a JavaScript player asks for its stream only when it
 * starts, so the user presses play, then taps Scan. The screen says so.
 */
class BrowserActivity : AppCompatActivity() {

    private lateinit var root: LinearLayout
    private lateinit var webView: WebView
    private lateinit var urlField: EditText
    private lateinit var listBox: LinearLayout
    private lateinit var status: TextView
    private lateinit var empty: TextView
    private val ui = Handler(Looper.getMainLooper())
    private var lastVersion = -1
    private var bg = MainActivity.BG_DARK

    /**
     * The page the captures belong to.
     *
     * A plain field, not `webView.url`: layer 1 runs on a WebView background
     * thread, and *any* WebView method called off the main thread throws
     * ("All WebView methods must be called on the same thread") — which is
     * exactly how this bug reached CI the first time.
     */
    @Volatile
    private var currentPage: String = ""

    /** This WebView's own User-Agent, read once on the UI thread: a WebView may
     *  only be asked anything from there, and the handoff needs it later. */
    private var ua: String = ""

    /** What the engine says each find *is* — kind, size, drm. Filled off the UI
     *  thread, one URL at a time, by [classifyOne]. */
    private val info = HashMap<String, JSONObject>()
    private val queued = HashSet<String>()
    private val classifyQueue = LinkedHashSet<String>()
    private val worker = Executors.newSingleThreadExecutor()

    /** Finds the engine called fragments of a playlist that is also here — url
     *  to reason. The count is shown, so nothing vanishes unexplained. */
    private var hidden: Map<String, String> = emptyMap()
    private var rankedFor: Int = -1

    private val ticker = object : Runnable {
        override fun run() {
            refreshIfChanged()
            ui.postDelayed(this, 700)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        if (BuildConfig.DEBUG) WebView.setWebContentsDebuggingEnabled(true)
        buildUi()
        webView.addJavascriptInterface(SniffBridge(), "SuravidlSniff")

        // The engine owns the pattern list; the baked-in copy stands when it is
        // not answering yet, so nothing here blocks the browser from opening.
        thread {
            val token = prefs().getString("token", "") ?: ""
            if (token.isNotEmpty()) SniffPatterns.fetchFromEngine(engineOrigin(), token)
            val color = themeColor(token)
            ui.post {
                if (isFinishing || isDestroyed) return@post
                applyTheme(color)
            }
        }

        val start = intent.getStringExtra(EXTRA_URL).orEmpty()
        if (start.isNotEmpty()) load(start) else loadStartPage()
        ui.postDelayed(ticker, 700)
    }

    override fun onDestroy() {
        ui.removeCallbacks(ticker)
        worker.shutdownNow()
        super.onDestroy()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    // -- chrome ---------------------------------------------------------------

    private fun buildUi() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(bg)
        }

        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(4), dp(8), dp(8), dp(2))
        }
        bar.addView(chip("‹") { if (webView.canGoBack()) webView.goBack() })
        bar.addView(chip("›") { if (webView.canGoForward()) webView.goForward() })
        bar.addView(chip("⟳") { webView.reload(); SniffLog.clear() })
        urlField = EditText(this).apply {
            setSingleLine(true)
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            imeOptions = EditorInfo.IME_ACTION_GO
            hint = "paste a page's address"
            setTextColor(Color.WHITE)
            setHintTextColor(GREY)
            textSize = 14f
            setBackgroundColor(0x14FFFFFF)
            setPadding(dp(10), dp(8), dp(10), dp(8))
            setOnEditorActionListener { _, actionId, _ ->
                if (actionId == EditorInfo.IME_ACTION_GO) {
                    go()
                    true
                } else false
            }
        }
        bar.addView(urlField, LinearLayout.LayoutParams(0, WRAP, 1f))
        bar.addView(chip("Go") { go() })
        root.addView(bar)

        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), 0, dp(8), dp(4))
        }
        status = TextView(this).apply {
            setTextColor(GREY)
            textSize = 12.5f
        }
        row.addView(status, LinearLayout.LayoutParams(0, WRAP, 1f))
        row.addView(chip("Scan") { scanAgain() })
        row.addView(chip("Clear list") {
            SniffLog.clear()
            render()
        })
        row.addView(chip("Clear data") { clearBrowsingData() })
        root.addView(row)

        webView = WebView(this).apply {
            settings.javaScriptEnabled = true          // the page is JS; so is the sniffer
            settings.domStorageEnabled = true
            settings.setSupportMultipleWindows(true)
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            setBackgroundColor(bg)
            webChromeClient = object : WebChromeClient() {
                /** `target=_blank` has nowhere to go without tabs: load it here. */
                override fun onCreateWindow(
                    view: WebView?, isDialog: Boolean, isUserGesture: Boolean, resultMsg: Message?
                ): Boolean {
                    val tmp = WebView(this@BrowserActivity)
                    tmp.webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(
                            v: WebView?, r: WebResourceRequest?
                        ): Boolean {
                            r?.url?.toString()?.let { load(it) }
                            return true
                        }
                    }
                    (resultMsg?.obj as? WebView.WebViewTransport)?.webView = tmp
                    resultMsg?.sendToTarget()
                    return true
                }
            }
            webViewClient = SnifferWebViewClient(
                pageUrl = { currentPage },
                onPageStart = { url ->
                    currentPage = url
                    if (!urlField.hasFocus()) urlField.setText(url)
                    SniffLog.clear()                    // a new page, new finds
                    refreshIfChanged()
                })
        }
        ua = try {
            webView.settings.userAgentString.orEmpty()
        } catch (_: Throwable) {
            ""
        }
        root.addView(webView, LinearLayout.LayoutParams(MATCH, 0, 1f))

        val scroll = ScrollView(this)
        listBox = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(4), dp(12), dp(12))
        }
        empty = TextView(this).apply {
            text = "Nothing found yet.\n\nOpen the video's page and press play for a " +
                "second — a JavaScript player only asks for its stream once it " +
                "starts — then tap Scan. What shows up here is what the page " +
                "asked for; the strongest signal (the stream you are actually " +
                "watching) is marked as such."
            setTextColor(GREY)
            textSize = 13f
            setLineSpacing(0f, 1.35f)
        }
        listBox.addView(empty)
        scroll.addView(listBox)
        root.addView(scroll, LinearLayout.LayoutParams(MATCH, dp(232)))

        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars()
                    or WindowInsetsCompat.Type.displayCutout()
                    or WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        ViewCompat.requestApplyInsets(root)
        setContentView(root)
    }

    private fun applyTheme(color: Int) {
        bg = color
        root.setBackgroundColor(color)
        webView.setBackgroundColor(color)
    }

    private fun loadStartPage() {
        val html = "<!doctype html><meta name=viewport content='width=device-width," +
            "initial-scale=1'><body style='margin:0;background:#06080F;color:#cfd6ea;" +
            "font-family:sans-serif;padding:22px'>" +
            "<h3 style='margin:0 0 10px'>Find a video on a page</h3>" +
            "<p style='color:#8a93a8;font-size:14px;line-height:1.5'>Type the address of " +
            "the page that plays the video above and press Go. When the video is " +
            "playing, tap Scan.</p>" +
            "<p style='color:#8a93a8;font-size:13px;line-height:1.5'>This is a plain " +
            "browser with a sniffer attached. Its cookies stay inside this WebView " +
            "and nothing is sent anywhere.</p></body>"
        webView.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    }

    // -- actions --------------------------------------------------------------

    private fun go() {
        var u = urlField.text.toString().trim()
        if (u.isEmpty()) return
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "https://$u"
        load(u)
    }

    private fun load(url: String) {
        currentPage = url
        SniffLog.clear()
        refreshIfChanged()
        urlField.setText(url)
        webView.loadUrl(url)
    }

    /** Ask again: re-install the hooks, then sweep the resource timeline. */
    private fun scanAgain() {
        status.text = "scanning…"
        webView.evaluateJavascript(SniffScript.js(), null)
        webView.evaluateJavascript(SniffScript.scan(), null)
    }

    private fun refreshIfChanged() {
        if (SniffLog.version == lastVersion) return
        lastVersion = SniffLog.version
        render()
    }

    /** Draw the list. UI thread only: the poller calls it, and so does whatever
     *  a background classify or handoff just finished doing. */
    private fun render() {
        lastVersion = SniffLog.version
        rankIfNeeded()                                    // the engine's shape rule
        val all = SniffLog.snapshot().asReversed()        // newest first
        val items = all.filter { !hidden.containsKey(it.url) }
        listBox.removeAllViews()
        if (all.isEmpty()) {
            listBox.addView(empty)
        } else {
            if (all.size >= SniffLog.MAX) {
                listBox.addView(note("kept the newest ${SniffLog.MAX}"))
            }
            for (c in items) listBox.addView(row(c))
            if (hidden.isNotEmpty()) {
                listBox.addView(note(
                    "${hidden.size} fragments belong to a playlist above — hidden"))
            }
        }
        // ask the engine what each new find is — it owns that judgement, and it
        // gets the headers a guarded URL needs to be looked at at all
        for (c in items) {
            if (!Handoff.isHandoffable(c.url)) continue
            if (info.containsKey(c.url) || !classifyQueue.add(c.url)) continue
            classifyOne(c)
        }
        status.text = when {
            all.isEmpty() -> "nothing found — press play, then Scan"
            queued.isNotEmpty() -> "${all.size} found · ${queued.size} queued"
            else -> "${all.size} found · press play, then Scan"
        }
    }

    /**
     * Ask the engine which of these finds is worth showing — a playlist over its
     * fragments, the same rule the desktop popup uses — once for each new list.
     * Until it answers, and if it never does, everything is shown.
     */
    private fun rankIfNeeded() {
        val urls = SniffLog.snapshot().map { it.url }
        if (urls.size < 2 || rankedFor == SniffLog.version) return
        val token = prefs().getString("token", "") ?: ""
        if (token.isEmpty()) return
        rankedFor = SniffLog.version
        worker.execute {
            val out = Handoff.rank(engineOrigin(), token, urls)
            val hide = HashMap<String, String>()
            val arr = out?.optJSONArray("items")
            if (arr != null) {
                for (i in 0 until arr.length()) {
                    val one = arr.optJSONObject(i) ?: continue
                    if (one.optBoolean("hidden")) {
                        hide[one.optString("url")] = one.optString("reason")
                    }
                }
            }
            ui.post {
                hidden = hide
                if (!isFinishing && !isDestroyed) render()
            }
        }
    }

    private fun row(c: Sniffed): View {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(8))
            background = rounded(0x14FFFFFF, 14f)
            layoutParams = LinearLayout.LayoutParams(MATCH, WRAP).apply { bottomMargin = dp(8) }
        }
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        head.addView(TextView(this).apply {
            text = VIA_LABEL[c.via] ?: c.via
            textSize = 10.5f
            setTextColor(0xFFDFE4F4.toInt())
            background = rounded(0x33818CF8, 99f)
            setPadding(dp(7), dp(3), dp(7), dp(3))
        })
        val verdict = verify(c)
        if (verdict != null) {
            head.addView(TextView(this).apply {
                text = "  $verdict"
                textSize = 10.5f
                setTextColor(if (isDrm(c.url)) 0xFFF2B8B8.toInt() else 0xFFBFE6C8.toInt())
                background = rounded(if (isDrm(c.url)) 0x40C0504E else 0x2E66C98A, 99f)
                setPadding(dp(7), dp(3), dp(7), dp(3))
            })
        }
        val where = frameLabel(c.frame)
        if (c.via != "mse" && where.isNotEmpty()) {
            head.addView(TextView(this).apply {
                text = "  in $where"
                textSize = 11f
                setTextColor(GREY)
            })
        }
        box.addView(head)
        box.addView(TextView(this).apply {
            text = if (c.via == "mse") "MSE stream — fed by JavaScript" else c.url
            textSize = 12f
            setTextColor(if (c.via == "mse") GREY else Color.WHITE)
            typeface = Typeface.MONOSPACE
            maxLines = 3
            ellipsize = TextUtils.TruncateAt.MIDDLE
            setPadding(0, dp(5), 0, dp(4))
        })
        val acts = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        if (c.via == "mse") {
            acts.addView(note("a blob: stream — look for the manifest above"))
        } else {
            if (queued.contains(c.url)) {
                acts.addView(chip("queued ✓") { toast("it downloads in the app's Queue tab") })
            } else if (Handoff.isHandoffable(c.url) && !isDrm(c.url)) {
                acts.addView(chip("Download") { queue(c) })
            }
            acts.addView(chip("Copy") { copy(c.url) })
            if (c.url.startsWith("http")) acts.addView(chip("Open") { openOutside(c.url) })
        }
        box.addView(acts)
        return box
    }

    private fun copy(url: String) {
        val clip = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clip.setPrimaryClip(ClipData.newPlainText("suravidl", url))
        Toast.makeText(this, "URL copied", Toast.LENGTH_SHORT).show()
    }

    private fun openOutside(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: Throwable) {
            Toast.makeText(this, "no app can open this", Toast.LENGTH_SHORT).show()
        }
    }

    // -- the handoff: classify what we found, then hand it to the engine ------

    /** The engine's one-line verdict on a find, e.g. "HLS · 42 MB". */
    private fun verify(c: Sniffed): String? {
        val v = info[c.url] ?: return if (classifyQueue.contains(c.url)) "checking…" else null
        if (v.optBoolean("drm")) return "DRM — not downloadable"
        val kind = when (v.optString("kind")) {
            "hls" -> "HLS"
            "dash" -> "DASH"
            "video" -> "video"
            "audio" -> "audio"
            "image" -> "image"
            "page" -> "page"
            else -> ""
        }
        val size = v.optLong("size", 0)
        return when {
            kind.isEmpty() -> null
            size > 0 -> "$kind · ${humanSize(size)}"
            else -> kind
        }
    }

    private fun isDrm(url: String): Boolean = info[url]?.optBoolean("drm") ?: false

    private fun humanSize(bytes: Long): String = when {
        bytes >= 1_048_576 -> String.format(Locale.US, "%.1f MB", bytes / 1048576.0)
        bytes >= 1024 -> "${bytes / 1024} KB"
        else -> "$bytes B"
    }

    /**
     * The headers this find needs to be looked at or fetched: this WebView's own
     * cookie jar, its own User-Agent, and the frame it came from as the referer.
     * UI thread only — [ua] was read there, and a WebView is never touched from
     * anywhere else.
     */
    private fun headersFor(c: Sniffed): Map<String, String> {
        val cookie = try {
            CookieManager.getInstance().getCookie(c.url).orEmpty()
        } catch (_: Throwable) {
            ""
        }
        return Handoff.headersFor(c.frame.ifEmpty { currentPage }, ua, cookie)
    }

    private fun classifyOne(c: Sniffed) {
        val token = prefs().getString("token", "") ?: ""
        if (token.isEmpty()) return
        val headers = headersFor(c)
        worker.execute {
            val verdict = Handoff.classify(engineOrigin(), token, c.url, headers)
            ui.post {
                classifyQueue.remove(c.url)
                if (verdict != null) info[c.url] = verdict
                if (!isFinishing && !isDestroyed) render()
            }
        }
    }

    /** Hand a find to the engine — the whole point of this browser. */
    private fun queue(c: Sniffed) {
        if (!Handoff.isHandoffable(c.url)) return
        val token = prefs().getString("token", "") ?: ""
        if (token.isEmpty()) {
            toast("the engine is not ready — try again in a moment")
            return
        }
        val headers = headersFor(c)
        toast("queueing…")
        worker.execute {
            val id = Handoff.download(engineOrigin(), token, c.url, headers)
            ui.post {
                if (id == null) {
                    toast("the engine refused it — is it still running?")
                } else {
                    queued.add(c.url)
                    toast("queued — it downloads in the app's Queue tab")
                    render()
                }
            }
        }
    }

    /**
     * The data *this* browser collected: cookies, site storage, the cache.
     * Deliberately not the imported cookie file, the vault, or any download —
     * and the confirm says so, because "clear browsing data" inside a downloader
     * could reasonably be read as something much worse.
     */
    private fun clearBrowsingData() {
        AlertDialog.Builder(this)
            .setTitle("Clear browsing data?")
            .setMessage("Cookies, site storage and the cache collected by this " +
                "browser. Your downloads and your imported cookie file are not " +
                "touched.")
            .setPositiveButton("Clear") { _, _ ->
                try {
                    CookieManager.getInstance().removeAllCookies(null)
                    CookieManager.getInstance().flush()
                } catch (_: Throwable) {
                }
                try {
                    WebStorage.getInstance().deleteAllData()
                } catch (_: Throwable) {
                }
                try {
                    webView.clearCache(true)
                    webView.clearHistory()
                } catch (_: Throwable) {
                }
                toast("browser data cleared")
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun toast(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    // -- plumbing -------------------------------------------------------------

    private fun prefs() = getSharedPreferences("engine", MODE_PRIVATE)

    private fun engineOrigin(): String = "http://127.0.0.1:${EngineService.ENGINE_PORT}"

    /** Strip behind the system bars, matched to the saved theme (same rule as
     *  MainActivity: the host re-expresses the theme in its own terms). */
    private fun themeColor(token: String): Int = try {
        val c = URL("${engineOrigin()}/settings").openConnection() as HttpURLConnection
        try {
            c.setRequestProperty("Authorization", "Bearer $token")
            c.connectTimeout = 2000
            c.readTimeout = 2500
            when (JSONObject(c.inputStream.bufferedReader().readText())
                .optString("theme", "dark")) {
                "light" -> MainActivity.BG_LIGHT
                "amoled" -> MainActivity.BG_AMOLED
                else -> MainActivity.BG_DARK
            }
        } finally {
            c.disconnect()
        }
    } catch (_: Throwable) {
        MainActivity.BG_DARK
    }

    private fun frameLabel(frame: String): String = try {
        val u = Uri.parse(frame)
        val last = u.lastPathSegment.orEmpty()
        val host = u.host.orEmpty()
        if (host.isEmpty()) "" else host + (if (last.isEmpty()) "" else "/$last")
    } catch (_: Throwable) {
        ""
    }

    private fun dp(n: Int): Int = (n * resources.displayMetrics.density).toInt()

    private fun rounded(color: Int, radiusDp: Float): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            setColor(color)
            cornerRadius = radiusDp * resources.displayMetrics.density
        }

    private fun chip(label: String, onClick: () -> Unit): Button =
        Button(this).apply {
            text = label
            isAllCaps = false
            textSize = 13f
            minWidth = 0
            minimumWidth = 0
            minHeight = 0
            minimumHeight = 0
            setPadding(dp(10), dp(4), dp(10), dp(4))
            setOnClickListener { onClick() }
        }

    private fun note(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 11.5f
            setTextColor(GREY)
        }

    /**
     * The JS side of layers 3 and 4. Minimal on purpose: one method that takes
     * (url, how, frame), validated again in [SniffLog] before it is kept. A
     * page that calls it with junk only pollutes its own list — it can reach
     * nothing else through this object.
     */
    inner class SniffBridge {
        @android.webkit.JavascriptInterface
        fun report(url: String?, via: String?, frame: String?) {
            SniffLog.add(url ?: return, via ?: "hook", frame ?: "", false)
        }
    }

    companion object {
        const val EXTRA_URL = "url"

        private const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        private const val WRAP = ViewGroup.LayoutParams.WRAP_CONTENT
        private val GREY = 0xFF8A93A8.toInt()

        /** Mechanism → what the user reads. */
        private val VIA_LABEL = mapOf(
            "request" to "network",
            "load" to "network",
            "fetch" to "script",
            "xhr" to "script",
            "player" to "player",
            "mse" to "MSE",
            "scan" to "loaded earlier",
        )
    }
}
