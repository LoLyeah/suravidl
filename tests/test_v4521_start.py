"""v0.45.21 "the start" — a claimed job says DOWNLOADING from the start.

Field report (2026-10-08, Android): "Why is it still queued?" — a job
that sat at QUEUED for hours while another completed. The row's status
flipped to 'downloading' only on yt-dlp's first progress event, so a
download stalled in the network layer before its first byte looked
queued for its entire run (the worker had already claimed it). Now
_execute marks the job 'downloading' the moment a worker takes it — a
stalled download is visible, and Cancel/Delete act on truth.

Pins:
- the label flips while yt-dlp is still inside its very first call
  (before any progress event could exist);
- a job still waiting behind the capacity limit stays 'queued' (the
  queued badge must keep meaning "waiting its turn");
- the failure path still lands as an honest error afterwards.
"""
import threading
import time
from pathlib import Path

from suravidl_engine import jobs as jobs_mod
from suravidl_engine.jobs import JobManager


def _wait_for(fn, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    return fn()


def test_a_claimed_job_reads_downloading_before_ytdlp_says_anything(tmp_path, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def fake_extract(opts, url, **kw):
        # standing in for yt-dlp parked inside its first network call —
        # no progress hook has fired, none can while we block here
        entered.set()
        release.wait(5)
        raise RuntimeError("probe: the source never answered")

    monkeypatch.setattr(jobs_mod, "extract_info", fake_extract)
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db",
                     auto_resume=True)
    job = mgr.create("https://example.invalid/slow")

    assert entered.wait(5), "the worker never took the job"
    # the whole point: the row tells the truth BEFORE yt-dlp does
    assert mgr.get(job["id"])["status"] == "downloading"

    release.set()
    final = _wait_for(lambda: mgr.get(job["id"])["status"] == "error")
    assert final, "the stalled download must land as an honest error"
    assert mgr.get(job["id"])["error"]


def test_a_job_waiting_its_turn_still_reads_queued(tmp_path, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def fake_extract(opts, url, **kw):
        if not entered.is_set():
            entered.set()
            release.wait(5)
        raise RuntimeError("probe")

    monkeypatch.setattr(jobs_mod, "extract_info", fake_extract)
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db",
                     auto_resume=True, max_concurrent=1)
    first = mgr.create("https://example.invalid/a")
    assert entered.wait(5)
    second = mgr.create("https://example.invalid/b")
    time.sleep(0.2)  # ample: capacity is full, b cannot be running
    assert mgr.get(first["id"])["status"] == "downloading"
    assert mgr.get(second["id"])["status"] == "queued", \
        "waiting its turn must still read queued"
    release.set()
    # let the worker settle under the monkeypatch — ending the test while
    # it still runs would restore the real extractor and hit the network
    done = _wait_for(lambda: mgr.get(second["id"])["status"] == "error")
    assert done, "the second job must run (and fail, per the probe) after release"
