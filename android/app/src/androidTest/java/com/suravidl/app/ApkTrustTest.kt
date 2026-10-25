package com.suravidl.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * v0.47.14 "the seal": the update installer only accepts an APK signed by
 * the same key as the running app. These prove both directions on a real
 * device image — the app's own APK passes, a stranger's bytes do not.
 */
@RunWith(AndroidJUnit4::class)
class ApkTrustTest {
    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext

    @Test(timeout = 120_000)
    fun theInstalledAppPassesItsOwnSeal() {
        val self = File(ctx.applicationInfo.sourceDir)
        assertTrue("the app's own APK must be readable", self.isFile)
        assertEquals(ctx.packageName, ApkTrust.packageOf(ctx, self))
        assertTrue("its own certificate must match", ApkTrust.signedLikeSelf(ctx, self))
    }

    @Test(timeout = 120_000)
    fun aStrangerFileIsRefused() {
        val f = File(ctx.cacheDir, "not-an-update.apk")
        f.writeBytes(ByteArray(64) { 0x30 })
        try {
            assertFalse("arbitrary bytes must never pass", ApkTrust.signedLikeSelf(ctx, f))
        } finally {
            f.delete()
        }
    }
}
