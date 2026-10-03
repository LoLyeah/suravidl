package com.suravidl.app

/**
 * v0.40.3 "the wide view" — the WebView's own user-agent, re-spelled as a
 * desktop Chrome for the "desktop site" switch. The Chrome version rides
 * along from the WebView's UA, so a site sees one coherent browser (an old
 * version number bolted onto a modern engine is its own smell). Pure
 * strings: JVM-testable, no Android framework.
 */
object DesktopUa {
    private val CHROME = Regex("Chrome/([\\d.]+)")

    /** The fallback only speaks when the WebView's UA has no Chrome token at
     *  all — some WebViews spell themselves oddly; a desktop face with a
     *  clean version still beats a phone face. */
    fun of(ua: String, fallbackVersion: String = "120.0.0.0"): String {
        val version = CHROME.find(ua)?.groupValues?.get(1) ?: fallbackVersion
        return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/" + version + " Safari/537.36"
    }
}
