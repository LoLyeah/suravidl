package com.suravidl.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Environment
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
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

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val prefs = getSharedPreferences("engine", MODE_PRIVATE)
        token = prefs.getString("token", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("token", it).apply()
        }
        try {
            startInForeground()
        } catch (t: Throwable) {
            Log.e(SuravidlApp.TAG, "startForeground failed", t)
            writeLog("engine-error", t)
        }

        val dl = File(getExternalFilesDir(Environment.DIRECTORY_MOVIES), "suravidl")
        dl.mkdirs()
        val db = File(filesDir, "jobs.db")

        thread(name = "engine") {
            try {
                if (!Python.isStarted()) Python.start(AndroidPlatform(this))
                Python.getInstance().getModule("suravidl_engine.__main__")
                    .callAttr("start_server", dl.absolutePath, token, ENGINE_PORT,
                              db.absolutePath)
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
                } catch (_: Throwable) {
                    // never let a polling hiccup kill the process
                }
                Thread.sleep(2000)
            }
        }
        return START_STICKY
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
        c.connectTimeout = 2000
        c.responseCode == 200
    } catch (_: Exception) {
        false
    }

    private fun writeLog(prefix: String, t: Throwable) {
        LogStore.write(
            this, "$prefix-${System.currentTimeMillis()}.txt",
            "thread=${Thread.currentThread().name}\n${t.stackTraceToString()}")
    }

    private val importedIds = HashSet<String>()

    /** Push newly completed engine downloads into the system gallery. */
    private fun importCompleted() {
        val c = URL("http://127.0.0.1:$ENGINE_PORT/jobs").openConnection()
            as HttpURLConnection
        c.setRequestProperty("Authorization", "Bearer $token")
        c.connectTimeout = 2000
        val jobs = JSONObject(c.inputStream.bufferedReader().readText())
            .getJSONArray("jobs")
        for (i in 0 until jobs.length()) {
            val j = jobs.getJSONObject(i)
            if (j.getString("status") != "completed") continue
            val id = j.getString("id")
            if (!importedIds.add(id)) continue
            val path = j.optString("filepath", "")
            if (path.isNotEmpty()) {
                val f = File(path)
                if (f.exists()) {
                    try {
                        MediaImporter.importToGallery(this, f)
                    } catch (_: Exception) {
                    }
                }
            }
        }
    }

    private fun activeCount(): Int {
        val c = URL("http://127.0.0.1:$ENGINE_PORT/jobs").openConnection()
            as HttpURLConnection
        c.setRequestProperty("Authorization", "Bearer $token")
        c.connectTimeout = 2000
        val body = c.inputStream.bufferedReader().readText()
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
            .setOngoing(true)
            .build()
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(1, notification)
    }

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

    override fun onDestroy() {
        polling = false
        super.onDestroy()
    }

    companion object {
        const val ENGINE_PORT = 8787
        const val CHANNEL = "downloads"
        const val NOTIF_ID = 1
    }
}
