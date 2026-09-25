package com.suravidl.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Environment
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import kotlin.concurrent.thread

/**
 * Foreground service hosting the engine (uvicorn on 127.0.0.1:8787).
 *
 * Every background thread here is fully guarded: an uncaught exception on
 * ANY thread kills the whole Android process ("app keeps stopping"), so all
 * failure paths are caught, logged to Android/data/.../files/logs, and
 * surfaced in the notification instead.
 */
class EngineService : Service() {
    private var token = ""
    @Volatile private var polling = true
    @Volatile private var engineError: String? = null

    /**
     * The framework re-delivers onStartCommand to a *running* service whenever
     * the activity is recreated (rotation, theme change, relaunch). Starting
     * the engine twice means two JobManagers on one jobs.db — and the second
     * one marks the first one's live downloads "interrupted" and re-downloads
     * them into the same paths — plus a leaked notifier thread per recreation
     * (v0.21.1 audit).
     */
    @Volatile private var engineStarted = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val prefs = getSharedPreferences("engine", MODE_PRIVATE)
        token = prefs.getString("token", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("token", it).apply()
        }
        // The page that inlines the token is gated behind a key only we have:
        // loopback is shared, so any other app could otherwise fetch the page
        // and drive the engine with the token it finds there (v0.21.1 audit).
        val pageKey = prefs.getString("page_key", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("page_key", it).apply()
        }
        if (engineStarted) return START_STICKY       // one engine per process
        engineStarted = true
        try {
            startInForeground()
        } catch (t: Throwable) {
            Log.e(SuravidlApp.TAG, "startForeground failed", t)
            writeLog("engine-error", t)
            // a service that cannot go foreground is killed within minutes and
            // would leave an un-swipeable "downloading…" notification behind
            NotificationManagerCompat.from(this).cancel(NOTIF_ID)
            stopSelf()
            return START_NOT_STICKY
        }

        val dl = File(
            getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: filesDir, "suravidl")
        dl.mkdirs()
        val db = File(filesDir, "jobs.db")

        thread(name = "engine") {
            try {
                if (!Python.isStarted()) Python.start(AndroidPlatform(this))
                Python.getInstance().getModule("suravidl_engine.__main__")
                    .callAttr("start_server", dl.absolutePath, token, ENGINE_PORT,
                              db.absolutePath, null, pageKey)
                awaitEngine()
                updateCount()
            } catch (t: Throwable) {
                engineError = t.stackTraceToString()
                Log.e(SuravidlApp.TAG, "engine failed to start", t)
                writeLog("engine-error", t)
                try {
                    updateCount()
                } catch (_: Throwable) {
                }
            }
        }
        thread(name = "notifier") {
            while (polling) {
                try {
                    updateCount()
                    importCompleted()
                    syncWakeLock()
                } catch (_: Throwable) {
                    // never let a polling hiccup kill the process
                }
                Thread.sleep(2000)
            }
        }
        return START_STICKY
    }

    /** Keep the CPU awake while downloads are active (screen off / background). */
    private var wakeLock: PowerManager.WakeLock? = null

    private fun syncWakeLock() {
        val active = try {
            activeCount()
        } catch (_: Exception) {
            return  // engine not answering; leave the lock as it is
        }
        if (active > 0) {
            if (wakeLock == null) {
                val pm = getSystemService(POWER_SERVICE) as PowerManager
                wakeLock = pm.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK, "suravidl:downloads")
            }
            wakeLock?.takeIf { !it.isHeld }?.acquire(6 * 60 * 60 * 1000L)
        } else {
            releaseWakeLock()
        }
    }

    private fun releaseWakeLock() {
        try {
            wakeLock?.takeIf { it.isHeld }?.release()
        } catch (_: Throwable) {
        }
    }

    /** Wait until the engine's /health answers (uvicorn binds asynchronously). */
    private fun awaitEngine(timeoutMs: Long = 60_000) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            if (healthOk()) return
            Thread.sleep(500)
        }
        throw IllegalStateException("engine did not answer /health within ${timeoutMs} ms")
    }

    private fun healthOk(): Boolean = try {
        val c = URL("http://127.0.0.1:$ENGINE_PORT/health").openConnection()
                as HttpURLConnection
        try {
            c.connectTimeout = 2000
            c.responseCode == 200
        } finally {
            c.disconnect()   // a probe that never closes leaks a socket per poll
        }
    } catch (_: Exception) {
        false
    }

    private fun writeLog(prefix: String, t: Throwable) {
        LogStore.write(
            this, "$prefix-${System.currentTimeMillis()}.txt",
            "thread=${Thread.currentThread().name}\n${t.stackTraceToString()}")
    }

    /** Ids already pushed into the system library. Persisted: a fresh process
     *  used to re-import every past download again, so each app start made one
     *  more gallery copy of everything ("clip (1).mp4", "clip (2).mp4", …)
     *  (v0.21.1 audit). */
    private val importedIds: MutableSet<String> by lazy {
        getSharedPreferences("engine", MODE_PRIVATE)
            .getStringSet("imported_ids", emptySet())!!.toMutableSet()
    }

    private fun rememberImported(id: String) {
        importedIds.add(id)
        getSharedPreferences("engine", MODE_PRIVATE).edit()
            .putStringSet("imported_ids", importedIds).apply()
    }

    /** Push newly completed engine downloads into the system gallery.
     *
     *  A playlist job names its own files (`files`); importing only its
     *  filepath (the download folder) was a no-op, so a finished playlist
     *  never showed up in the gallery (v0.21.1 audit). */
    private fun importCompleted() {
        val c = URL("http://127.0.0.1:$ENGINE_PORT/jobs").openConnection()
            as HttpURLConnection
        c.setRequestProperty("Authorization", "Bearer $token")
        c.connectTimeout = 2000
        val jobs = try {
            JSONObject(c.inputStream.bufferedReader().readText()).getJSONArray("jobs")
        } finally {
            c.disconnect()
        }
        for (i in 0 until jobs.length()) {
            val j = jobs.getJSONObject(i)
            if (j.getString("status") != "completed") continue
            val id = j.getString("id")
            if (id in importedIds) continue
            val paths = mutableListOf<String>()
            val listed = j.optJSONArray("files")
            if (listed != null) {
                for (k in 0 until listed.length()) {
                    paths.add(listed.getString(k))
                }
            } else {
                j.optString("filepath", "").takeIf { it.isNotEmpty() }?.let { paths.add(it) }
            }
            var imported = false
            var existing = 0
            for (p in paths) {
                val f = File(p)
                if (!f.isFile) continue
                existing++
                try {
                    if (MediaImporter.importToGallery(this, f) != null) imported = true
                } catch (t: Throwable) {
                    writeLog("import-error", t)
                }
            }
            // remember what worked — and a job with nothing left to import;
            // a transient failure is retried on the next tick instead
            if (imported || existing == 0) rememberImported(id)
        }
    }

    private fun activeCount(): Int {
        val c = URL("http://127.0.0.1:$ENGINE_PORT/jobs").openConnection()
            as HttpURLConnection
        c.setRequestProperty("Authorization", "Bearer $token")
        c.connectTimeout = 2000
        val body = try {
            c.inputStream.bufferedReader().readText()
        } finally {
            c.disconnect()
        }
        val jobs = JSONObject(body).getJSONArray("jobs")
        var n = 0
        for (i in 0 until jobs.length()) {
            when (jobs.getJSONObject(i).getString("status")) {
                "queued", "downloading", "merging" -> n++
            }
        }
        return n
    }

    private fun updateCount() {
        val text = engineError?.let { err ->
            "engine failed — log saved (${err.lineSequence().first()})"
        } ?: try {
            val n = activeCount()
            if (n == 0) "engine running — no active downloads"
            else "downloading $n…"
        } catch (_: Exception) {
            "starting engine…"
        }
        val notification = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("suravidl")
            .setContentText(text)
            .setContentIntent(openAppIntent())
            .setOngoing(true)
            .build()
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, notification)   // same id as the foreground one:
                                            // onDestroy can take it down again
    }

    private fun openAppIntent(): PendingIntent = PendingIntent.getActivity(
        this, 0, Intent(this, MainActivity::class.java),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Downloads",
                                NotificationManager.IMPORTANCE_LOW))
        val n = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("suravidl")
            .setContentText("starting engine…")
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 29) {
            ServiceCompat.startForeground(
                this, NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, n)
        }
    }

    /**
     * Android 15 gives a `dataSync` foreground service about six hours a day;
     * past that the system kills the process with an exception — and this app
     * legitimately runs for hours (v0.21.1 audit). Stop politely instead: the
     * engine keeps its jobs in SQLite, so auto-resume picks them up next start.
     */
    override fun onTimeout(startId: Int, fgsType: Int) {
        polling = false
        releaseWakeLock()
        NotificationManagerCompat.from(this).cancel(NOTIF_ID)
        stopSelf()
    }

    override fun onDestroy() {
        polling = false
        releaseWakeLock()
        // the ongoing notification is ours to take down; a killed process
        // otherwise leaves it behind with nothing running (v0.21.1 audit)
        NotificationManagerCompat.from(this).cancel(NOTIF_ID)
        super.onDestroy()
    }

    companion object {
        const val ENGINE_PORT = 8787
        const val CHANNEL = "downloads"
        const val NOTIF_ID = 1

        /** The page key the shell generated (the service writes it before the
         *  engine starts, the activity reads it to load the UI with it). */
        fun pageKeyOf(context: Context): String =
            context.getSharedPreferences("engine", Context.MODE_PRIVATE)
                .getString("page_key", "") ?: ""
    }
}
