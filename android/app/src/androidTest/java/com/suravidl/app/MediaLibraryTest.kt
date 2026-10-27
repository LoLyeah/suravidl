package com.suravidl.app

import android.content.ContentUris
import android.content.ContentValues
import android.os.Environment
import android.provider.MediaStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * v0.47.9 "the ghost": an import that was killed mid-copy leaves an
 * IS_PENDING row plus a hidden `.pending-*` file — invisible to every file
 * manager, still counted (18 items / 516 MB on an "empty" folder). The sweep
 * must take exactly those, and nothing that finished properly.
 */
@RunWith(AndroidJUnit4::class)
class MediaLibraryTest {
    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext
    private val collection get() = MediaStore.Video.Media
        .getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)

    private fun pendingUri(name: String): android.net.Uri {
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
            put(MediaStore.MediaColumns.RELATIVE_PATH,
                Environment.DIRECTORY_MOVIES + "/suravidl")
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri = ctx.contentResolver.insert(collection, values)!!
        // a pending item only exists while bytes are being written
        ctx.contentResolver.openOutputStream(uri)!!.use { it.write(ByteArray(1024) { 0x55 }) }
        return uri
    }

    private fun exists(uri: android.net.Uri): Boolean =
        ctx.contentResolver.query(uri, arrayOf(MediaStore.MediaColumns._ID),
            null, null, null)?.use { it.count > 0 } ?: false

    @Test(timeout = 240_000)
    fun anAbandonedPendingImportIsSwept() {
        val ghost = pendingUri("ghost-pending-test.mp4")
        try {
            assertTrue("the pending row must exist first", exists(ghost))
            val swept = MediaLibrary.sweepPending(ctx)
            assertTrue("the sweep must take it (${MediaLibrary.lastSweepError ?: "no error"})",
                swept >= 1)
            assertEquals("the row (and its .pending file) must be gone",
                false, exists(ghost))
        } finally {
            runCatching { ctx.contentResolver.delete(ghost, null, null) }
        }
    }

    @Test(timeout = 240_000)
    fun aProperlyPublishedImportSurvivesTheSweep() {
        val f = File(ctx.cacheDir, "ghost-survivor-test.mp4")
        f.writeBytes(ByteArray(2048) { 0x56 })
        var uri: android.net.Uri? = null
        try {
            uri = MediaImporter.importToGallery(ctx, f)
            assertTrue("the importer must publish it", uri != null)
            MediaLibrary.sweepPending(ctx)
            assertTrue("a finished copy is not a ghost", exists(uri!!))
        } finally {
            f.delete()
            uri?.let { ctx.contentResolver.delete(it, null, null) }
        }
    }

    /**
     * v0.47.18 "the twin": two downloads can carry the same display name
     * (MediaStore numbers the second). Trashing one row must take exactly the
     * copy that row made — deleting by name took both.
     */
    @Test(timeout = 240_000)
    fun aSameNamedTwinSurvivesDeletingOneJob() {
        val dirA = File(ctx.cacheDir, "twin-a").apply { mkdirs() }
        val dirB = File(ctx.cacheDir, "twin-b").apply { mkdirs() }
        val a = File(dirA, "twin-test.mp4").apply { writeBytes(ByteArray(2048) { 0x11 }) }
        val b = File(dirB, "twin-test.mp4").apply { writeBytes(ByteArray(2048) { 0x22 }) }
        val uriA = MediaImporter.importToGallery(ctx, a)
        val uriB = MediaImporter.importToGallery(ctx, b)
        assertTrue("both copies must land", uriA != null && uriB != null)
        try {
            MediaLibrary.rememberCopy(ctx, "job-a", uriA!!)
            MediaLibrary.rememberCopy(ctx, "job-b", uriB!!)
            assertEquals("exactly one row must go", 1,
                MediaLibrary.deleteOwnCopiesForJob(ctx, "job-a"))
            assertFalse("the trashed job's copy is gone", exists(uriA))
            assertTrue("its same-named twin must stay", exists(uriB))
        } finally {
            runCatching { ctx.contentResolver.delete(uriA!!, null, null) }
            runCatching { ctx.contentResolver.delete(uriB!!, null, null) }
            MediaLibrary.deleteOwnCopiesForJob(ctx, "job-b")
            a.delete()
            b.delete()
        }
    }
}
