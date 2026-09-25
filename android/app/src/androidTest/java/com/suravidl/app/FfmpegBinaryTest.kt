package com.suravidl.app

import android.system.Os
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.TimeUnit

/** The bundled static ffmpeg must exist on-device and actually execute. */
@RunWith(AndroidJUnit4::class)
class FfmpegBinaryTest {

    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext

    @Test(timeout = 60_000)
    fun bundledFfmpegRuns() {
        val f = SuravidlApp.ffmpegBinary(ctx)
        assertTrue("libffmpeg.so missing from nativeLibraryDir", f != null)
        if (!f!!.canExecute()) {
            try {
                Os.chmod(f.absolutePath, 0b111101101)
            } catch (_: Throwable) {
                // extraction normally sets 0755; EACCES here is not fatal
            }
        }
        assertTrue("libffmpeg.so is not executable", f.canExecute())

        val proc = ProcessBuilder(f.absolutePath, "-version")
            .redirectErrorStream(true)
            .start()
        val finished = proc.waitFor(30, TimeUnit.SECONDS)
        if (!finished) {
            proc.destroyForcibly()
            fail("ffmpeg -version did not finish within 30s")
        }
        val out = proc.inputStream.bufferedReader().readText()
        assertEquals("ffmpeg -version exited ${proc.exitValue()}; output:\n$out",
            0, proc.exitValue())
        assertTrue("not an ffmpeg build:\n$out", out.contains("ffmpeg version"))
    }

    @Test(timeout = 30_000)
    fun engineEnvPointsAtBundledFfmpeg() {
        // exported by SuravidlApp.onCreate; the engine reads it for yt-dlp
        val path = System.getenv("SURAVIDL_FFMPEG")
        assertTrue("SURAVIDL_FFMPEG not set", path != null)
        assertTrue("SURAVIDL_FFMPEG does not exist: $path", File(path!!).exists())
        val probe = System.getenv("SURAVIDL_FFPROBE")
        assertTrue("SURAVIDL_FFPROBE not set", probe != null)
        assertTrue("SURAVIDL_FFPROBE does not exist: $probe", File(probe!!).exists())
    }

    /**
     * ffprobe has to work on-device twice over: as a binary, and as the
     * program yt-dlp resolves from the ffmpeg path it was handed.
     */
    @Test(timeout = 120_000)
    fun bundledFfprobeRunsAndYtDlpFindsIt() {
        val probe = SuravidlApp.ffprobeBinary(ctx)
        assertTrue("libffprobe.so missing from nativeLibraryDir", probe != null)
        if (!probe!!.canExecute()) {
            try {
                Os.chmod(probe.absolutePath, 0b111101101)
            } catch (_: Throwable) {
                // as with ffmpeg: extraction normally sets 0755
            }
        }
        assertTrue("libffprobe.so is not executable", probe.canExecute())

        // 1. it is really an ffprobe build
        val version = run(listOf(probe.absolutePath, "-version"))
        assertTrue("not an ffprobe build:\n$version", version.contains("ffprobe version"))

        // 2. it can read a file the bundled ffmpeg just wrote
        val ffmpeg = SuravidlApp.ffmpegBinary(ctx)
        assertTrue("libffmpeg.so missing", ffmpeg != null)
        val smoke = File(ctx.cacheDir, "probe-smoke.m4a")
        smoke.delete()
        val made = run(listOf(ffmpeg!!.absolutePath, "-v", "error", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=8000:cl=mono", "-t", "1", "-c:a", "aac", smoke.absolutePath))
        assertTrue("ffmpeg wrote no file:\n$made", smoke.length() > 0)
        val codec = run(listOf(probe.absolutePath, "-v", "error", "-show_entries",
            "stream=codec_name", "-of", "default=nw=1:nk=1", smoke.absolutePath)).trim()
        assertEquals("ffprobe read the wrong codec from an ffmpeg-written file",
            "aac", codec)
        smoke.delete()
        assertTrue("the engine's ffprobe is a different file",
            System.getenv("SURAVIDL_FFPROBE") == probe.absolutePath)

        // 3. yt-dlp, running in this process, resolves that same binary
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
        val py = Python.getInstance()
        val ydlClass = py.getModule("yt_dlp").get("YoutubeDL")
        val ydl = ydlClass.call(mapOf(
            "ffmpeg_location" to System.getenv("SURAVIDL_FFMPEG"),
            "quiet" to true))
        val versions = py.getModule("yt_dlp.postprocessor.ffmpeg")
            .get("FFmpegPostProcessor")
            .callAttr("get_versions_and_features", ydl).asList()[0].asMap()
        val found = versions.entries.first { it.key.toString() == "ffprobe" }.value.toString()
        assertTrue("yt-dlp could not run ffprobe (got '$found')", found.isNotBlank() &&
            found != "None" && found.contains("."))
    }

    private fun run(argv: List<String>): String {
        val proc = ProcessBuilder(argv).redirectErrorStream(true).start()
        val finished = proc.waitFor(60, TimeUnit.SECONDS)
        if (!finished) {
            proc.destroyForcibly()
            fail("${argv.first()} did not finish within 60s")
        }
        return proc.inputStream.bufferedReader().readText()
    }
}
