package com.suravidl.app

import android.provider.MediaStore
import androidx.core.content.FileProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Files live under Android/data, which file managers refuse to open — so the
 * app hands the file itself to another app. That only works if the
 * FileProvider is wired up (manifest authority + file_paths.xml), which is
 * exactly what these tests pin down.
 */
@RunWith(AndroidJUnit4::class)
class FileHandoffTest {
    private val ctx = InstrumentationRegistry.getInstrumentation().targetContext

    @Test(timeout = 120_000)
    fun a_download_in_the_app_folder_can_be_handed_to_another_app() {
        // Downloads live under external-files-path, which is the only root the
        // provider exposes — the app-private files dir (cookie session copy,
        // jobs.db) is deliberately out of reach (v0.21.1 audit).
        val dir = File(ctx.getExternalFilesDir(null), "handoff").apply { mkdirs() }
        val f = File(dir, "handoff-test.mp4")
        f.writeBytes(ByteArray(4096) { 0x33 })
        try {
            val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", f)
            assertEquals("content", uri.scheme)
            assertTrue("provider uri should point at our file",
                       uri.toString().contains("handoff-test.mp4"))
            // the grant target (a player, the share sheet) reads it through the resolver
            val bytes = ctx.contentResolver.openInputStream(uri)!!.use { it.readBytes() }
            assertEquals(4096, bytes.size)
        } finally {
            f.delete()
        }
    }

    @Test(timeout = 120_000)
    fun private_files_are_not_shareable() {
        // the cookie-session copy and jobs.db must not be reachable through
        // the provider, whatever a page with the JS bridge asks for
        val f = File(ctx.filesDir, "handoff-private.mp4")
        f.writeBytes(ByteArray(64) { 0x66 })
        try {
            var refused = false
            try {
                FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", f)
            } catch (_: IllegalArgumentException) {
                refused = true
            }
            assertTrue("the provider must not hand out app-private files", refused)
        } finally {
            f.delete()
        }
    }

    @Test(timeout = 240_000)
    fun audio_downloads_land_in_the_music_collection() {
        val f = File(ctx.cacheDir, "tone-test.m4a")
        f.writeBytes(ByteArray(2048) { 0x44 })
        var uri: android.net.Uri? = null
        try {
            uri = MediaImporter.importToGallery(ctx, f)
            assertNotNull("audio importer returned no uri", uri)
            val resolver = ctx.contentResolver
            resolver.query(
                MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                arrayOf(MediaStore.Audio.Media._ID, MediaStore.Audio.Media.DISPLAY_NAME),
                "${MediaStore.Audio.Media.DISPLAY_NAME} = ?", arrayOf(f.name), null
            )!!.use { c ->
                assertEquals("audio file not found in MediaStore", true, c.moveToFirst())
            }
        } finally {
            f.delete()
            uri?.let { ctx.contentResolver.delete(it, null, null) }
        }
    }

    @Test(timeout = 240_000)
    fun deleting_downloads_takes_the_gallery_copies_with_them() {
        val f = File(ctx.cacheDir, "wipe-test.mp4")
        f.writeBytes(ByteArray(2048) { 0x55 })
        var uri: android.net.Uri? = null
        try {
            uri = MediaImporter.importToGallery(ctx, f)
            assertNotNull("nothing was imported", uri)

            val removed = MediaLibrary.deleteOwnCopies(ctx)
            assertTrue("expected at least our own copy to go, removed=$removed",
                       removed >= 1)

            val resolver = ctx.contentResolver
            resolver.query(
                MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                arrayOf(MediaStore.Video.Media._ID),
                "${MediaStore.Video.Media.DISPLAY_NAME} = ?", arrayOf(f.name), null
            )!!.use { c ->
                assertEquals("row should be gone after deleteOwnCopies",
                             false, c.moveToFirst())
            }
            uri = null
        } finally {
            f.delete()
            uri?.let { ctx.contentResolver.delete(it, null, null) }
        }
    }

    @Test(timeout = 240_000)
    fun deleting_one_download_takes_only_its_own_gallery_copy() {
        val keep = File(ctx.cacheDir, "keep-test.mp4")
        val drop = File(ctx.cacheDir, "drop-test.mp4")
        keep.writeBytes(ByteArray(1024) { 0x66 })
        drop.writeBytes(ByteArray(1024) { 0x77 })
        var keepUri: android.net.Uri? = null
        var dropUri: android.net.Uri? = null
        try {
            keepUri = MediaImporter.importToGallery(ctx, keep)
            dropUri = MediaImporter.importToGallery(ctx, drop)
            assertNotNull("nothing was imported", dropUri)

            val removed = MediaLibrary.deleteOwnCopiesNamed(ctx, drop.name)
            assertTrue("expected the named copy to go, removed=$removed", removed >= 1)

            val resolver = ctx.contentResolver
            fun rows(name: String): Int = resolver.query(
                MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                arrayOf(MediaStore.Video.Media._ID),
                "${MediaStore.Video.Media.DISPLAY_NAME} = ?", arrayOf(name), null
            )!!.use { c -> if (c.moveToFirst()) 1 else 0 }

            assertEquals("the deleted download's copy should be gone", 0, rows(drop.name))
            assertEquals("an untouched download's copy must stay", 1, rows(keep.name))
            dropUri = null
        } finally {
            keep.delete()
            drop.delete()
            keepUri?.let { ctx.contentResolver.delete(it, null, null) }
            dropUri?.let { ctx.contentResolver.delete(it, null, null) }
        }
    }

    @Test(timeout = 120_000)
    fun sidecars_are_not_imported_as_media() {
        val f = File(ctx.cacheDir, "tiny-test.info.json")
        f.writeText("{}")
        try {
            assertEquals(null, MediaImporter.importToGallery(ctx, f))
        } finally {
            f.delete()
        }
    }
}
