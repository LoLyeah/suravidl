"""Job manager: background downloads with live progress."""
import threading
import uuid
from pathlib import Path

import yt_dlp


class JobManager:
    def __init__(self, download_dir, max_concurrent: int = 2):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._threads: dict[str, threading.Thread] = {}

    # -- public API -------------------------------------------------------
    def create(self, url: str, fmt: str | None = None,
               extra_headers: dict | None = None) -> dict:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "url": url,
            "status": "queued",  # queued|downloading|merging|completed|error
            "title": None,
            "filepath": None,
            "error": None,
            "progress": {"downloaded_bytes": 0, "total_bytes": None,
                         "speed": None, "eta": None},
        }
        with self._lock:
            self._jobs[job_id] = job
        t = threading.Thread(target=self._run, args=(job, fmt, extra_headers),
                             daemon=True)
        with self._lock:
            self._threads[job_id] = t
        t.start()
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._lock:
            return dict(self._jobs[job_id])

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(j) for j in self._jobs.values()]

    # -- worker -----------------------------------------------------------
    def _run(self, job: dict, fmt: str | None, extra_headers: dict | None):
        with self._slots:
            self._execute(job, fmt, extra_headers)

    def _execute(self, job: dict, fmt: str | None, extra_headers: dict | None):
        def hook(d):
            if d["status"] == "downloading":
                job["status"] = "downloading"
                job["progress"] = {
                    "downloaded_bytes": d.get("downloaded_bytes") or 0,
                    "total_bytes": d.get("total_bytes")
                    or d.get("total_bytes_estimate"),
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                }
            elif d["status"] == "finished":
                job["status"] = "merging"

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
        except Exception as e:  # noqa: BLE001 - surfaced to the UI
            job["status"] = "error"
            job["error"] = str(e)
