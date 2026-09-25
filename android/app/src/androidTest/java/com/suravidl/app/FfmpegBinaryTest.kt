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

        // 2. it can read a real file (built by hand: no lavfi — this build has
        //    no avdevice — and no assets, so the test is deterministic)
        val wav = File(ctx.cacheDir, "probe-smoke.wav")
        writeWavSilence(wav)
        assertTrue("could not write the test wav", wav.length() > 1000)
        val codec = run(listOf(probe.absolutePath, "-v", "error", "-show_entries",
            "stream=codec_name", "-of", "default=nw=1:nk=1", wav.absolutePath)).trim()
        assertEquals("ffprobe read the wrong codec from a wav", "pcm_s16le", codec)
        val dur = run(listOf(probe.absolutePath, "-v", "error", "-show_entries",
            "format=duration", "-of", "default=nw=1:nk=1", wav.absolutePath)).trim()
        assertTrue("ffprobe reported a bogus duration: '$dur'",
            dur.toDoubleOrNull()?.let { it in 0.9..1.1 } == true)

        // 3. ffmpeg writes, ffprobe reads back (the pairing yt-dlp relies on)
        val ffmpeg = SuravidlApp.ffmpegBinary(ctx)
        assertTrue("libffmpeg.so missing", ffmpeg != null)
        val m4a = File(ctx.cacheDir, "probe-smoke.m4a")
        m4a.delete()
        val made = run(listOf(ffmpeg!!.absolutePath, "-v", "error", "-y",
            "-i", wav.absolutePath, "-c:a", "aac", m4a.absolutePath))
        assertTrue("ffmpeg could not convert the wav:\n$made", m4a.length() > 0)
        val m4aCodec = run(listOf(probe.absolutePath, "-v", "error", "-show_entries",
            "stream=codec_name", "-of", "default=nw=1:nk=1", m4a.absolutePath)).trim()
        assertEquals("ffprobe read the wrong codec from an ffmpeg-written file",
            "aac", m4aCodec)
        wav.delete(); m4a.delete()
        assertTrue("the engine's ffprobe is a different file",
            System.getenv("SURAVIDL_FFPROBE") == probe.absolutePath)

        // 4. yt-dlp, running in this process, resolves that same binary
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
        val py = Python.getInstance()
        val ydlClass = py.getModule("yt_dlp").get("YoutubeDL")!!
        // a Kotlin Map crosses into Python as a java.util.LinkedHashMap, and
        // yt-dlp calls params.get(key, default) — which Java maps refuse. Let
        // Python build the dict from JSON instead.
        val loc = System.getenv("SURAVIDL_FFMPEG").replace("\\", "\\\\")
        val opts = py.getModule("json").callAttr(
            "loads", """{"ffmpeg_location": "$loc", "quiet": true}""")
        val ydl = ydlClass.call(opts)
        val versions = py.getModule("yt_dlp.postprocessor.ffmpeg")
            .get("FFmpegPostProcessor")!!
            .callAttr("get_versions_and_features", ydl).asList()[0].asMap()
        val found = versions.entries.first { it.key.toString() == "ffprobe" }.value.toString()
        assertTrue("yt-dlp could not run ffprobe (got '$found')", found.isNotBlank() &&
            found != "None" && found.contains("."))
    }

    /** A 1 s / 8 kHz / mono / 16-bit PCM silence WAV, built by hand: the
     *  bundled ffmpeg has no avdevice, so `-f lavfi` is not available, and a
     *  hand-built RIFF file keeps the test free of assets. */
    private fun writeWavSilence(f: File, seconds: Int = 1, rate: Int = 8000) {
        val data = rate * seconds * 2
        f.outputStream().buffered().use { out ->
            fun le32(v: Int) = byteArrayOf(
                (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte(),
                ((v shr 16) and 0xff).toByte(), ((v shr 24) and 0xff).toByte())
            fun le16(v: Int) = byteArrayOf(
                (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte())
            out.write("RIFF".toByteArray()); out.write(le32(36 + data))
            out.write("WAVE".toByteArray())
            out.write("fmt ".toByteArray()); out.write(le32(16))
            out.write(le16(1)); out.write(le16(1))         // PCM, mono
            out.write(le32(rate)); out.write(le32(rate * 2))
            out.write(le16(2)); out.write(le16(16))        // block align, bits
            out.write("data".toByteArray()); out.write(le32(data))
            out.write(ByteArray(data))
        }
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
