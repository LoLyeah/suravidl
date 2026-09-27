package com.suravidl.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * The logs dir used to grow for ever: one timestamped file per crash or
 * engine failure, kept in the user-visible Android/media folder too, plus a
 * share-detail log appended per shared link. Both are bounded now (v0.24.9).
 */
@RunWith(AndroidJUnit4::class)
class LogStoreTest {

    private val ctx get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun privateLogs(): File =
        File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "logs").apply { mkdirs() }

    @Test
    fun pruneKeepsTheNewestAndNeverTouchesFixedNames() {
        val dir = privateLogs()
        // clean any leftovers from an earlier run of this test
        dir.listFiles()?.forEach { if (it.name.startsWith("crash-100000")) it.delete() }

        // seeded directly, not via LogStore.write: prune is the thing under
        // test, and direct writes keep its input exactly what we chose
        val mine = (1..14).map { i ->
            File(dir, "crash-10000${i.toString().padStart(2, '0')}.txt")
                .apply { writeText("seed $i") }
        }
        val appended = File(dir, "share-detail.log")
            .apply { appendText("shared link: x\n") }

        LogStore.prune(ctx, keep = 3)

        assertFalse("the oldest must go", mine[0].exists())
        assertFalse("everything past the newest 3 must go", mine[10].exists())
        assertTrue("the newest 3 stay", mine[11].exists() && mine[13].exists())
        assertTrue("appended logs are not timestamped and are never pruned",
                   appended.exists())
        // deliberately no total-count assertion: another test's engine may be
        // writing real logs concurrently, and prune only ever deletes
    }

    @Test
    fun appendBoundedKeepsTheFileUnderItsCap() {
        val f = File(ctx.cacheDir, "append-bounded-test.log").apply { delete() }
        repeat(200) { LogStore.appendBounded(f, "line $it\n", maxBytes = 1000) }
        assertTrue("must stay bounded, was ${f.length()} bytes", f.length() <= 1000)
        assertTrue("the newest line must survive", f.readText().contains("line 199"))
    }
}
