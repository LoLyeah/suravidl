"""Job manager: background downloads, live progress, SQLite persistence."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    fmt TEXT,
    preset TEXT,
    playlist_items TEXT,
    raw_args TEXT,
    overrides TEXT,
    headers TEXT,
    status TEXT NOT NULL,
    title TEXT,
    filepath TEXT,
    error TEXT,
    downloaded_bytes INTEGER DEFAULT 0,
    total_bytes INTEGER,
    speed REAL,
    eta INTEGER,
    created_at TEXT,
    completed_at TEXT
)
"""

ACTIVE_STATUSES = ("queued", "downloading", "merging")

# Only these captured browser headers are forwarded to yt-dlp.
ALLOWED_HEADER_KEYS = {"cookie", "user-agent", "referer", "origin",
                       "accept", "accept-language"}

# playlist item selections: '1-10', '2', '1,3,5-9'; empty = whole playlist
_PLAYLIST_ITEMS_RE = re.compile(r"^[\d,\-\s]+$")

# Cookie values are never written to disk: the live value stays in memory for
# the running job (and in-session retries); anything persisted is redacted.
REDACTED = "<redacted>"


def _redacted_headers(h: dict | None) -> dict | None:
    if not h:
        return None
    return {k: (REDACTED if str(k).lower() == "cookie" else v)
            for k, v in h.items()}


def redact_job(job: dict) -> dict:
    """Copy of a job safe to send to clients / store: cookie values removed."""
    out = dict(job)
    if out.get("headers"):
        out["headers"] = _redacted_headers(out["headers"])
    return out


def _safe_headers(h: dict | None) -> dict | None:
    if not h:
        return None
    return {k: v for k, v in h.items() if str(k).lower() in ALLOWED_HEADER_KEYS}


# One-click download intents that don't fit the per-format table.
# audio-native keeps the source stream untouched (no ffmpeg anywhere);
# the convert variants run yt-dlp's FFmpegExtractAudio post-processor.
AUDIO_PRESETS: dict[str, dict] = {
    "audio-native": {"format": "bestaudio/best"},
    "audio-m4a": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
        ],
    },
    "audio-mp3": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
             "preferredquality": "192"},
        ],
    },
}


def preset_opts(preset: str | None) -> dict:
    """yt-dlp options for a preset; ValueError on unknown names."""
    if not preset:
        return {}
    if preset not in AUDIO_PRESETS:
        raise ValueError(f"unknown preset: {preset!r}")
    spec = AUDIO_PRESETS[preset]
    opts: dict = {"format": spec["format"]}
    if spec.get("postprocessors"):
        opts["postprocessors"] = [dict(pp) for pp in spec["postprocessors"]]
    return opts


def ffmpeg_opts() -> dict:
    """Point yt-dlp at the bundled ffmpeg when the host provides one.

    Android ships a static ffmpeg as a jniLib (libffmpeg.so) and passes its
    path in via this env var; desktop builds leave it unset so yt-dlp finds
    the system ffmpeg on its own.
    """
    loc = os.environ.get("SURAVIDL_FFMPEG", "").strip()
    return {"ffmpeg_location": loc} if loc else {}


class JobManager:
    def __init__(self, download_dir, db_path=None, max_concurrent: int = 2,
                 auto_resume: bool = False, cookie_session=None,
                 download_opts=None):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path) if db_path else ":memory:"
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # one shared connection: with :memory: each connect() would be a fresh db
        self._db_lock = threading.Lock()
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.execute("PRAGMA secure_delete=ON")  # scrubbed rows leave no bytes
        self._con.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            try:
                os.chmod(self.db_path, 0o600)  # job history is private
            except OSError:
                pass
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # adaptive concurrency gate: capacity can change at runtime
        self._cap_cv = threading.Condition(threading.Lock())
        self._capacity = max(1, int(max_concurrent))
        self._active = 0
        self.on_complete = None  # optional callable(job) run after success
        # optional callable -> context manager yielding yt-dlp cookie opts
        self._cookie_session = cookie_session
        # optional callable(download_dir) -> settings-derived yt-dlp options
        self._download_opts = download_opts
        self._init_db()
        if auto_resume:
            self.resume_interrupted()

    # -- persistence -------------------------------------------------------
    def _init_db(self):
        with self._db_lock:
            with self._con:
                self._con.executescript(_SCHEMA)
                # lightweight migration for dbs created before the headers column
                cols = {r[1] for r in self._con.execute("PRAGMA table_info(jobs)")}
                if "headers" not in cols:
                    self._con.execute("ALTER TABLE jobs ADD COLUMN headers TEXT")
                if "preset" not in cols:
                    self._con.execute("ALTER TABLE jobs ADD COLUMN preset TEXT")
                if "playlist_items" not in cols:
                    self._con.execute(
                        "ALTER TABLE jobs ADD COLUMN playlist_items TEXT")
                if "raw_args" not in cols:
                    self._con.execute("ALTER TABLE jobs ADD COLUMN raw_args TEXT")
                if "overrides" not in cols:
                    self._con.execute(
                        "ALTER TABLE jobs ADD COLUMN overrides TEXT")
                # scrub cookie values persisted by earlier versions
                scrubbed = self._scrub_persisted_cookies()
                # crash recovery: anything active when we died is interrupted
                self._con.execute(
                    "UPDATE jobs SET status='interrupted', "
                    "error='engine restarted before job finished' "
                    "WHERE status IN (?, ?, ?)", ACTIVE_STATUSES,
                )
            if scrubbed:
                # rewrite the file so the old bytes are gone, not just the row
                self._con.execute("VACUUM")
            for row in self._con.execute("SELECT * FROM jobs"):
                self._jobs[row["id"]] = self._row_to_job(row)

    def _scrub_persisted_cookies(self) -> bool:
        """Redact cookie values already in old rows. True if anything changed."""
        changed = False
        for row in self._con.execute(
                "SELECT id, headers FROM jobs WHERE headers IS NOT NULL"):
            try:
                h = json.loads(row["headers"])
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(h, dict):
                continue
            if any(str(k).lower() == "cookie" and v != REDACTED
                   for k, v in h.items()):
                self._con.execute("UPDATE jobs SET headers=? WHERE id=?",
                                  (json.dumps(_redacted_headers(h)), row["id"]))
                changed = True
        return changed

    @staticmethod
    def _row_to_job(row: dict) -> dict:
        job = dict(row)
        h = json.loads(job["headers"]) if job.get("headers") else None
        if h:
            # a redacted cookie on disk is no cookie at all — never send the
            # placeholder to yt-dlp
            h = {k: v for k, v in h.items()
                 if not (str(k).lower() == "cookie" and v == REDACTED)}
            h = h or None
        job["headers"] = h
        overrides = job.get("overrides")
        if overrides:
            try:
                job["overrides"] = json.loads(overrides)
            except (json.JSONDecodeError, TypeError):
                job["overrides"] = None
        else:
            job["overrides"] = None
        job["progress"] = {
            "downloaded_bytes": job.get("downloaded_bytes") or 0,
            "total_bytes": job.get("total_bytes"),
            "speed": job.get("speed"),
            "eta": job.get("eta"),
        }
        return job

    def _save(self, job: dict):
        with self._db_lock, self._con:
            self._con.execute(
                "INSERT INTO jobs (id, url, fmt, preset, playlist_items,"
                " raw_args, overrides, headers, status, title,"
                " filepath, error, downloaded_bytes, total_bytes, speed, eta,"
                " created_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
                " title=excluded.title, filepath=excluded.filepath,"
                " error=excluded.error, downloaded_bytes=excluded.downloaded_bytes,"
                " total_bytes=excluded.total_bytes, speed=excluded.speed,"
                " eta=excluded.eta, completed_at=excluded.completed_at",
                (
                    job["id"], job["url"], job.get("fmt"), job.get("preset"),
                    job.get("playlist_items"),
                    job.get("raw_args"),
                    json.dumps(job["overrides"]) if job.get("overrides") else None,
                    json.dumps(_redacted_headers(job["headers"]))
                    if job.get("headers") else None,
                    job["status"], job.get("title"), job.get("filepath"),
                    job.get("error"),
                    job["progress"]["downloaded_bytes"],
                    job["progress"]["total_bytes"], job["progress"]["speed"],
                    job["progress"]["eta"], job.get("created_at"),
                    job.get("completed_at"),
                ),
            )

    # -- public API --------------------------------------------------------
    def create(self, url: str, fmt: str | None = None,
               extra_headers: dict | None = None,
               preset: str | None = None,
               playlist_items: str | None = None,
               raw_args: str | None = None,
               overrides: dict | None = None) -> dict:
        from .settings import validate_overrides

        if overrides:
            # validated here, before a row exists: a bad patch never queues
            overrides = validate_overrides(overrides) or None
        else:
            overrides = None
        if preset and fmt:
            raise ValueError("pass either 'preset' or 'fmt', not both")
        if preset:
            preset_opts(preset)  # validate up front, before queueing
        if playlist_items is not None:
            playlist_items = str(playlist_items).strip()
            if playlist_items and not _PLAYLIST_ITEMS_RE.match(playlist_items):
                raise ValueError(
                    "playlist_items must look like '1-10', '2', '1,3,5-9' "
                    "or be empty for the whole playlist")
        if raw_args is not None:
            raw_args = str(raw_args).strip() or None
            if raw_args:
                from .download_opts import parse_raw_args

                parse_raw_args(raw_args)  # raises ValueError on junk
        extra_headers = _safe_headers(extra_headers)
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "url": url,
            "fmt": fmt,
            "preset": preset,
            "playlist_items": playlist_items,
            "raw_args": raw_args,
            "overrides": overrides,
            "headers": extra_headers,
            "status": "queued",
            "title": None,
            "filepath": None,
            "error": None,
            "progress": {"downloaded_bytes": 0, "total_bytes": None,
                         "speed": None, "eta": None},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._jobs[job_id] = job
        self._save(job)
        t = threading.Thread(target=self._run, args=(job, fmt, extra_headers),
                             daemon=True)
        t.start()
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._lock:
            return dict(self._jobs[job_id])

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(j) for j in self._jobs.values()]

    def cancel(self, job_id: str) -> dict:
        """Cancel a queued or running job. Running ones stop at the next hook."""
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] not in ACTIVE_STATUSES:
                raise ValueError(f"cannot cancel job in status '{job['status']}'")
            job["status"] = "cancelled"  # queued jobs never start; running see below
        self._save(job)
        return self.get(job_id)

    def retry(self, job_id: str) -> dict:
        """Re-run a terminal (error/interrupted/cancelled) job as a new job."""
        src = self.get(job_id)
        if src["status"] not in ("error", "interrupted", "cancelled"):
            raise ValueError(f"cannot retry job in status '{src['status']}'")
        return self.create(src["url"], fmt=src.get("fmt"),
                           extra_headers=src.get("headers"),
                           preset=src.get("preset"),
                           playlist_items=src.get("playlist_items"),
                           raw_args=src.get("raw_args"),
                           overrides=src.get("overrides"))

    def clear_completed(self) -> int:
        """Forget completed jobs (their files are gone after /files/clear).

        Errored/cancelled rows stay so they can still be retried.
        """
        with self._lock:
            gone = [jid for jid, j in self._jobs.items()
                    if j["status"] == "completed"]
            for jid in gone:
                self._jobs.pop(jid, None)
            if gone:
                self._con.execute(
                    "DELETE FROM jobs WHERE status = 'completed'")
                self._con.commit()
        return len(gone)

    # -- deleting one download (the trash button) -------------------------
    SIDECAR_SUFFIXES = (".info.json", ".description", ".annotations.xml",
                        ".jpg", ".jpeg", ".png", ".webp", ".vtt", ".srt",
                        ".ass", ".lrc", ".json", ".live_chat.json")

    def _job_file_targets(self, job: dict) -> list[Path]:
        """The files a job owns: its path plus sidecars sharing its stem.

        Anything outside the download dir is refused — a job row is not a
        licence to delete arbitrary paths.
        """
        raw = job.get("filepath")
        if not raw:
            return []
        path = Path(str(raw))
        root = Path(self.download_dir).resolve()
        try:
            inside = path.resolve().is_relative_to(root)
        except OSError:
            inside = False
        if not inside:
            raise PermissionError(
                f"refusing to delete {path}: it is outside the download folder")
        if not path.exists():
            return []
        if path.is_dir():
            return [p for p in sorted(path.rglob("*"),
                                      key=lambda q: len(q.parts), reverse=True)
                    if p.is_file() or p.is_dir()]
        targets = [path]
        for suffix in self.SIDECAR_SUFFIXES:
            sidecar = path.with_name(path.stem + suffix)
            if sidecar.exists() and sidecar.is_file() and sidecar != path:
                targets.append(sidecar)
        return targets

    def delete_job(self, job_id: str) -> dict:
        """Delete one download: its file, its sidecars, and its row.

        Refuses while the job is still running (cancel first) and for files
        that live outside the download folder — deleting is one-way, so the
        refusal is the feature.
        """
        try:
            job = self.get(job_id)
        except KeyError:
            raise KeyError(job_id) from None
        status = job.get("status")
        if status in ("queued", "downloading", "merging"):
            raise ValueError("cancel this download before deleting it")
        targets = self._job_file_targets(job)
        deleted = freed = 0
        for p in targets:
            try:
                if p.is_dir():
                    p.rmdir()
                else:
                    freed += p.stat().st_size
                    p.unlink()
                    deleted += 1
            except OSError:
                pass
        with self._lock:
            self._jobs.pop(job_id, None)
            with self._con:
                self._con.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return {"deleted": deleted, "freed_bytes": freed,
                "filepath": job.get("filepath")}

    def resume_interrupted(self) -> list[str]:
        """Re-queue jobs marked 'interrupted' (e.g. killed mid-download).

        Restarts them in place — same job id, progress reset — so a process
        death (swipe-away, low-memory kill) doesn't strand downloads.
        Returns the resumed job ids.
        """
        with self._lock:
            stale = [j for j in self._jobs.values()
                     if j["status"] == "interrupted"]
        resumed: list[str] = []
        for job in stale:
            with self._lock:
                job["status"] = "queued"
                job["error"] = None
                job["progress"] = {"downloaded_bytes": 0, "total_bytes": None,
                                   "speed": None, "eta": None}
            self._save(job)
            threading.Thread(target=self._run,
                             args=(job, job.get("fmt"), job.get("headers")),
                             daemon=True).start()
            resumed.append(job["id"])
        return resumed

    # -- runtime tuning ----------------------------------------------------
    def set_download_dir(self, path) -> None:
        """New jobs land in `path`; in-flight jobs keep their original dir."""
        self.download_dir = Path(path)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def set_capacity(self, n: int) -> None:
        """Live-adjust how many jobs may run at once (wakes waiters)."""
        with self._cap_cv:
            self._capacity = max(1, int(n))
            self._cap_cv.notify_all()

    def _acquire_slot(self) -> None:
        with self._cap_cv:
            while self._active >= self._capacity:
                self._cap_cv.wait()
            self._active += 1

    def _release_slot(self) -> None:
        with self._cap_cv:
            self._active -= 1
            self._cap_cv.notify_all()

    def _run(self, job: dict, fmt: str | None, extra_headers: dict | None):
        self._acquire_slot()
        try:
            self._execute(job, fmt, extra_headers)
        finally:
            self._release_slot()

    def _execute(self, job: dict, fmt: str | None, extra_headers: dict | None):
        if job["status"] == "cancelled":  # cancelled while queued
            return

        class _Cancelled(Exception):
            pass

        def hook(d):
            if job["status"] == "cancelled":  # cancel requested mid-run
                raise _Cancelled()
            if d["status"] == "downloading":
                job["status"] = "downloading"
                d_info = d.get("info_dict") or {}
                job["progress"] = {
                    "downloaded_bytes": d.get("downloaded_bytes") or 0,
                    "total_bytes": d.get("total_bytes")
                    or d.get("total_bytes_estimate"),
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    # playlists: which item of how many is running
                    "playlist_index": d_info.get("playlist_index")
                    or d.get("playlist_index"),
                    "playlist_count": d_info.get("n_entries")
                    or d.get("playlist_count"),
                }
                self._save(job)
            elif d["status"] == "finished":
                job["status"] = "merging"
                self._save(job)

        opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": str(self.download_dir / "%(title).100B.%(ext)s"),
            "progress_hooks": [hook],
            "postprocessor_hooks": [hook],
        }
        opts.update(ffmpeg_opts())
        # settings-derived options (template, subtitles, embed, network, ...)
        user_pps: list[dict] = []
        if self._download_opts:
            settings_opts = dict(self._download_opts(
                self.download_dir, raw_args=job.get("raw_args"),
                overrides=job.get("overrides")) or {})
            user_pps = list(settings_opts.pop("postprocessors", []) or [])
            opts.update(settings_opts)
        # preset postprocessors run first (e.g. extract audio), then the
        # settings ones (embed metadata/thumbnail/subs) on the result
        preset_pps: list[dict] = []
        if job.get("preset"):
            p = preset_opts(job["preset"])
            opts["format"] = p["format"]
            preset_pps = list(p.get("postprocessors", []) or [])
        pps = preset_pps + user_pps
        if pps:
            opts["postprocessors"] = pps
        # playlists are opt-in: only an explicit playlist_items (even empty,
        # meaning "everything") unlocks the whole list; a playlist URL
        # without one yields just its first entry (yt-dlp's noplaylist alone
        # does not stop a playlist-only URL).
        if job.get("playlist_items") is not None:
            opts["noplaylist"] = False
            if job["playlist_items"]:
                opts["playlist_items"] = job["playlist_items"]
        else:
            opts["noplaylist"] = True
            opts["playlist_items"] = "1"
        if fmt:
            opts["format"] = fmt
        if extra_headers:
            opts["http_headers"] = extra_headers
        try:
            with (self._cookie_session() if self._cookie_session
                  else nullcontext()) as cookie_opts:
                if cookie_opts:
                    opts.update(cookie_opts)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(job["url"], download=True)
                    info = ydl.sanitize_info(info) or {}
            if (info or {}).get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if e]
                job["title"] = info.get("title") or "playlist"
                job["filepath"] = str(self.download_dir)
                job["playlist_count"] = len(entries)
            else:
                req = (info.get("requested_downloads") or [{}])[0]
                job["title"] = info.get("title")
                job["filepath"] = req.get("filepath") or info.get("filepath")
                if not job["filepath"] and opts.get("download_archive"):
                    # a URL already in the archive is skipped by design
                    job["note"] = "already in the archive — skipped"
                    job["filepath"] = str(self.download_dir)
                if not job["filepath"]:
                    raise RuntimeError("download finished but no filepath reported")
            job["status"] = "completed"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
        except _Cancelled:
            job["status"] = "cancelled"
            job["error"] = "cancelled by user"
        except Exception as e:  # noqa: BLE001 - surfaced to the UI
            if job["status"] == "cancelled":  # raced with cancel
                job["error"] = "cancelled by user"
            else:
                job["status"] = "error"
                job["error"] = str(e)
        finally:
            self._save(job)
        if job["status"] == "completed" and self.on_complete:
            try:
                self.on_complete(job)
            except Exception:  # noqa: BLE001 - a hook must never kill a job
                pass
