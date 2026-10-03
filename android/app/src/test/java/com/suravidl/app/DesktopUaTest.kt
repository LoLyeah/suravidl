package com.suravidl.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The desktop spell, on the JVM: pure strings in, a UA out (v0.40.3). */
class DesktopUaTest {

    private val webviewUa =
        "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230805.001; wv) " +
            "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 " +
            "Chrome/119.0.6045.66 Mobile Safari/537.36"

    @Test
    fun anAndroidUaIsRespelledAsADesktopChrome() {
        val out = DesktopUa.of(webviewUa)
        assertTrue(out.contains("X11; Linux x86_64"))
        assertTrue(out.contains("Chrome/119.0.6045.66"))
        assertFalse(out.contains("Mobile"))
        assertFalse(out.contains("wv"))
        assertFalse(out.contains("Android"))
        assertFalse(out.contains("Version/4.0"))
    }

    @Test
    fun aUaWithoutAChromeTokenStillYieldsADesktopFace() {
        val out = DesktopUa.of("Mozilla/5.0 (Linux; Android 10)")
        assertTrue(out.contains("Chrome/120.0.0.0"))
        assertTrue(out.contains("X11; Linux x86_64"))
    }

    @Test
    fun aDesktopUaPassesThroughUnchanged() {
        val desktop =
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        assertEquals(desktop, DesktopUa.of(desktop))
    }
}
