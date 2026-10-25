package com.suravidl.app

/**
 * The bounce policy for the in-app browser, and the worst of the ad networks
 * it refuses to load at all (v0.39.7).
 *
 * This browser exists to hold ONE page while its streams are found. Ad-fed
 * pages break that promise two ways: a full-page redirect to an ad site, and
 * a pop-up window. Either one replaces the page and wipes the find list
 * mid-hunt — the live report was a list that filled for a fraction of a
 * second and was gone.
 *
 * The rule here is deliberately blunt: a top-level hop to another site is
 * refused — refused, named on screen, and one tap from being followed anyway
 * (the user keeps the last word). Same-site hops and sub-frames pass: that is
 * ordinary site behavior, and a sub-frame cannot replace the page.
 *
 * Pure strings in, verdicts out: `android.net.Uri` is unavailable in JVM unit
 * tests, so this file touches nothing from `android.*`.
 */
object NavGuard {

    /** The host of an http(s) URL, lowercased, port and userinfo stripped.
     *  Null for anything that is not a web address. */
    fun host(url: String?): String? {
        if (url == null) return null
        val schemeAt = url.indexOf("://")
        if (schemeAt < 0) return null
        val scheme = url.substring(0, schemeAt).lowercase()
        if (scheme != "http" && scheme != "https") return null
        var rest = url.substring(schemeAt + 3)
        // Browsers strip tab/CR/LF anywhere and read `\` as `/` before they
        // resolve a URL: `https://evil.com\sub.trusted.com/x` navigates to
        // evil.com. The v0.39.7 scan treated the backslash as an ordinary
        // character and named `sub.trusted.com` — so the hop passed the
        // off-site check and the page was replaced anyway (v0.43.2 audit).
        // Resolve those characters the way the browser will, then scan.
        rest = rest.replace("\t", "").replace("\r", "").replace("\n", "")
        val cut = rest.indexOfFirst {
            it == '/' || it == '?' || it == '#' || it == '\\' || it == ' '
        }
        if (cut >= 0) rest = rest.substring(0, cut)
        val at = rest.lastIndexOf('@')            // userinfo is not the host
        if (at >= 0) rest = rest.substring(at + 1)
        val colon = rest.lastIndexOf(':')
        if (colon >= 0) rest = rest.substring(0, colon)
        rest = rest.lowercase().trim()
        return if (rest.isEmpty()) null else rest
    }

    /**
     * Suffixes that own their own subdomain space, so the site is three
     * labels, not two. Without this, `video.co.uk` and `ads.co.uk` both
     * collapse to `co.uk` and every hop between them looked like a
     * same-site hop (v0.47.14 "the seal" — the audit's V-01).
     *
     * Deliberately not the whole Public Suffix List: it is a few hundred
     * kilobytes, and this file only needs the shapes that appear in ad and
     * pop-under hops. A missing entry does not open a hole — it just keeps
     * the old, coarser behaviour for that suffix.
     */
    private val MULTI_PART = setOf(
        "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "net.uk", "sch.uk",
        "com.au", "net.au", "org.au", "edu.au", "gov.au", "id.au",
        "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
        "com.br", "net.br", "org.br", "gov.br",
        "co.nz", "net.nz", "org.nz", "govt.nz",
        "co.za", "org.za", "co.in", "net.in", "org.in",
        "co.kr", "or.kr", "com.tr", "com.mx", "com.ar", "com.co",
        "com.cn", "net.cn", "org.cn", "com.hk", "com.tw", "com.sg",
        "com.my", "co.id", "or.id", "web.id", "co.th", "in.th",
        "com.ph", "com.vn", "co.il", "com.sa", "com.eg", "com.pk",
        // private suffixes: two users' spaces are two different sites
        "github.io", "githubusercontent.com", "pages.dev", "workers.dev",
        "netlify.app", "vercel.app", "herokuapp.com", "blogspot.com",
        "wordpress.com", "tumblr.com", "cloudfront.net", "amazonaws.com",
        "azurewebsites.net", "appspot.com", "firebaseapp.com",
    )

    /** The registrable-ish site: the last two labels of the host, or three
     *  where the last two are a suffix that hosts sites beneath itself. */
    fun siteKey(url: String?): String {
        val h = host(url) ?: return ""
        val parts = h.split('.').filter { it.isNotEmpty() }
        if (parts.size <= 2) return parts.joinToString(".")
        val lastTwo = parts.takeLast(2).joinToString(".")
        val take = if (lastTwo in MULTI_PART) 3 else 2
        return parts.takeLast(take).joinToString(".")
    }

    fun sameSite(a: String?, b: String?): Boolean {
        val ka = siteKey(a)
        return ka.isNotEmpty() && ka == siteKey(b)
    }

    /** Null = let it load. Non-null = a short reason, for the note on screen. */
    fun blockReason(current: String?, target: String): String? {
        if (host(target) == null) return "not a web page"
        if (siteKey(current).isEmpty()) return null     // nothing to protect yet
        if (sameSite(current, target)) return null
        return "off-site hop"
    }
}

/**
 * The short deny list: hosts that exist to serve ads, blocked before they
 * load. Deliberately small and unambitious — these are the pop-up farms that
 * plague streaming pages; anything subtler is [NavGuard]'s job, not a
 * whack-a-mole list's.
 */
object AdHosts {
    private val DENY = listOf(
        "doubleclick.net",
        "googlesyndication.com",
        "googleadservices.com",
        "popads.net",
        "popcash.net",
        "propellerads.com",
        "onclickads.net",
        "adsterra.com",
        "clickadu.com",
        "clickadu.net",
        "exoclick.com",
        "realsrv.com",
        "tsyndicate.com",
        "juicyads.com",
        "trafficjunky.net",
        "adnium.com",
        "adcash.com",
        "hilltopads.net",
        "monetag.com",
        "admaven.com",
        "adspyglass.com",
    )

    /** Suffix match on the host: `cdn.popads.net` is blocked, `notpopads.net`
     *  is not.
     *
     *  `enabled` is the truce switch (v0.39.8): a page that notices its ad
     *  networks being served empty can refuse to run — the user's report was
     *  exactly that worry. The browser passes the current setting in; the
     *  list itself stays pure. */
    fun blocked(url: String, enabled: Boolean = true): Boolean {
        if (!enabled) return false
        val h = NavGuard.host(url) ?: return false
        return DENY.any { h == it || h.endsWith(".$it") }
    }
}
