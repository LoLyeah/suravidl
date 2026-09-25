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
        val f = File(ctx.filesDir, "handoff-test.mp4")
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
