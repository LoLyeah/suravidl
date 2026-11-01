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
import android.system.Os
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
import java.util.Locale
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

    /** The notification's big tile: OUR pine mark, rasterized from this
     *  build's own resources, never the phone's possibly-stale copy of the
     *  app icon. Drawable API on purpose: on modern Android the launcher
     *  icon is an adaptive-icon XML that BitmapFactory cannot decode (a
     *  silent null). Guarded too: a notification with no big tile is fine,
     *  a dead engine is not. */
    private val notifLogo: android.graphics.Bitmap? by lazy {
        try {
            val d = androidx.core.content.ContextCompat.getDrawable(this, R.mipmap.ic_launcher)
            if (d == null) null else {
                val side = 96
                val bmp = android.graphics.Bitmap.createBitmap(
                    side, side, android.graphics.Bitmap.Config.ARGB_8888)
                d.setBounds(0, 0, side, side)
                d.draw(android.graphics.Canvas(bmp))
                bmp
            }
        } catch (t: Throwable) {
            Log.w(SuravidlApp.TAG, "the notification's big tile could not be drawn", t)
            null
        }
    }
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
        // The notification's Cancel action re-enters here (v0.47.28). It must
        // run before the engineStarted guard: a running service still has to
        // answer it, and it must never restart the engine.
        if (intent?.action == ACTION_CANCEL) {
            intent.getStringExtra(EXTRA_JOB_ID)?.takeIf { it.isNotBlank() }?.let { id ->
                thread(name = "cancel-job") { cancelJob(id) }
            }
            return START_STICKY
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
                // yt-dlp's cache belongs in the app's cache bucket: the
                // system's Clear-cache button governs it, storage pressure
                // may evict it, and it stops counting as unbrowsable app
                // "data" (v0.24.9). Export before Python starts — Chaquopy
                // builds os.environ from the process env.
                try {
                    Os.setenv("SURAVIDL_CACHE_DIR", cacheDir.absolutePath, true)
                    // python engine detects the android shell by this flag
                    Os.setenv("SURAVIDL_ANDROID", "1", true)
                } catch (t: Throwable) {
                    Log.w(SuravidlApp.TAG, "could not export SURAVIDL_CACHE_DIR", t)
                }
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
            activeJobs().size
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

    /** Failed gallery-import attempts per job, so one bad file cannot cause a
     *  full re-copy on every 2-second tick. Cleared when the job settles. */
    private val importTries = HashMap<String, Int>()

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
            var lastError: Throwable? = null
            for (p in paths) {
                val f = File(p)
                if (!f.isFile) continue
                existing++
                try {
                    // the row's URI is the only exact way back to it
                    // (v0.47.18: name-based deletion took same-named twins)
                    val copy = MediaImporter.importToGallery(this, f)
                    if (copy != null) {
                        imported = true
                        MediaLibrary.rememberCopy(this, id, copy)
                    }
                } catch (t: Throwable) {
                    lastError = t
                }
            }
            // Below API 29 there is no scoped storage: the app's own folder is
            // already reachable, MediaImporter returns null by design and no
            // copy is ever made. `existing` counts FILES, not copies, so the
            // old condition could never be met there — every finished job was
            // re-checked every 2 seconds forever and wrote a log line each
            // time (found in the UI/Android review).
            val canCopy = Build.VERSION.SDK_INT >= 29
            if (imported || existing == 0 || !canCopy) {
                importTries.remove(id)
                rememberImported(id)
                continue
            }
            // A copy that keeps failing (full storage, revoked permission)
            // gets a few tries and one log line — not a full re-copy on every
            // tick with a fresh log entry beside it.
            val tries = (importTries[id] ?: 0) + 1
            importTries[id] = tries
            if (tries == 1 && lastError != null) writeLog("import-error", lastError)
            if (tries >= IMPORT_TRIES) {
                writeLog("import-gave-up", IllegalStateException(
                    "gallery import failed $tries times for $id: " +
                        (lastError?.toString() ?: "no detail")))
                rememberImported(id)
            }
        }
    }

    /** One row of /jobs, reduced to what the shade can show. */
    private data class JobBit(
        val id: String, val title: String, val status: String,
        val pct: Int, val speed: Double, val eta: Long,
    )

    /**
     * Everything the notification needs, from the same endpoint the UI polls.
     * The old version counted rows and threw the numbers away; `jobs` already
     * carries downloaded_bytes / total_bytes / speed / eta (v0.47.28).
     */
    private fun activeJobs(): List<JobBit> {
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
        val out = ArrayList<JobBit>(jobs.length())
        for (i in 0 until jobs.length()) {
            val j = jobs.getJSONObject(i)
            val status = j.optString("status")
            if (status != "queued" && status != "downloading" && status != "merging") continue
            val p = j.optJSONObject("progress") ?: JSONObject()
            val got = p.optLong("downloaded_bytes", 0L)
            val total = p.optLong("total_bytes", 0L)
            val pct = if (total > 0) ((got * 100) / total).toInt().coerceIn(0, 100) else 0
            out.add(JobBit(
                id = j.optString("id"),
                title = j.optString("title").ifBlank { j.optString("url") },
                status = status,
                pct = pct,
                speed = p.optDouble("speed", 0.0),
                eta = p.optLong("eta", 0L),
            ))
        }
        return out
    }

    private fun speedText(bps: Double): String = when {
        bps >= 1048576 -> String.format(Locale.US, "%.1f MB/s", bps / 1048576)
        bps >= 1024 -> String.format(Locale.US, "%.0f KB/s", bps / 1024)
        bps > 0 -> String.format(Locale.US, "%.0f B/s", bps)
        else -> ""
    }

    private fun etaText(sec: Long): String =
        if (sec <= 0 || sec > 86400) "" else String.format(Locale.US, "%d:%02d left", sec / 60, sec % 60)

    private fun cancelJob(id: String) {
        try {
            val c = URL("http://127.0.0.1:$ENGINE_PORT/jobs/$id/cancel").openConnection()
                as HttpURLConnection
            c.requestMethod = "POST"
            c.setRequestProperty("Authorization", "Bearer $token")
            c.connectTimeout = 3000
            c.readTimeout = 3000
            c.responseCode      // run it; the body does not matter here
            c.disconnect()
        } catch (t: Throwable) {
            Log.w(SuravidlApp.TAG, "cancel from the notification failed", t)
        }
        updateCount()
    }

    private fun cancelIntent(id: String): PendingIntent =
        PendingIntent.getService(
            this, 11,
            Intent(this, EngineService::class.java)
                .setAction(ACTION_CANCEL)
                .putExtra(EXTRA_JOB_ID, id),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    /** A download in progress, in the shade: how far, how fast, how long, and
     *  a way to stop it without opening the app. */
    private fun buildProgress(jobs: List<JobBit>): android.app.Notification {
        val j = jobs.first()
        val bits = ArrayList<String>(3)
        if (j.pct > 0) bits.add("${j.pct}%")
        speedText(j.speed).takeIf { it.isNotEmpty() }?.let { bits.add(it) }
        etaText(j.eta).takeIf { it.isNotEmpty() }?.let { bits.add(it) }
        if (j.status == "merging") bits.add("finishing up")
        val text = if (bits.isEmpty()) "downloading…" else bits.joinToString(" · ")
        val title = if (jobs.size > 1) "suravidl — ${jobs.size} downloading" else "suravidl — downloading"
        val builder = NotificationCompat.Builder(this, CHANNEL).apply {
            setContentTitle(title)
            setContentText(text)
            setSubText(j.title.take(80))
            setOngoing(true)
            setOnlyAlertOnce(true)
            if (j.pct > 0 && j.status != "merging") setProgress(100, j.pct, false)
            else setProgress(0, 0, true)
            setContentIntent(openAppIntent())
            addAction(android.R.drawable.ic_menu_close_clear_cancel, "Cancel", cancelIntent(j.id))
            notifLogo?.let { setLargeIcon(it) }
        }
        return try {
            builder.setSmallIcon(R.drawable.ic_stat_suravidl).build()
        } catch (t: Throwable) {
            Log.w(SuravidlApp.TAG, "the drawn notification glyph failed; using the platform's", t)
            builder.setSmallIcon(android.R.drawable.stat_sys_download).build()
        }
    }

    private fun updateCount() {
        val notification = if (engineError != null) {
            buildNotification(
                "engine failed — log saved (${engineError!!.lineSequence().first()})", openApp = true)
        } else {
            val jobs = try { activeJobs() } catch (_: Exception) { null }
            when {
                jobs == null -> buildNotification("starting engine…", openApp = true)
                jobs.isEmpty() -> buildNotification("engine running — no active downloads", openApp = true)
                else -> buildProgress(jobs)
            }
        }
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, notification)   // same id as the foreground one:
                                            // onDestroy can take it down again
    }

    /**
     * One builder for both notification sites. The drawn mark is attempted
     * first; if attaching it throws, the platform's download glyph takes
     * over — and startInForeground has a plainer fallback still (v0.39.7).
     * A dressy icon may never keep startForeground from being called: the
     * fg-start watchdog crashes the app when a service it started does not
     * go foreground in time, and the v0.39.6 build died exactly so on both
     * emulators (ForegroundServiceDidNotStartInTimeException).
     */
    private fun buildNotification(text: String, openApp: Boolean): android.app.Notification {
        fun dressy() = NotificationCompat.Builder(this, CHANNEL).apply {
            setContentTitle("suravidl")
            setContentText(text)
            setOngoing(true)
            notifLogo?.let { setLargeIcon(it) }
            if (openApp) setContentIntent(openAppIntent())
        }
        return try {
            dressy().setSmallIcon(R.drawable.ic_stat_suravidl).build()
        } catch (t: Throwable) {
            Log.w(SuravidlApp.TAG, "the drawn notification glyph failed; using the platform's", t)
            dressy().setSmallIcon(android.R.drawable.stat_sys_download).build()
        }
    }

    private fun openAppIntent(): PendingIntent = PendingIntent.getActivity(
        this, 0, Intent(this, MainActivity::class.java),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        // NotificationChannel does not exist before API 26 and its class is
        // resolved when this line runs: unguarded, an Android 7.0/7.1 phone —
        // which the manifest says we support — died with NoClassDefFoundError
        // before Python ever started. Found in the UI/Android review.
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL, "Downloads",
                                    NotificationManager.IMPORTANCE_LOW))
        }
        val n = try {
            buildNotification("starting engine…", openApp = false)
        } catch (t: Throwable) {
            // the plainest notification that can exist: platform glyph, no
            // logo, no intent. If even this fails, the outer catch stops the
            // service honestly — but it is not going to.
            Log.e(SuravidlApp.TAG, "no usable notification; posting the plainest one", t)
            writeLog("notif-fallback", t)
            NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle("suravidl")
                .setContentText("starting engine…")
                .setOngoing(true)
                .build()
        }
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
        // the decrypted session cookies must not outlive the engine: a
        // swipe-away kill (not the app's Quit path) used to leave
        // cookies.session.txt on disk until the next launch (v0.40.10 audit;
        // unlocking is on demand, so wiping here costs nothing)
        try {
            CookieVault.lockSession(this)
        } catch (_: Throwable) {
        }
        // the ongoing notification is ours to take down; a killed process
        // otherwise leaves it behind with nothing running (v0.21.1 audit)
        NotificationManagerCompat.from(this).cancel(NOTIF_ID)
        super.onDestroy()
    }

    companion object {
        const val ENGINE_PORT = 8787
        const val CHANNEL = "downloads"
        const val NOTIF_ID = 1

        /** The notification's Cancel action; handled before the engine guard. */
        const val ACTION_CANCEL = "com.suravidl.app.CANCEL_JOB"
        const val EXTRA_JOB_ID = "job_id"

        /** How many ticks a failing Gallery/Music copy gets before the app
         *  stops trying (and says so once in the log). */
        const val IMPORT_TRIES = 5

        /** The page key the shell generated (the service writes it before the
         *  engine starts, the activity reads it to load the UI with it). */
        fun pageKeyOf(context: Context): String =
            context.getSharedPreferences("engine", Context.MODE_PRIVATE)
                .getString("page_key", "") ?: ""
    }
}
