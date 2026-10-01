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
        val cut = rest.indexOfFirst { it == '/' || it == '?' || it == '#' }
        if (cut >= 0) rest = rest.substring(0, cut)
        val at = rest.lastIndexOf('@')            // userinfo is not the host
        if (at >= 0) rest = rest.substring(at + 1)
        val colon = rest.lastIndexOf(':')
        if (colon >= 0) rest = rest.substring(0, colon)
        rest = rest.lowercase().trim()
        return if (rest.isEmpty()) null else rest
    }

    /** The registrable-ish site: the last two labels of the host. Not a
     *  Public-Suffix-List implementation on purpose — a hop from a video page
     *  to *.some-ad.net is a hop off the page, and that is all this maps. */
    fun siteKey(url: String?): String {
        val h = host(url) ?: return ""
        val parts = h.split('.').filter { it.isNotEmpty() }
        if (parts.size <= 2) return parts.joinToString(".")
        return parts.takeLast(2).joinToString(".")
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
     *  is not. */
    fun blocked(url: String): Boolean {
        val h = NavGuard.host(url) ?: return false
        return DENY.any { h == it || h.endsWith(".$it") }
    }
}
