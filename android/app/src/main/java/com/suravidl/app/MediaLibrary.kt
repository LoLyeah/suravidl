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

    fun deleteOwnCopies(context: Context): Int {
        if (Build.VERSION.SDK_INT < 29) return 0
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
                            MediaStore.MediaColumns.RELATIVE_PATH),
                    "${MediaStore.MediaColumns.OWNER_PACKAGE_NAME} = ?",
                    arrayOf(context.packageName), null
                )?.use { cursor ->
                    while (cursor.moveToNext()) {
                        val path = cursor.getString(1) ?: ""
                        if (!path.contains(FOLDER)) continue
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
}
