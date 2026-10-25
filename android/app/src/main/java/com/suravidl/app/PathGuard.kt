package com.suravidl.app

import java.io.File

/**
 * Where a file is, not what it is called (v0.47.14 "the seal").
 *
 * FileProvider's configured paths also cover `cache/updates` — the APK the
 * updater downloaded — so a path arriving from the page is not by itself
 * permission to hand that file to another app. The check is canonical:
 * `…/Movies/suravidl2` must not pass for `…/Movies/suravidl`, and a `..`
 * segment must not climb out.
 */
object PathGuard {

    /** True when [path] is [root] itself or below it. */
    fun inside(path: File, root: File): Boolean {
        val p = try {
            path.canonicalPath
        } catch (_: Throwable) {
            return false
        }
        val r = try {
            root.canonicalPath
        } catch (_: Throwable) {
            return false
        }
        if (r.isEmpty()) return false
        return p == r || p.startsWith(r + File.separator)
    }

    /** True when [path] sits under any of [roots]. */
    fun insideAny(path: File, roots: List<File>): Boolean = roots.any { inside(path, it) }
}
