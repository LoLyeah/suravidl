package com.suravidl.app

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File

/**
 * Puts finished downloads where the user can open them.
 *
 * The engine works in the app's own folder (Android/data/…), which no file
 * manager will show on Android 11+. Importing into MediaStore gives the user
 * a copy the Gallery/Files/Music apps can actually open — video under
 * Movies/suravidl, audio under Music/suravidl. Sidecars (.json/.srt/.vtt)
 * stay in the app folder on purpose.
 */
object MediaImporter {
    fun importToGallery(context: Context, file: File): Uri? {
        if (Build.VERSION.SDK_INT < 29) return null  // pre-scoped storage: skip
        val audio = file.extension.lowercase() in AUDIO_EXT
        val video = file.extension.lowercase() in VIDEO_EXT
        if (!audio && !video) return null
        val resolver = context.contentResolver
        val relative = if (audio) Environment.DIRECTORY_MUSIC + "/suravidl"
                       else Environment.DIRECTORY_MOVIES + "/suravidl"
        val collection = if (audio) {
            MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        } else {
            MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        }
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, file.name)
            put(MediaStore.MediaColumns.MIME_TYPE, if (audio) audioMime(file) else videoMime(file))
            put(MediaStore.MediaColumns.RELATIVE_PATH, relative)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri = resolver.insert(collection, values) ?: return null
        try {
            resolver.openOutputStream(uri)!!.use { out ->
                file.inputStream().use { it.copyTo(out) }
            }
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            throw e
        }
        val published = resolver.update(uri, ContentValues().apply {
            put(MediaStore.MediaColumns.IS_PENDING, 0)
        }, null, null)
        if (published <= 0) {
            // a row left on IS_PENDING is invisible in the gallery while it
            // still occupies disk: publish or take it back (v0.21.1 audit)
            resolver.delete(uri, null, null)
            throw IOException("could not publish ${file.name} to MediaStore")
        }
        return uri
    }

    private fun audioMime(file: File): String = when (file.extension.lowercase()) {
        "m4a" -> "audio/mp4"
        "mp3" -> "audio/mpeg"
        "opus", "ogg" -> "audio/ogg"
        "wav" -> "audio/wav"
        "aac" -> "audio/aac"
        "flac" -> "audio/flac"
        else -> "audio/*"
    }

    private fun videoMime(file: File): String = when (file.extension.lowercase()) {
        "webm" -> "video/webm"
        "mkv" -> "video/x-matroska"
        "mov" -> "video/quicktime"
        "3gp" -> "video/3gpp"
        else -> "video/mp4"
    }

    private val AUDIO_EXT = setOf("m4a", "mp3", "opus", "ogg", "wav", "aac", "flac")
    private val VIDEO_EXT = setOf("mp4", "webm", "mkv", "mov", "3gp")
}
