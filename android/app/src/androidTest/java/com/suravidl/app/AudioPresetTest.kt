package com.suravidl.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * End-to-end on-device proof of the audio-only feature: the real engine
 * downloads a fixture and converts it to MP3 using the APK's bundled ffmpeg.
 */
@RunWith(AndroidJUnit4::class)
class AudioPresetTest {

    @Test
    fun mp3PresetConvertsUsingBundledFfmpeg() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
        val py = Python.getInstance()

        val jobs = py.getModule("suravidl_engine.jobs")
        val dir = File(ctx.getExternalFilesDir(null), "test_audio").apply { mkdirs() }
        val mgr = jobs.callAttr("JobManager", dir.absolutePath)

        // positional: create(url, fmt, extra_headers, preset)
        val job = mgr.callAttr("create", "http://10.0.2.2:8801/tone.m4a",
            null, null, "audio-mp3")
        val id = job.callAttr("__getitem__", "id").toString()

        var status = ""
        var error = ""
        for (i in 1..90) {
            val j = mgr.callAttr("get", id)
            status = j.callAttr("__getitem__", "status").toString()
            if (status == "completed") break
            if (status == "error") {
                error = j.callAttr("__getitem__", "error").toString()
                break
            }
            Thread.sleep(1000)
        }
        assertEquals("engine error: $error", "completed", status)

        val f = File(dir, "tone.mp3")
        assertTrue("converted mp3 missing: $f", f.exists())
        assertTrue("converted mp3 too small: ${f.length()}", f.length() > 1000)
        val head = f.readBytes().take(3)
        val isMp3 = (head.size == 3 && head[0] == 0xFF.toByte() &&
            (head[1].toInt() and 0xE0) == 0xE0) ||
            String(head.toByteArray(), Charsets.ISO_8859_1) == "ID3"
        assertTrue("not an mp3 header: $head", isMp3)
    }
}
