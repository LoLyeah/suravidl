package com.suravidl.app

import android.content.ContentUris
import android.content.Context
import android.os.Build
import android.provider.MediaStore

/**
 * The copies this app contributed to the system library (Gallery → Movies/
 * suravidl, Music → Music/suravidl).
 *
 * They exist so the user can actually open a download (the real file lives in
 * Android/data, which file managers refuse to browse). "Delete downloaded
 * files" must therefore remove these too — and an app may only delete rows it
 * owns, which is exactly what this does.
 */
object MediaLibrary {
    private const val FOLDER = "suravidl"

    fun deleteOwnCopies(context: Context): Int = deleteOwnCopiesNamed(context, null)

    /**
     * Delete the library copies this app made. `name` limits it to one
     * download (the trash button on a single row); null wipes them all —
     * a blank name does not, so a bridge call with a missing argument can
     * never erase the whole library (v0.21.1 audit).
     */
    fun deleteOwnCopiesNamed(context: Context, name: String?): Int {
        if (Build.VERSION.SDK_INT < 29) return 0
        if (name != null && name.isBlank()) return 0
        val resolver = context.contentResolver
        val collections = listOf(
            MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
            MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
        )
        var removed = 0
        for (collection in collections) {
            try {
                resolver.query(
                    collection,
                    arrayOf(MediaStore.MediaColumns._ID,
                            MediaStore.MediaColumns.RELATIVE_PATH,
                            MediaStore.MediaColumns.DISPLAY_NAME),
                    "${MediaStore.MediaColumns.OWNER_PACKAGE_NAME} = ?",
                    arrayOf(context.packageName), null
                )?.use { cursor ->
                    while (cursor.moveToNext()) {
                        val path = cursor.getString(1) ?: ""
                        if (!path.contains(FOLDER)) continue
                        if (name != null && !matchesName(cursor.getString(2), name)) continue
                        val uri = ContentUris.withAppendedId(collection, cursor.getLong(0))
                        try {
                            if (resolver.delete(uri, null, null) > 0) removed++
                        } catch (_: Throwable) {
                        }
                    }
                }
            } catch (_: Throwable) {
            }
        }
        return removed
    }

    /**
     * MediaStore renames collisions when it inserts ("clip.mp4" becomes
     * "clip (1).mp4"), so the copy of a download the user did twice does not
     * carry the engine's exact file name — matching only the exact name found
     * nothing and the trash button left the copy behind (v0.21.1 audit).
     */
    private fun matchesName(actual: String?, wanted: String): Boolean {
        if (actual == null) return false
        if (actual == wanted) return true
        val dot = wanted.lastIndexOf('.')
        val stem = if (dot > 0) wanted.substring(0, dot) else wanted
        val ext = if (dot > 0) wanted.substring(dot) else ""
        return actual.startsWith("$stem (") && actual.endsWith(")$ext")
    }
}
