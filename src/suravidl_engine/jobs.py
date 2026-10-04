"""Job manager: background downloads, live progress, SQLite persistence."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from collections import deque
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

from .auth import explain_download_error
from .classify import blocked_reason
from .extract import extract_info

# How many worker threads serve the queue. It equals the settings ceiling for
# `max_concurrent` (1..4, settings.py), so a raised capacity always has a
# worker to use; waiting jobs sit in a deque, not on a thread each (v0.40.0:
# a 20-link batch used to park 20 sleeping threads).
POOL_SIZE = 4

# A ceiling on waiting jobs (v0.43.2 audit): a caller could append to the
# queue forever — the pool stays saturated, the deque (and every job's row)
# does not. Past this, create() refuses and the caller backs off.
MAX_QUEUE = 500

# Bumped when the migration block in `_init_db` changes shape.
SCHEMA_VERSION = 1

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
    completed_at TEXT,
    files TEXT,
    partials TEXT,
    download_dir TEXT
)
"""

ACTIVE_STATUSES = ("queued", "downloading", "merging")


def _stop_requested(job: dict) -> bool:
    """Did the user ask this job to stop — cancel or pause?

    Both share the same cooperative stop: the worker returns at its next
    progress hook, which is also what keeps the partial `.part` file on disk.
    `cancelled` means "I do not want this"; `paused` means "not now, keep the
    bytes" (v0.22.0 feature review #6).
    """
    return job["status"] in ("cancelled", "paused")


def _stat_size(job: dict) -> int | None:
    """Bytes on disk for a job's files — what the expanded queue card shows.

    A single-file row reads its filepath (the record's true size when the
    download is finished — a merged download's `files` also lists the muxed
    fragments, so summing would double-count). A playlist row's filepath is
    a folder, so its finished entries are summed instead. None while nothing
    is on disk (v0.38.2 report: "show us the file size and the location").
    """
    path = job.get("filepath")
    try:
        if path and os.path.isfile(path):
            return os.path.getsize(path)
    except OSError:
        pass
    total, found = 0, False
    for f in job.get("files") or []:
        if f == path:
            continue
        try:
            if os.path.isfile(f):
                total += os.path.getsize(f)
                found = True
        except OSError:
            continue
    return total if found else None

# A URL longer than this is junk, not a link (the audit found the engine
# happily storing 5000 characters of "xxxx…" as a job).
URL_MAX = 4096

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
FORMAT_INTENTS: dict[str, dict] = {
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
    # the v0.22.0 feature review (#9): 192k was the only MP3, and the native
    # Opus / lossless FLAC that YouTube and Bandcamp actually serve had no
    # path except raw arguments. The Android build's ffmpeg already carries
    # the mp3/flac/opus encoders and muxers, so all of these work on a phone.
    "audio-mp3-320": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
             "preferredquality": "320"},
        ],
    },
    "audio-mp3-128": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
             "preferredquality": "128"},
        ],
    },
    "audio-flac": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "flac"},
        ],
    },
    "audio-opus": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "opus"},
        ],
    },
    # v0.29.0: the video side of the same idea. "MP4" here means "this file
    # must open on a TV, an iPhone or WhatsApp": prefer H.264 + AAC streams
    # when the site has them, keep the app's usual capped ladder for the
    # sites that don't, and repackage whatever arrives into an mp4 container
    # (FFmpegVideoRemuxer repacks, it never re-encodes).
    "video-mp4-1080": {
        "format": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080][ext=mp4]"
                  "/bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
    },
    "video-mp4-720": {
        "format": "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/b[height<=720][ext=mp4]"
                  "/bv*[height<=720]+ba/b[height<=720]/b",
        "merge_output_format": "mp4",
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
    },
}


def preset_opts(preset: str | None) -> dict:
    """yt-dlp options for a preset intent; ValueError on unknown names."""
    if not preset:
        return {}
    if preset not in FORMAT_INTENTS:
        raise ValueError(f"unknown preset: {preset!r}")
    spec = FORMAT_INTENTS[preset]
    opts: dict = {"format": spec["format"]}
    if spec.get("merge_output_format"):
        opts["merge_output_format"] = spec["merge_output_format"]
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


# A language tag, BCP-47-shaped: `.en`, `.en-US`, `.zh-Hans`, `.es-419`,
# and yt-dlp's own `.en-orig`. The old `[A-Za-z0-9]{2,}` subtag accepted
# `movie.hd-trailer.srt` as a subtitle of movie.mp4, and the trash button
# deleted a file the job never wrote (v0.43.2 audit). A tag outside this
# shape loses nothing: the sidecar simply stays put.
_LANG_TAG_RE = re.compile(
    r"\.[A-Za-z]{2,3}"
    r"(?:-(?:[A-Za-z]{2}|[0-9]{3}|orig|Hans|Hant|Latn|Cyrl|Arab|Deva|Hebr"
    r"|Jpan|Kore|Thai))*")


def _subtitle_files(info) -> list[str]:
    """Subtitle paths a run really produced — under their FINAL names.

    The srt convertor renames `Name.en.vtt` to `Name.en.srt` (and deletes
    the original); only the final info knows the new name, and no progress
    hook fires for a postprocessor's output — the hook recorded the `.vtt`
    instead (v0.32.1 audit). Keep what is actually on disk.
    """
    out: list[str] = []
    subs = (info or {}).get("requested_subtitles") or {}
    for sub in subs.values():
        fp = (sub or {}).get("filepath")
        if fp and Path(fp).is_file() and str(fp) not in out:
            out.append(str(fp))
    return out


# yt-dlp's wording when a caption track will not download; media failures
# say "video data", so the two never collide (v0.34.0: an m4a job died on a
# subtitles-endpoint 429 before the audio ever started)
_SUB_ERROR_MARK = ("unable to download", "subtitle")


def _is_subtitle_error(e: BaseException) -> bool:
    text = str(e).lower()
    return all(m in text for m in _SUB_ERROR_MARK)


def _subtitle_reason(e: BaseException) -> str:
    """The human half of yt-dlp's subtitle error, for the job row."""
    text = str(e)
    if "subtitle" in text.lower():
        # "…video subtitles for 'en': HTTP Error 429: Too Many Requests"
        tail = text.split("subtitles", 1)[1]
        if ":" in tail:
            text = tail.split(":", 1)[1]
    return text.strip()[:120] or "the site refused them"


def _drop_subtitles(opts: dict) -> None:
    """Strip every subtitle option, so a retry fetches media only."""
    for key in ("writesubtitles", "writeautomaticsub", "subtitleslangs",
                "subtitlesformat"):
        opts.pop(key, None)
    pps = opts.get("postprocessors")
    if pps:
        keep = [p for p in pps
                if p.get("key") not in ("FFmpegSubtitlesConvertor",
                                        "FFmpegEmbedSubtitle")]
        if keep:
            opts["postprocessors"] = keep
        else:
            opts.pop("postprocessors", None)


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
        # ids deleted by the user: a worker finishing (or writing progress) a
        # moment later must not write the row back
        self._deleted: set[str] = set()
        # adaptive concurrency gate: capacity can change at runtime
        self._cap_cv = threading.Condition(threading.Lock())
        self._capacity = max(1, int(max_concurrent))
        self._active = 0
        # queued work, FIFO: (job, fmt, extra_headers), served by the pool
        self._pending: deque = deque()
        # the pool itself: started at the first enqueue, lives with the engine
        self._workers: list[threading.Thread] = []
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
            if self.db_path != ":memory:":
                # WAL: several workers write progress at once, and a reader
                # must never be the one that waits on them; :memory: dbs
                # have no journal to mode. A filesystem that refuses WAL is
                # not worth a failed boot.
                try:
                    self._con.execute("PRAGMA journal_mode=WAL")
                except sqlite3.Error:  # pragma: no cover - fs-dependent
                    pass
            with self._con:
                self._con.executescript(_SCHEMA)
                # versioned migration: carry any older db forward, then
                # stamp it so the checks run at most once per database.
                # Columns gained over time: headers/preset/playlist_items/
                # raw_args/overrides (v0.22.0), files (v0.21.1), partials
                # (v0.26.0), download_dir (v0.21.2).
                version = self._con.execute("PRAGMA user_version").fetchone()[0]
                if version < SCHEMA_VERSION:
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
                    if "files" not in cols:
                        self._con.execute("ALTER TABLE jobs ADD COLUMN files TEXT")
                    if "partials" not in cols:
                        # every target yt-dlp named while downloading (v0.26.0):
                        # a playlist cancelled between entries strands the
                        # in-flight one's `.part` under a name `files` never
                        # learns, and the delete could not find it
                        self._con.execute(
                            "ALTER TABLE jobs ADD COLUMN partials TEXT")
                    if "download_dir" not in cols:
                        # the folder this job downloaded into: a later settings
                        # change must not make its files undeletable (v0.21.2)
                        self._con.execute(
                            "ALTER TABLE jobs ADD COLUMN download_dir TEXT")
                    self._con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                # scrub cookie values persisted by earlier versions
                scrubbed = self._scrub_persisted_cookies()
                # crash recovery: anything active when we died is interrupted
                self._con.execute(
                    "UPDATE jobs SET status='interrupted', "
                    "error='engine restarted before job finished' "
                    "WHERE status IN (?, ?, ?)", ACTIVE_STATUSES,
                )
            if scrubbed:
                if self.db_path != ":memory:":
                    # WAL: the pre-scrub page images still sit in the sidecar;
                    # a truncating checkpoint brings the scrubbed pages home
                    # and empties it, then VACUUM rewrites the file so the old
                    # bytes are gone, not just the row.
                    try:
                        self._con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except sqlite3.Error:  # pragma: no cover - fs-dependent
                        pass
                self._con.execute("VACUUM")
            if self.db_path != ":memory:":
                # the WAL sidecars hold the same private rows as the db
                for suffix in ("-wal", "-shm"):
                    side = Path(self.db_path + suffix)
                    if side.exists():
                        try:
                            os.chmod(side, 0o600)
                        except OSError:
                            pass
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
        files = job.get("files")
        if files:
            try:
                job["files"] = json.loads(files)
            except (json.JSONDecodeError, TypeError):
                job["files"] = None
        else:
            job["files"] = None
        parts = job.get("partials")
        if parts:
            try:
                job["partials"] = json.loads(parts)
            except (json.JSONDecodeError, TypeError):
                job["partials"] = None
        else:
            job["partials"] = None
        job["size_bytes"] = _stat_size(job)
        return job

    def _save(self, job: dict):
        with self._db_lock, self._con:
            # a deleted job must stay deleted: a late write from the worker
            # thread (progress, completion) must not resurrect the row
            if job["id"] in self._deleted:
                return
            self._con.execute(
                "INSERT INTO jobs (id, url, fmt, preset, playlist_items,"
                " raw_args, overrides, headers, status, title,"
                " filepath, error, downloaded_bytes, total_bytes, speed, eta,"
                " created_at, completed_at, files, partials, download_dir)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
                " title=excluded.title, filepath=excluded.filepath,"
                " error=excluded.error, downloaded_bytes=excluded.downloaded_bytes,"
                " total_bytes=excluded.total_bytes, speed=excluded.speed,"
                " eta=excluded.eta, completed_at=excluded.completed_at,"
                " files=excluded.files, partials=excluded.partials,"
                " download_dir=excluded.download_dir",
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
                    json.dumps(job["files"]) if job.get("files") else None,
                    json.dumps(job["partials"]) if job.get("partials") else None,
                    job.get("download_dir") or str(self.download_dir),
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

        # a job with no URL is not a job: it would only fail later, in the
        # worker, with an error nobody can act on (found by the v0.21.1 audit)
        url = (url or "").strip()
        if not url:
            raise ValueError("a job needs a URL")
        if len(url) > URL_MAX:
            raise ValueError(f"that URL is too long (max {URL_MAX} characters)")
        # one judgement, every door (v0.43.2): classify rendered it, but a
        # job could still be created straight for a link-local address
        why = blocked_reason(url)
        if why:
            raise ValueError(why)
        if len(self._pending) >= MAX_QUEUE:
            raise ValueError(
                f"the queue is full ({MAX_QUEUE} waiting) — let some "
                "downloads finish first")

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
            # remember where this job downloaded: deleting it later must work
            # even after the download folder changes (v0.21.2 audit)
            "download_dir": str(self.download_dir),
        }
        with self._lock:
            self._jobs[job_id] = job
        self._save(job)
        self._enqueue(job, fmt, extra_headers)
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = dict(self._jobs[job_id])
        job["size_bytes"] = _stat_size(job)
        return job

    def list(self) -> list[dict]:
        with self._lock:
            jobs = [dict(j) for j in self._jobs.values()]
        # the size on disk is read per call: a listing is how the queue card
        # learns it, and the worker's in-memory dict never stats anything
        # (v0.38.2 — without this the API answered size_bytes: null)
        for j in jobs:
            j["size_bytes"] = _stat_size(j)
        return jobs

    def cancel(self, job_id: str) -> dict:
        """Cancel a queued or running job. Running ones stop at the next hook."""
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] not in ACTIVE_STATUSES:
                raise ValueError(f"cannot cancel job in status '{job['status']}'")
            job["status"] = "cancelled"  # queued jobs never start; running see below
        self._save(job)
        return self.get(job_id)

    def pause(self, job_id: str) -> dict:
        """Stop a running job *without* discarding what it already has.

        It is the same cooperative stop cancel uses (the worker returns at its
        next progress hook, which is what keeps the `.part` file on disk), but
        it is recorded as `paused` so the row can be resumed instead of
        retried. Cancel means "I do not want this"; pause means "not now"
        (v0.22.0 feature review #6).
        """
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] not in ACTIVE_STATUSES:
                raise ValueError(f"cannot pause job in status '{job['status']}'")
            job["status"] = "paused"
        self._save(job)
        return self.get(job_id)

    def resume(self, job_id: str) -> dict:
        """Continue a paused job: a new row that reuses the partial file."""
        src = self.get(job_id)
        if src["status"] != "paused":
            raise ValueError(f"cannot resume job in status '{src['status']}'")
        return self._requeue(src)

    def retry(self, job_id: str,
              patch: dict | None = None) -> dict:
        """Re-run a terminal job as a new one, optionally with edits.

        `patch` may carry {fmt, preset, overrides, raw_args}: a site that
        answered 403 for one format often works with another, and re-running
        the exact same failing request just loops (v0.22.0 review #11).
        """
        src = self.get(job_id)
        if src["status"] not in ("error", "interrupted", "cancelled", "paused"):
            raise ValueError(f"cannot retry job in status '{src['status']}'")
        return self._requeue(src, patch)

    def _requeue(self, src: dict, patch: dict | None = None) -> dict:
        """Create a new job from an old row, with optional edits applied.

        A row keeps one lane — a preset or a raw format, never both (`create`
        refuses that) — so an edit that names one clears the other instead of
        handing `create` a contradiction (v0.32.1 audit). A preset that
        expands to no intent (a pure bundle) clears the lane just the same.
        """
        patch = dict(patch or {})
        overrides = {**(src.get("overrides") or {}),
                     **(patch.get("overrides") or {})} or None
        fmt = patch.get("fmt", src.get("fmt"))
        preset = patch.get("preset", src.get("preset"))
        if "fmt" in patch and "preset" not in patch:
            preset = None               # a raw format asked for by name
        if "preset" in patch and "fmt" not in patch:
            fmt = None
        job = self.create(src["url"],
                          fmt=fmt,
                          extra_headers=patch.get("headers", src.get("headers")),
                          preset=preset,
                          playlist_items=src.get("playlist_items"),
                          raw_args=patch.get("raw_args", src.get("raw_args")),
                          overrides=overrides)
        # The successor owns everything on disk now: the source row keeps its
        # story (error, progress) but loses its claim on files — trashing the
        # stale card later must not take the successor's finished download
        # with it (v0.40.10 audit; pause→resume reproduced the data loss).
        live = None
        with self._lock:
            live = self._jobs.get(src["id"])
            if live is not None:
                live["filepath"] = None
                live["partials"] = None
                live["files"] = None
        if live is not None:
            self._save(live)
        return job

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
            # the same rule as deleting one row: the DB work happens under the
            # database lock, and the ids join `_deleted` in that same section
            # so a write that was already in flight cannot bring a cleared row
            # back (`_save` checks that set under the same lock)
            with self._db_lock, self._con:
                self._deleted.update(gone)
                self._con.execute(
                    "DELETE FROM jobs WHERE status = 'completed'")
        return len(gone)

    # -- deleting one download (the trash button) -------------------------
    SIDECAR_SUFFIXES = (".info.json", ".description", ".annotations.xml",
                        ".jpg", ".jpeg", ".png", ".webp", ".vtt", ".srt",
                        ".ass", ".lrc", ".json", ".live_chat.json")
    # the sidecars that carry language tags (`Name.en.vtt`): see the tagged
    # pass in `_sidecars_for`
    SUBTITLE_SUFFIXES = (".vtt", ".srt", ".ass", ".lrc")

    def _require_inside(self, path: Path, job: dict | None = None) -> None:
        """A job row is not a licence to delete arbitrary paths.

        Allowed: anything inside the engine's current download folder, or
        inside the folder the job was created under (`job["download_dir"]`).
        The second root matters because changing the download folder in
        Settings used to make every earlier download undeletable — the file
        was "outside the download folder" for ever after (v0.21.2 audit).
        """
        roots = [Path(self.download_dir)]
        recorded = (job or {}).get("download_dir")
        if recorded:
            roots.append(Path(str(recorded)))
        try:
            resolved = path.resolve()
        except OSError:
            resolved = None
        for root in roots:
            try:
                if resolved is not None and resolved.is_relative_to(root.resolve()):
                    return
            except OSError:
                continue
        raise PermissionError(
            f"refusing to use {path}: it is outside the download folder")

    def _sidecars_for(self, path: Path) -> list[Path]:
        out: list[Path] = []
        for suffix in self.SIDECAR_SUFFIXES:
            sidecar = path.with_name(path.stem + suffix)
            if sidecar.exists() and sidecar.is_file() and sidecar != path:
                out.append(sidecar)
        # Language-tagged subtitles share no stem with the video: yt-dlp
        # writes `Name.en.vtt`, and the srt convertor leaves only the renamed
        # `Name.en.srt` — the hook only ever saw the `.vtt`, so deleting the
        # job left the `.srt` behind (v0.32.1 audit). One directory pass; the
        # tag must look like a language, so `Name.2.vtt` is left alone.
        try:
            entries = list(path.parent.iterdir())
        except OSError:
            return out
        stem = path.stem
        for cand in entries:
            if cand == path or cand in out or not cand.is_file():
                continue
            name = cand.name
            if not name.startswith(stem):
                continue
            for suffix in self.SUBTITLE_SUFFIXES:
                if name.endswith(suffix):
                    if _LANG_TAG_RE.fullmatch(name[len(stem):-len(suffix)]):
                        out.append(cand)
                    break
        return out

    def _partials_for(self, path: Path) -> list[Path]:
        """yt-dlp's work-in-progress files hang off the FULL name, not the
        stem: `clip.mp4` in flight is `clip.mp4.part` (and `.ytdl`). The
        v0.21.2 audit found cancelled downloads keeping both forever."""
        out: list[Path] = []
        for suffix in (".part", ".ytdl", ".part-Frag0", ".temp"):
            cand = path.with_name(path.name + suffix)
            if cand.exists() and cand.is_file():
                out.append(cand)
        return out

    def _job_file_targets(self, job: dict) -> list[Path]:
        """The files a job owns: its path plus sidecars sharing its stem.

        A playlist job's filepath is the download *folder*, so what it owns is
        the list it recorded while downloading (`files`) — never whatever
        happens to be in that folder. The v0.21.1 audit found the trash button
        on a playlist row deleting every other job's downloads; a row from
        before per-file tracking deletes nothing (the note in `delete_job`
        says so) rather than emptying a shared folder.
        """
        listed = [Path(str(p)) for p in (job.get("files") or []) if p]
        raw = job.get("filepath")
        if raw and not listed:
            path = Path(str(raw))
            if not path.is_dir():
                listed = [path]
        parts = [Path(str(p)) for p in (job.get("partials") or []) if p]
        if not listed and not parts:
            return []
        out: list[Path] = []
        for p in listed:
            self._require_inside(p, job)
            if p.is_file():
                out.append(p)
                out.extend(self._sidecars_for(p))
            out.extend(self._partials_for(p))
        # the entries `files` never learned: a cancelled playlist's in-flight
        # target lives only in `partials`, and its `.part` is exactly what a
        # delete must not leave behind (v0.26.0)
        for p in parts:
            self._require_inside(p, job)
            out.extend(self._partials_for(p))
        return out

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
        # a playlist that wrote into its own subfolder leaves it behind empty;
        # only a parent strictly INSIDE one of the roots is fair game — the
        # roots themselves are never removed, or a Settings folder change
        # would let deleting a job take the previous download folder with it
        # (v0.32.1 audit, extending the v0.21.2 fix below)
        roots = []
        for r in (Path(self.download_dir), job.get("download_dir")):
            if not r:
                continue
            try:
                resolved_root = Path(str(r)).resolve()
            except OSError:
                continue
            if resolved_root not in roots:
                roots.append(resolved_root)
        for p in {t.parent for t in targets}:
            # resolve BOTH sides: with a relative download_dir (or a symlinked
            # one) the unresolved parent never compared equal to the resolved
            # root, so this removed the download folder itself (v0.21.2 audit)
            try:
                p_resolved = p.resolve()
            except OSError:
                continue
            if any(p_resolved == r for r in roots):
                continue                    # a root itself: never remove it
            if not any(p_resolved.is_relative_to(r) for r in roots):
                continue                    # outside every root: not ours
            try:
                p_resolved.rmdir()
            except OSError:
                pass
        note = None
        if not targets and job.get("filepath"):
            if Path(str(job["filepath"])).is_dir() and not job.get("files"):
                note = ("files kept: this row predates per-file tracking, so "
                        "only the row was removed — clean the folder in "
                        "Settings when you want it gone")
        with self._lock:
            self._jobs.pop(job_id, None)
        # The row goes under the database lock, and `_deleted` is stamped in the
        # same section: `_save` (the worker thread) checks that set under the
        # same lock, so a late write can neither commit in the middle of this
        # transaction — `sqlite3.OperationalError: cannot commit - no
        # transaction is active`, which is how CI caught this on Python 3.10 —
        # nor slip past the check and bring the row back.
        with self._db_lock, self._con:
            self._deleted.add(job_id)
            self._con.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        out = {"deleted": deleted, "freed_bytes": freed,
               "filepath": job.get("filepath")}
        if note:
            out["note"] = note
        return out

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
            self._enqueue(job, job.get("fmt"), job.get("headers"))
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

    def _ensure_workers(self) -> None:
        """Start the pool once, at the first queued job."""
        with self._lock:
            if self._workers:
                return
            for i in range(POOL_SIZE):
                t = threading.Thread(target=self._worker_loop,
                                     name=f"suravidl-job-{i}", daemon=True)
                t.start()
                self._workers.append(t)

    def _enqueue(self, job: dict, fmt: str | None,
                 extra_headers: dict | None) -> None:
        """Hand a job to the pool: one deque entry, no thread of its own."""
        self._ensure_workers()
        with self._cap_cv:
            self._pending.append((job, fmt, extra_headers))
            self._cap_cv.notify_all()

    def _run(self, job: dict, fmt: str | None, extra_headers: dict | None) -> None:
        """One job, one call — the seam the pool invokes per queued item
        (tests stub it to keep the network out of their fixtures)."""
        self._execute(job, fmt, extra_headers)

    def _worker_loop(self) -> None:
        """One pool thread: take the next queued job when a slot is free."""
        while True:
            with self._cap_cv:
                while not (self._pending
                           and self._active < self._capacity):
                    self._cap_cv.wait()
                job, fmt, extra_headers = self._pending.popleft()
                self._active += 1
            try:
                self._run(job, fmt, extra_headers)
            except Exception:  # noqa: BLE001 - a worker must survive a bad job
                pass
            finally:
                with self._cap_cv:
                    self._active -= 1
                    self._cap_cv.notify_all()

    def _execute(self, job: dict, fmt: str | None, extra_headers: dict | None):
        if _stop_requested(job):  # cancelled or paused while queued
            return

        class _Cancelled(Exception):
            pass

        def hook(d):
            if _stop_requested(job):  # stop requested mid-run
                raise _Cancelled()
            d_info = d.get("info_dict") or {}
            # Record the target as soon as yt-dlp names it. A cancelled or
            # failed download used to keep `filepath = None`, so deleting the
            # row left its `.part` (and every playlist entry already written)
            # on disk forever (v0.21.2 audit).
            name = d.get("filename")
            if name:
                if not job.get("filepath"):
                    job["filepath"] = str(name)
                if str(name) not in (job.get("partials") or []):
                    # every target yt-dlp has named this run. A playlist runs
                    # its entries one at a time, and a cancel can strand the
                    # current one's `.part` under a name `files` never learns
                    # (only finished entries land there) — the delete used to
                    # leave exactly that file behind (v0.26.0, found by a
                    # random-order suite run).
                    job["partials"] = [*(job.get("partials") or []), str(name)]
                if d["status"] == "finished":
                    made = list(job.get("files") or [])
                    if str(name) not in made:
                        made.append(str(name))
                        job["files"] = made
            if d["status"] == "downloading":
                job["status"] = "downloading"
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
            opts["format"] = p.pop("format")
            preset_pps = list(p.pop("postprocessors", None) or [])
            opts.update(p)   # e.g. merge_output_format on the mp4 intents
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
        # no_audio (per-download): the shells pair a video-only pick with the
        # site's audio by default; this override keeps it silent. It applies
        # to what the app controls — a stream that carries its own audio is
        # left alone — and a bare "best" pairs nothing at all (2026-09-27).
        if (job.get("overrides") or {}).get("no_audio"):
            if "format" not in opts:
                opts["format"] = "bv/b"
            else:
                from .download_opts import strip_audio_pairing

                opts["format"] = strip_audio_pairing(opts["format"])
        if extra_headers:
            opts["http_headers"] = extra_headers
        try:
            subs_skipped = None
            with (self._cookie_session() if self._cookie_session
                  else nullcontext()) as cookie_opts:
                if cookie_opts:
                    opts.update(cookie_opts)
                try:
                    info = extract_info(opts, job["url"], download=True, retry_refresh=True) or {}
                except Exception as e:  # noqa: BLE001 — classified below
                    # a subtitle sidecar is not the download: when the site
                    # refuses to serve captions (YouTube throttles them hard),
                    # retry once without them instead of losing the media
                    if not _is_subtitle_error(e):
                        raise
                    subs_skipped = _subtitle_reason(e)
                    _drop_subtitles(opts)
                    info = extract_info(opts, job["url"], download=True, retry_refresh=True) or {}
            if subs_skipped:
                job["note"] = (f"subtitles could not be fetched ({subs_skipped})"
                               " — downloaded without them")
            if (info or {}).get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if e]
                job["title"] = info.get("title") or "playlist"
                job["filepath"] = str(self.download_dir)
                job["playlist_count"] = len(entries)
                # the folder holds everyone's downloads: remember the ones this
                # job made, so deleting it takes its own files (v0.21.1 audit).
                # Keep what the hook already recorded — a run that was
                # interrupted and retried must not forget earlier entries.
                made = list(job.get("files") or [])
                for e in entries:
                    req = (e.get("requested_downloads") or [{}])[0]
                    fp = req.get("filepath") or e.get("filepath")
                    if fp and str(fp) not in made:
                        made.append(str(fp))
                    for sub_fp in _subtitle_files(e):
                        if sub_fp not in made:
                            made.append(sub_fp)
                job["files"] = made or None
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
                # the finished file (after any conversion) is what the row
                # owns; the hook may also have recorded the pre-conversion
                # name, which is fine — a missing target is skipped on delete
                made = list(job.get("files") or [])
                if str(job["filepath"]) not in made:
                    made.append(str(job["filepath"]))
                for sub_fp in _subtitle_files(info):
                    if sub_fp not in made:
                        made.append(sub_fp)
                job["files"] = made
            with self._lock:
                if _stop_requested(job):
                    # a cancel (or pause) that landed while yt-dlp was finishing
                    # is still a stop: claiming "completed" (and firing the
                    # completion action) would contradict the user (v0.21.2)
                    return
                job["status"] = "completed"
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
        except _Cancelled:
            if not _stop_requested(job):   # keep the word the user asked for
                job["status"] = "cancelled"
            job["error"] = ("paused by user" if job["status"] == "paused"
                            else "cancelled by user")
        except Exception as e:  # noqa: BLE001 - surfaced to the UI
            if _stop_requested(job):  # raced with cancel/pause
                job["error"] = ("paused by user" if job["status"] == "paused"
                                else "cancelled by user")
            else:
                job["status"] = "error"
                job["error"] = explain_download_error(str(e))
        finally:
            self._save(job)
        if job["status"] == "completed" and self.on_complete:
            try:
                self.on_complete(job)
            except Exception:  # noqa: BLE001 - a hook must never kill a job
                pass
