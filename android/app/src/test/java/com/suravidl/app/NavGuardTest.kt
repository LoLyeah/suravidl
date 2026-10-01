package com.suravidl.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The bounce policy, on the JVM: pure strings in, verdicts out (v0.39.7). */
class NavGuardTest {

    @Test
    fun sameSiteAndSubdomainHopsPass() {
        assertNull(
            NavGuard.blockReason(
                "https://video.example.com/v/zzz",
                "https://video.example.com/e/zzz"
            )
        )
        assertNull(
            NavGuard.blockReason(
                "https://video.example.com/v/zzz",
                "https://www.video.example.com/watch"
            )
        )
    }

    @Test
    fun offSiteHopsAreRefused() {
        assertNotNull(
            NavGuard.blockReason(
                "https://video.example.com/v/zzz",
                "https://ads.example.net/?x=1"
            )
        )
    }

    @Test
    fun theFirstLoadHasNothingToProtectYet() {
        assertNull(NavGuard.blockReason(null, "https://video.example.com/v/zzz"))
        assertNull(NavGuard.blockReason("", "https://video.example.com/v/zzz"))
    }

    @Test
    fun nonWebTargetsAreNotPages() {
        assertEquals("not a web page", NavGuard.blockReason(null, "mailto:x@example.com"))
        assertEquals("not a web page", NavGuard.blockReason("https://a.example", "intent://x"))
    }

    @Test
    fun siteKeysIgnorePortsPathsUserinfoAndCase() {
        assertEquals("example.com", NavGuard.siteKey("https://A.B.Example.COM:8080/x?q=1"))
        assertEquals("example.com", NavGuard.siteKey("http://example.com"))
        assertEquals("video.example.com", NavGuard.host("https://user:pass@video.example.com/x"))
        assertEquals("", NavGuard.siteKey("not a url"))
    }

    @Test
    fun classicAdHostsAreBlockedBySuffix() {
        assertTrue(AdHosts.blocked("https://cdn.popads.net/pop.js"))
        assertTrue(AdHosts.blocked("https://a.b.doubleclick.net/x"))
        assertFalse(AdHosts.blocked("https://video.example.com/stream.mp4"))
        assertFalse(AdHosts.blocked("not a url"))
    }
}
