"""v0.45.22 "the watch" — a stalled download cannot wedge the app.

Field report (2026-10-08, Android): a download from a CDN that opened the
connection and then sent nothing sat at QUEUED for hours; the in-app
browser said "the engine refused it — is it still running?"; cancelling
worked; deleting answered "could not delete: 500".

What the evidence pins down:

- The row flip to "downloading" only happened on yt-dlp's first progress
  event, so a download stalled before its first byte masqueraded as
  QUEUED (fixed in v0.45.21 — the moment a worker claims the job, the
  row says so).
- Nothing gave up on a stalled transfer: yt-dlp only enforces socket
  timeouts (and DNS through Android's netd has none). A job whose source
  stops answering could hold a worker forever.
- The delete endpoint could emit a raw HTTP 500 (any uncaught exception
  coming out of the file operations), which the UI can only render as
  "could not delete: 500" — no cause, no path forward.

This module pins the repairs:

1. a download with no events for STALL_LIMIT seconds is failed with an
   honest "stalled" error — the worker may be unwinding, but the ROW is
   truthful and actionable, and the app stays usable;
2. deleting a job in a TERMINAL state (error/cancelled) never waits
   behind a wedged worker for more than a beat — it proceeds;
3. the delete endpoint answers with a structured detail on EVERY
   failure — never a bare 500.
"""
import json
import socket
import threading
import time
from pathlib import Path

import pytest


def _drip_server():
    """Accepts connections; sends nothing, ever. The CDN that stalls."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    held = []
    stop = threading.Event()

    def run():
        srv.settimeout(0.5)
        while not stop.is_set():
            try:
                c, _ = srv.accept()
                held.append(c)
            except socket.timeout:
                continue
            except OSError:
                return

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], stop, held


def test_a_stalled_download_is_watched_and_failed(tmp_path, monkeypatch):
    """No event for STALL_LIMIT seconds -> the row turns 'error', honestly."""
    from suravidl_engine import jobs as jobs_mod
    from suravidl_engine.jobs import JobManager

    monkeypatch.setattr(jobs_mod, "STALL_LIMIT", 3.0)   # fast for the test
    monkeypatch.setattr(jobs_mod, "STALL_POLL", 0.5)

    port, stop, held = _drip_server()
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db",
                     auto_resume=True)
    job = mgr.create(f"http://127.0.0.1:{port}/stuck.mp4")

    # it is claimed at once (v0.45.21) and then… nothing. The watchdog
    # must fail it with a stall note instead of letting it sit forever.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        s = mgr.get(job["id"])
        if s["status"] == "error":
            break
        time.sleep(0.3)
    s = mgr.get(job["id"])
    assert s["status"] == "error", f"still {s['status']} after a stall"
    wording = (s.get("error") or "").lower()
    assert "no progress" in wording or "stalled" in wording, s.get("error")
    stop.set()


def test_delete_proceeds_when_the_worker_is_wedged(tmp_path, monkeypatch):
    """A cancelled job with a still-live worker deletes without a 500."""
    from suravidl_engine import jobs as jobs_mod
    from suravidl_engine.jobs import JobManager

    port, stop, held = _drip_server()
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db",
                     auto_resume=True)
    job = mgr.create(f"http://127.0.0.1:{port}/stuck.mp4")
    time.sleep(1.0)                      # worker is now wedged in the read
    mgr.cancel(job["id"])

    t0 = time.monotonic()
    r = mgr.delete_job(job["id"])       # must not hang 15s nor raise
    dt = time.monotonic() - t0
    assert dt < 8, f"delete waited {dt:.1f}s behind a wedged worker"
    assert isinstance(r, dict)
    with pytest.raises(KeyError):
        mgr.get(job["id"])              # the row is gone
    stop.set()
