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

/** The real engine, running on-device, downloading over HTTP. */
@RunWith(AndroidJUnit4::class)
class EngineDownloadTest {
    @Test(timeout = 240_000)
    fun engineDownloadsOverHttp() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
        val py = Python.getInstance()

        // the bundled engine must import on Android
        val jobs = py.getModule("suravidl_engine.jobs")
        val dir = File(ctx.getExternalFilesDir(null), "test_dl").apply { mkdirs() }
        val mgr = jobs.callAttr("JobManager", dir.absolutePath)

        val job = mgr.callAttr("create", "http://10.0.2.2:8801/tiny.mp4")
        val id = job.callAttr("__getitem__", "id").toString()

        var status = ""
        for (i in 1..60) {
            val j = mgr.callAttr("get", id)
            status = j.callAttr("__getitem__", "status").toString()
            if (status == "completed") break
            if (status == "error") {
                throw AssertionError(
                    "engine job errored: " + j.callAttr("__getitem__", "error"))
            }
            Thread.sleep(1000)
        }
        assertEquals("completed", status)

        val f = File(dir, "tiny.mp4")
        assertTrue("downloaded file missing or empty: $f", f.exists() && f.length() > 1000)
    }
}