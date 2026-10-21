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
     * Abandoned imports: rows this app inserted as IS_PENDING and never
     * finalized. The copy into the gallery runs in the background service;
     * when Android kills it mid-copy (screen off, app swiped, low memory) the
     * row stays pending — and AOSP keeps a pending item's bytes in a hidden
     * `.pending-<time>-<name>` file inside the target folder. File managers
     * hide dot-files, MediaStore keeps counting them: an "empty"
     * Movies/suravidl that properties say holds 18 files / 516 MB
     * (field report, 2026-10-18). Deleting the row deletes its pending file.
     */
    fun sweepPending(context: Context): Int {
        if (Build.VERSION.SDK_INT < 29) return 0
        val resolver = context.contentResolver
        val collections = listOf(
            MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
            MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
        )
        var removed = 0
        for (collection in collections) {
            val ids = mutableListOf<Long>()
            try {
                // The owner selection is the one deleteOwnCopies already
                // proves on real devices; `is_pending` is read from the
                // projection, never selected on — as a WHERE term the
                // provider rejects it on some builds and the sweep found
                // nothing at all (caught by the emulator board, 2026-10-21).
                resolver.query(
                    collection,
                    arrayOf(MediaStore.MediaColumns._ID,
                            MediaStore.MediaColumns.RELATIVE_PATH,
                            MediaStore.MediaColumns.IS_PENDING),
                    "${MediaStore.MediaColumns.OWNER_PACKAGE_NAME} = ?",
                    arrayOf(context.packageName), null
                )?.use { cursor ->
                    while (cursor.moveToNext()) {
                        if (cursor.getInt(2) != 1) continue      // finished: keep
                        val path = cursor.getString(1) ?: ""
                        if (!path.contains(FOLDER)) continue
                        ids.add(cursor.getLong(0))
                    }
                }
            } catch (_: Throwable) {
            }
            for (id in ids) {
                val uri = ContentUris.withAppendedId(collection, id)
                try {
                    resolver.delete(uri, null, null)
                } catch (_: Throwable) {
                }
                // delete() reports 0 for some pending rows even when it takes
                // them: what counts is that the row no longer answers
                val gone = try {
                    resolver.query(uri, arrayOf(MediaStore.MediaColumns._ID),
                        null, null, null)?.use { it.count == 0 } ?: true
                } catch (_: Throwable) {
                    true
                }
                if (gone) removed++
            }
        }
        return removed
    }

    /**
     * MediaStore renames collisions when it inserts ("clip.mp4" becomes
     * "clip (1).mp4"), so the copy of a download the user did twice does not
     * carry the engine's exact file name — matching only the exact name found
     * nothing and the trash button left the copy behind (v0.21.1 audit).
     *
     * MediaStore only ever appends *numbers*. The loose "stem (" + ")" match
     * used here first also accepted the user's own files — deleting a
     * download named "clip.mp4" removed "clip (Official Music Video).mp4"
     * with it (v0.21.2 audit).
     */
    private fun matchesName(actual: String?, wanted: String): Boolean {
        if (actual == null) return false
        if (actual == wanted) return true
        val dot = wanted.lastIndexOf('.')
        val stem = if (dot > 0) wanted.substring(0, dot) else wanted
        val ext = if (dot > 0) wanted.substring(dot) else ""
        val numbered = Regex(
            "^" + Regex.escape(stem) + " \\(\\d+\\)" + Regex.escape(ext) + "$")
        return numbered.matches(actual)
    }
}
