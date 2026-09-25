package com.suravidl.app

import android.net.Uri
import android.provider.MediaStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Completed downloads must be visible in the system gallery (MediaStore). */
@RunWith(AndroidJUnit4::class)
class MediaImporterTest {
    @Test(timeout = 240_000)
    fun completedFileAppearsInMediaStore() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val f = File(ctx.cacheDir, "tiny-m5-test.mp4")
        f.writeBytes(ByteArray(2048) { 0x55 })
        var uri: android.net.Uri? = null
        try {
            uri = MediaImporter.importToGallery(ctx, f)
            assertNotNull("importer returned no uri", uri)

            val resolver = ctx.contentResolver
            resolver.query(
                MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                arrayOf(MediaStore.Video.Media._ID, MediaStore.Video.Media.SIZE),
                "${MediaStore.Video.Media.DISPLAY_NAME} = ?", arrayOf(f.name), null
            )!!.use { c ->
                assertEquals("file not found in MediaStore", true, c.moveToFirst())
                assertEquals(2048L, c.getLong(1))
            }
        } finally {
            f.delete()
            uri?.let { ctx.contentResolver.delete(it, null, null) }
        }
    }
}