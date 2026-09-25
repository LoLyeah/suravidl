package com.suravidl.app

import android.app.Application
import android.content.Context
import android.os.Build
import android.os.Environment
import android.system.Os
import android.util.Log
import java.io.File

/**
 * Log storage that is actually reachable by the user: files land in
 * Android/media/<pkg>/logs/ (readable by any file manager, no permissions)
 * with a copy in the app-private external dir for tests.
 */
object LogStore {
    fun mediaDir(ctx: Context): File? {
        if (Build.VERSION.SDK_INT < 29) return null
        val dir = File(Environment.getExternalStorageDirectory(),
                       "Android/media/${ctx.packageName}/logs")
        dir.mkdirs()
        return dir
    }

    fun write(ctx: Context, name: String, text: String) {
        try {
            mediaDir(ctx)?.let { File(it, name).writeText(text) }
        } catch (_: Throwable) {
        }
        try {
            val alt = File(ctx.getExternalFilesDir(null), "logs").apply { mkdirs() }
            File(alt, name).writeText(text)
        } catch (_: Throwable) {
        }
    }

    /** Most recent crash/engine logs, newest first, concatenated (bounded). */
    fun readAll(ctx: Context, limit: Int = 3): String {
        val dir = mediaDir(ctx) ?: File(ctx.getExternalFilesDir(null), "logs")
        val files = dir.listFiles()
            ?.filter { it.name.startsWith("crash-") || it.name.startsWith("engine-error") }
            ?.sortedByDescending { it.name }
            ?.take(limit)
            ?: return ""
        return files.joinToString("\n\n") { f ->
            "== ${f.name} ==\n" + f.readText().take(4000)
        }
    }
}

/**
 * Installs an uncaught-exception handler that saves the stack trace before
 * the process dies — the only crash evidence available without a computer.
 */
class SuravidlApp : Application() {
    override fun onCreate() {
        super.onCreate()
        setupFfmpeg()
        val prev = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            Log.e(TAG, "uncaught exception on thread ${t.name}", e)
            try {
                LogStore.write(
                    this,
                    "crash-${System.currentTimeMillis()}.txt",
                    "version=${BuildConfig.VERSION_NAME}\n" +
                        "thread=${t.name}\n" +
                        e.stackTraceToString()
                )
            } catch (_: Throwable) {
                // never make the crash handler itself the problem
            }
            prev?.uncaughtException(t, e)
        }
    }

    /**
     * The APK bundles a static ffmpeg + ffprobe as jniLibs (libffmpeg.so,
     * libffprobe.so). Files extracted into nativeLibraryDir are the one place
     * Android allows us to exec from, so export both for the engine. yt-dlp
     * resolves ffprobe from the ffmpeg path it is given (it substitutes the
     * program name), which is why the sibling file is enough.
     */
    private fun setupFfmpeg() {
        val f = ffmpegBinary(this)
        if (f == null) {
            Log.w(TAG, "bundled ffmpeg missing from nativeLibraryDir")
        } else {
            makeExecutable(f, "ffmpeg")
            try {
                Os.setenv("SURAVIDL_FFMPEG", f.absolutePath, true)
                Log.i(TAG, "bundled ffmpeg: ${f.absolutePath}")
            } catch (e: Throwable) {
                Log.e(TAG, "could not export SURAVIDL_FFMPEG", e)
            }
        }
        val probe = ffprobeBinary(this)
        if (probe == null) {
            Log.w(TAG, "bundled ffprobe missing from nativeLibraryDir")
        } else {
            makeExecutable(probe, "ffprobe")
            try {
                Os.setenv("SURAVIDL_FFPROBE", probe.absolutePath, true)
                Log.i(TAG, "bundled ffprobe: ${probe.absolutePath}")
            } catch (e: Throwable) {
                Log.e(TAG, "could not export SURAVIDL_FFPROBE", e)
            }
        }
    }

    private fun makeExecutable(f: File, what: String) {
        if (f.canExecute()) return
        try {
            Os.chmod(f.absolutePath, 0b111101101) // rwxr-xr-x
        } catch (e: Throwable) {
            // the lib dir belongs to the platform: extraction already applies
            // 0755, so an EACCES here is not fatal by itself
            Log.w(TAG, "chmod on bundled $what failed: $e")
        }
    }

    companion object {
        const val TAG = "suravidl"

        /** The bundled ffmpeg executable, or null when the APK lacks one. */
        fun ffmpegBinary(ctx: Context): File? = nativeBinary(ctx, "libffmpeg.so")

        /** The bundled ffprobe executable (yt-dlp's stream inspector). */
        fun ffprobeBinary(ctx: Context): File? = nativeBinary(ctx, "libffprobe.so")

        private fun nativeBinary(ctx: Context, name: String): File? {
            val f = File(ctx.applicationInfo.nativeLibraryDir, name)
            return if (f.exists()) f else null
        }
    }
}
