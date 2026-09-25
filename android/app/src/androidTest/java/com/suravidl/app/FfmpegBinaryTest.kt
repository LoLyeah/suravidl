package com.suravidl.app

import android.system.Os
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** The bundled static ffmpeg must exist on-device and actually execute. */
@RunWith(AndroidJUnit4::class)
class FfmpegBinaryTest {

    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun bundledFfmpegRuns() {
        val f = SuravidlApp.ffmpegBinary(ctx)
        assertTrue("libffmpeg.so missing from nativeLibraryDir", f != null)
        Os.chmod(f!!.absolutePath, 0b111101101)

        val proc = ProcessBuilder(f.absolutePath, "-version")
            .redirectErrorStream(true)
            .start()
        val out = proc.inputStream.bufferedReader().readText()
        val code = proc.waitFor()
        assertEquals("ffmpeg -version exited $code; output:\n$out", 0, code)
        assertTrue("not an ffmpeg build:\n$out", out.contains("ffmpeg version"))
    }

    @Test
    fun engineEnvPointsAtBundledFfmpeg() {
        // exported by SuravidlApp.onCreate; the engine reads it for yt-dlp
        val path = System.getenv("SURAVIDL_FFMPEG")
        assertTrue("SURAVIDL_FFMPEG not set", path != null)
        assertTrue("SURAVIDL_FFMPEG does not exist: $path", File(path!!).exists())
    }
}
