package com.suravidl.app

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * The REAL app path end to end: MainActivity launches the foreground
 * EngineService, Chaquopy boots the engine, and /health answers.
 * Also fails if the app recorded an uncaught exception while booting.
 *
 * Starts the activity fire-and-forget on purpose: ActivityScenario.launch()
 * blocks until the activity reaches RESUMED, which intermittently never
 * happens on API 30 emulators (flaky harness, not app code). What matters
 * here is the engine coming up via the real launch path.
 */
@RunWith(AndroidJUnit4::class)
class AppStartupTest {
    @Test(timeout = 300_000)
    fun appStartsEngineAndServesHealth() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val logs = File(ctx.getExternalFilesDir(null), "logs")
        logs.listFiles()?.forEach { it.delete() }

        val intent = Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(intent)

        var up = false
        val deadline = System.currentTimeMillis() + 120_000
        while (System.currentTimeMillis() < deadline) {
            try {
                val c = URL("http://127.0.0.1:8787/health").openConnection()
                        as HttpURLConnection
                c.connectTimeout = 2000
                if (c.responseCode == 200) {
                    up = true
                    break
                }
            } catch (_: Exception) {
            }
            Thread.sleep(1000)
        }
        assertTrue("engine never came up via the MainActivity/EngineService path", up)

        val crashFiles = logs.listFiles()?.filter { it.name.startsWith("crash-") }
            ?: emptyList()
        assertTrue(
            "app recorded uncaught exception(s): " +
                crashFiles.joinToString(" | ") { it.name },
            crashFiles.isEmpty())

        val engineErrs = logs.listFiles()?.filter { it.name.startsWith("engine-error") }
            ?: emptyList()
        assertTrue(
            "engine failed to start:\n" +
                engineErrs.joinToString("\n") { it.readText() },
            engineErrs.isEmpty())
    }
}
