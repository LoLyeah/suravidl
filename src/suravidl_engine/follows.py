"""The watch list (v0.46.2 "the follower").

Follow a playlist or channel; new entries arrive on their own. Three
laws hold this together:

- **Following starts from NOW.** Adding a follow seeds every current
  entry as seen, so the first check does not queue a hundred-back
  backlog. The panel says so; surprises are not a feature.
- **Nothing is grabbed twice.** Seen is marked the moment an entry is
  queued (not when it finishes): a failed download is the user's to
  retry, never an automatic re-grab loop. An entry already downloaded
  any other way is marked seen and skipped for good.
- **Checks are polite and bounded.** A per-host minimum gap, a cap on
  new grabs per check, a capped entry listing, and jittered cadence.
  A failed check records its reason on the row and waits its turn.

On Android the engine runs while the app does: checks happen on app
open (catch-up) and via the manual button — no background illusion,
said plainly in the panel.
"""
from __future__ import annotations

import random
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

SCHEMA = """
CREATE TABLE IF NOT EXISTS follows (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    label TEXT,
    cadence_hours REAL DEFAULT 6,
    preset TEXT,
    auto_queue INTEGER DEFAULT 1,
    created_at TEXT,
    last_checked TEXT,
    last_error TEXT,
    last_new INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS follow_seen (
    follow_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    at TEXT,
    PRIMARY KEY (follow_id, video_id)
);
"""

CAP_ENTRIES = 100      # entries looked at per check
CAP_NEW = 25           # new things queued per check, ever
HOST_GAP = 300.0       # seconds between two checks touching one host

# Flat entries from lazy extractors are just {"_type": "url", "url": …} —
# no id, no title. The dedupe key must be DERIVED, or the feature drops
# every entry it exists to follow (found against real yt-dlp, fixture of
# YouTube embeds, 2026-10-10). The same video via watch/embed/shorts
# must fold to one key, and tracking junk must not make keys wobble.
_YT_KEY = re.compile(
    r"(?:youtube\.com/(?:watch\?[^#]*?v=|embed/|shorts/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{6,})")
_TRACKERS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
             "utm_content", "fbclid", "gclid", "igshid", "feature"}


def _key_from_url(url: str) -> str:
    """The dedupe key when the entry has no id of its own."""
    m = _YT_KEY.search(url)
    if m:
        return "yt:" + m.group(1)
    try:
        p = urlparse(url)
    except ValueError:
        return url
    key = f"{(p.hostname or '').lower()}{p.path.rstrip('/')}"
    q = [kv for kv in p.query.split("&")
         if kv and kv.split("=")[0].lower() not in _TRACKERS]
    return key + (("?" + "&".join(q)) if q else "")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def flat_entries(url: str, settings: dict, *, cap: int = CAP_ENTRIES):
    """The playlist page, read FLAT: one light extraction, no downloads.

    Returns (entries, title). Entries are the shape the check needs —
    id, url, title — and anything without an id is not followable.
    """
    import yt_dlp

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": cap,
        "skip_download": True,
    }
    # the auth and routing the settings already carry, so a members-only
    # or proxied playlist checks like it downloads
    if settings.get("cookies_file"):
        opts["cookiefile"] = settings["cookies_file"]
    if settings.get("cookies_from_browser"):
        opts["cookiesfrombrowser"] = (settings["cookies_from_browser"],)
    if settings.get("proxy"):
        opts["proxy"] = settings["proxy"]
    if settings.get("ip_version") and settings["ip_version"] != "auto":
        opts["source_address"] = {"ipv4": "0.0.0.0", "ipv6": "::"}[
            settings["ip_version"]]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    out = []
    for e in info.get("entries") or []:
        if not isinstance(e, dict):
            continue
        eu = str(e.get("url") or e.get("webpage_url")
                 or e.get("original_url") or "").strip()
        if not eu:
            continue
        # a lazy entry has no id of its own: derive the key from its URL
        vid = str(e.get("id") or "").strip() or _key_from_url(eu)
        out.append({"id": vid, "url": eu,
                    "title": str(e.get("title") or "")})
    return out, str(info.get("title") or "")


class FollowStore:
    """The follows table and its seen-set, beside the jobs database."""

    def __init__(self, db_path):
        self._con = sqlite3.connect(str(db_path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._con:
            self._con.executescript(SCHEMA)

    def list(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM follows ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def get(self, fid: str) -> dict | None:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM follows WHERE id = ?", (fid,)).fetchone()
        return dict(row) if row else None

    def add(self, url: str, *, label: str = "", cadence_hours: float = 6.0,
            preset: str | None = None, auto_queue: bool = True,
            seed: list[str] | None = None) -> dict:
        fid = uuid.uuid4().hex[:12]
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO follows (id, url, label, cadence_hours, preset,"
                " auto_queue, created_at, last_checked)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (fid, url, label or url, float(cadence_hours), preset,
                 1 if auto_queue else 0, _now(), _now()))
            for vid in seed or []:
                self._con.execute(
                    "INSERT OR IGNORE INTO follow_seen (follow_id, video_id,"
                    " at) VALUES (?,?,?)", (fid, vid, _now()))
        return self.get(fid)

    def remove(self, fid: str) -> bool:
        with self._lock, self._con:
            cur = self._con.execute("DELETE FROM follows WHERE id = ?", (fid,))
            self._con.execute("DELETE FROM follow_seen WHERE follow_id = ?",
                              (fid,))
        return cur.rowcount > 0

    def seen(self, fid: str, video_id: str) -> bool:
        with self._lock:
            row = self._con.execute(
                "SELECT 1 FROM follow_seen WHERE follow_id = ? AND"
                " video_id = ?", (fid, video_id)).fetchone()
        return row is not None

    def mark_seen(self, fid: str, video_id: str) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT OR IGNORE INTO follow_seen (follow_id, video_id, at)"
                " VALUES (?,?,?)", (fid, video_id, _now()))

    def record(self, fid: str, *, error: str | None = None,
               new: int | None = None) -> None:
        with self._lock, self._con:
            self._con.execute(
                "UPDATE follows SET last_checked = ?,"
                " last_error = ? WHERE id = ?", (_now(), error, fid))
            if new is not None:
                self._con.execute(
                    "UPDATE follows SET last_new = ? WHERE id = ?", (new, fid))


def due(follow: dict, now: float | None = None) -> bool:
    """Is this follow's next check up? Cadence with jitter, so a dozen
    follows created the same evening never march in lockstep."""
    now = now if now is not None else time.time()
    try:
        last = datetime.fromisoformat(follow.get("last_checked") or "")
        last_ts = last.timestamp()
    except ValueError:
        return True
    hours = float(follow.get("cadence_hours") or 6)
    jitter = 0.9 + random.random() * 0.2
    return now >= last_ts + hours * 3600 * jitter


def check_one(follow: dict, store: FollowStore, *, fetch, queue,
              cap_new: int = CAP_NEW) -> dict:
    """One check. `fetch(url) -> (entries, title)` and
    `queue(entry, follow) -> job_id | None` are injected, which is how
    this is tested without a network or a queue.

    Returns {checked, new, queued, error}. A failure is recorded on the
    row (its reason survives until the next attempt) and never raises.
    """
    try:
        entries, _title = fetch(follow["url"])
    except Exception as e:  # noqa: BLE001 - the row carries the reason
        store.record(follow["id"], error=f"check failed: {e}")
        return {"checked": False, "new": 0, "queued": 0, "error": str(e)}

    fresh = []
    for e in entries:
        if len(fresh) >= cap_new:
            break
        if not store.seen(follow["id"], e["id"]):
            fresh.append(e)

    auto = bool(follow.get("auto_queue", 1))
    queued = 0
    for e in fresh:
        if not auto:
            # count only: with auto-grab off the entry stays fresh and
            # keeps being reported until the follow is switched on
            continue
        try:
            job_id = queue(e, follow)
        except Exception:  # noqa: BLE001 - a bad entry must not stop the rest
            job_id = None
        # seen either way: a failed grab is the user's to retry, and an
        # entry already had another way is never re-grabbed
        store.mark_seen(follow["id"], e["id"])
        if job_id:
            queued += 1

    store.record(follow["id"], error=None, new=queued)
    return {"checked": True, "new": len(fresh), "queued": queued, "error": None}


class FollowChecker:
    """The daemon: every poll, run whichever follows are due.

    One host is not asked twice inside HOST_GAP seconds; the engine's
    own lifetime bounds the daemon (it dies with the process — on
    Android that is the app's lifetime, said plainly in the panel).
    """

    def __init__(self, store: FollowStore, fetch, queue, *,
                 poll: float = 60.0, gap: float = HOST_GAP):
        self.store = store
        self.fetch = fetch
        self.queue = queue
        self.poll = poll
        self.gap = gap
        self._host_last: dict[str, float] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="follow-checker")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self.poll):
            try:
                self.run_due()
            except Exception:  # noqa: BLE001 - the daemon never dies loudly
                time.sleep(5)

    def _host_of(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return (urlparse(url).hostname or "").lower()
        except ValueError:
            return ""

    def run_due(self) -> int:
        ran = 0
        now = time.time()
        for f in self.store.list():
            if self._stop.is_set():
                break
            if not due(f, now):
                continue
            host = self._host_of(f["url"])
            if now - self._host_last.get(host, 0) < self.gap:
                continue
            self._host_last[host] = time.time()
            check_one(f, self.store, fetch=self.fetch, queue=self.queue)
            ran += 1
        return ran
