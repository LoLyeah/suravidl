package com.suravidl.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * The vault's promise: at rest there is only ciphertext, and a readable copy
 * exists just for the session the engine runs in.
 */
@RunWith(AndroidJUnit4::class)
class CookieVaultTest {
    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext
    private val marker = "TESTCOOKIE_${System.currentTimeMillis()}"

    private val sample =
        "# Netscape HTTP Cookie File\n" +
        ".example.com\tTRUE\t/\tFALSE\t0\t$marker\t1\n"

    /** Any file in the app's storage that still contains the cookie in clear. */
    private fun readableCopies(): List<String> {
        val hits = mutableListOf<String>()
        ctx.filesDir.walkTopDown().forEach { f ->
            if (f.isFile && f.length() in 1..5_000_000) {
                try {
                    if (f.readText().contains(marker)) hits.add(f.name)
                } catch (_: Throwable) {
                    // binary (the encrypted blob): nothing readable in it
                }
            }
        }
        return hits
    }

    @Test(timeout = 60_000)
    fun import_leaves_only_ciphertext_until_unlocked() {
        CookieVault.delete(ctx)
        CookieVault.save(ctx, sample.toByteArray())

        assertTrue(CookieVault.has(ctx))
        assertTrue(File(ctx.filesDir, "cookies.enc").exists())
        assertFalse("plain import must not survive",
                    File(ctx.filesDir, "cookies.txt").exists())
        assertEquals("cookie readable at rest", emptyList<String>(), readableCopies())

        val session = CookieVault.unlockForSession(ctx)
        assertNotNull(session)
        assertTrue("session copy must hold the real cookies",
                   session!!.readText().contains(marker))
        assertEquals(listOf(session.name), readableCopies())

        CookieVault.lockSession(ctx)
        assertFalse(session.exists())
        assertEquals("cookie readable after lock", emptyList<String>(), readableCopies())
    }

    @Test(timeout = 60_000)
    fun delete_wipes_ciphertext_and_session() {
        CookieVault.save(ctx, sample.toByteArray())
        CookieVault.unlockForSession(ctx)
        CookieVault.delete(ctx)

        assertFalse(CookieVault.has(ctx))
        assertFalse(File(ctx.filesDir, "cookies.session.txt").exists())
        assertNull("nothing to unlock after delete", CookieVault.unlockForSession(ctx))
        assertEquals(emptyList<String>(), readableCopies())
        assertTrue(CookieVault.status(ctx).contains("no stored cookies"))
    }

    @Test(timeout = 60_000)
    fun a_plaintext_file_from_an_older_version_is_encrypted_or_removed() {
        File(ctx.filesDir, "cookies.txt").writeText(sample)
        CookieVault.migrateLegacy(ctx)

        assertFalse(File(ctx.filesDir, "cookies.txt").exists())
        assertEquals(emptyList<String>(), readableCopies())
        val session = CookieVault.unlockForSession(ctx)
        assertNotNull("migrated cookies must still work", session)
        assertTrue(session!!.readText().contains(marker))
        CookieVault.delete(ctx)
    }
}
