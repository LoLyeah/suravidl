package com.suravidl.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Environment
import android.os.IBinder
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

/** Foreground service hosting the engine (uvicorn on 127.0.0.1:8787). */
class EngineService : Service() {
    private var token = ""
    @Volatile private var polling = true

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val prefs = getSharedPreferences("engine", MODE_PRIVATE)
        token = prefs.getString("token", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("token", it).apply()
        }
        startInForeground()

        val dl = File(getExternalFilesDir(Environment.DIRECTORY_MOVIES), "suravidl")
        dl.mkdirs()
        val db = File(filesDir, "jobs.db")

        thread(name = "engine") {
            if (!Python.isStarted()) Python.start(AndroidPlatform(this))
            Python.getInstance().getModule("suravidl_engine.__main__")
                .callAttr("start_server", dl.absolutePath, token, ENGINE_PORT,
                          db.absolutePath)
            updateCount()
        }
        thread(name = "notifier") {
            while (polling) {
                try {
                    updateCount()
                } catch (_: Exception) {
                }
                Thread.sleep(2000)
            }
        }
        return START_STICKY
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
        val n = activeCount()
        val text = if (n == 0) "engine running — no active downloads"
        else "downloading $n…"
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