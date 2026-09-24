"""Job manager: background downloads, live progress, SQLite persistence."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    fmt TEXT,
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


def _safe_headers(h: dict | None) -> dict | None:
    if not h:
        return None
    return {k: v for k, v in h.items() if str(k).lower() in ALLOWED_HEADER_KEYS}


class JobManager:
    def __init__(self, download_dir, db_path=None, max_concurrent: int = 2):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path) if db_path else ":memory:"
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # one shared connection: with :memory: each connect() would be a fresh db
        self._db_lock = threading.Lock()
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # adaptive concurrency gate: capacity can change at runtime
        self._cap_cv = threading.Condition(threading.Lock())
        self._capacity = max(1, int(max_concurrent))
        self._active = 0
        self.on_complete = None  # optional callable(job) run after success
        self._init_db()

    # -- persistence -------------------------------------------------------
    def _init_db(self):
        with self._db_lock, self._con:
            self._con.executescript(_SCHEMA)
            # lightweight migration for dbs created before the headers column
            cols = {r[1] for r in self._con.execute("PRAGMA table_info(jobs)")}
            if "headers" not in cols:
                self._con.execute("ALTER TABLE jobs ADD COLUMN headers TEXT")
            # crash recovery: anything active when we died is interrupted
            self._con.execute(
                "UPDATE jobs SET status='interrupted', "
                "error='engine restarted before job finished' "
                "WHERE status IN (?, ?, ?)", ACTIVE_STATUSES,
            )
            for row in self._con.execute("SELECT * FROM jobs"):
                self._jobs[row["id"]] = self._row_to_job(row)

    @staticmethod
    def _row_to_job(row: dict) -> dict:
        job = dict(row)
        job["headers"] = json.loads(job["headers"]) if job.get("headers") else None
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
                "INSERT INTO jobs (id, url, fmt, headers, status, title, filepath,"
                " error, downloaded_bytes, total_bytes, speed, eta, created_at,"
                " completed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
                " title=excluded.title, filepath=excluded.filepath,"
                " error=excluded.error, downloaded_bytes=excluded.downloaded_bytes,"
                " total_bytes=excluded.total_bytes, speed=excluded.speed,"
                " eta=excluded.eta, completed_at=excluded.completed_at",
                (
                    job["id"], job["url"], job.get("fmt"),
                    json.dumps(job["headers"]) if job.get("headers") else None,
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
               extra_headers: dict | None = None) -> dict:
        extra_headers = _safe_headers(extra_headers)
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "url": url,
            "fmt": fmt,
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
                           extra_headers=src.get("headers"))

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
                job["progress"] = {
                    "downloaded_bytes": d.get("downloaded_bytes") or 0,
                    "total_bytes": d.get("total_bytes")
                    or d.get("total_bytes_estimate"),
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                }
                self._save(job)
            elif d["status"] == "finished":
                job["status"] = "merging"
                self._save(job)

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": str(self.download_dir / "%(title).100B.%(ext)s"),
            "progress_hooks": [hook],
            "postprocessor_hooks": [hook],
        }
        if fmt:
            opts["format"] = fmt
        if extra_headers:
            opts["http_headers"] = extra_headers
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(job["url"], download=True)
                info = ydl.sanitize_info(info)
            req = (info.get("requested_downloads") or [{}])[0]
            job["title"] = info.get("title")
            job["filepath"] = req.get("filepath") or info.get("filepath")
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
