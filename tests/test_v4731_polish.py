"""v0.47.31 "the polish" — nine small improvements from the Argon review.

None of these is a feature: a poll that respects an idle queue, a size that is
not re-stat-ed every 1.2s, a cancelled job that stops claiming the running
lamp, a split that keeps its sidecars and its second audio track, a button
that obeys the empty-field rule, a dialog Escape covers generically, a sub-nav
with real arrow keys, and a storage-full message a user can act on.
"""
import functools
import http.server
import json
import pathlib
import threading
import time

import pytest

from suravidl_engine import __version__, jobs
from suravidl_engine.jobs import JobManager
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()
JOBS_SRC = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["title"].lower() == "the polish" for e in ENTRIES)


def test_a_settled_size_is_not_stat_ed_on_every_poll(tmp_path, monkeypatch):
    calls = []
    real = jobs._stat_size

    def spy(job):
        calls.append(job.get("id"))
        return real(job)

    monkeypatch.setattr(jobs, "_stat_size", spy)
    (tmp_path / "dl").mkdir(parents=True)
    f = tmp_path / "dl" / "a.mp4"
    f.write_bytes(b"12345")
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    mgr._jobs["j1"] = {"id": "j1", "url": "u", "status": "completed",
                       "filepath": str(f), "files": [str(f)], "overrides": {},
                       "progress": {"downloaded_bytes": 5, "total_bytes": 5,
                                    "speed": 0, "eta": 0}}
    first = mgr.list()[0]["size_bytes"]
    second = mgr.list()[0]["size_bytes"]
    assert first == second == 5
    assert calls == ["j1"], "a finished row was stat-ed twice"


def test_a_split_keeps_its_sidecars(tmp_path):
    assert "SIDECAR_SUFFIXES" in JOBS_SRC
    body = JOBS_SRC[JOBS_SRC.index("def _apply_finish_meta"):]
    body = body[:body.index("def _retitle")]
    assert "SIDECAR_SUFFIXES" in body, "sidecars are dropped from job.files on split"
    assert '"-map", "0"' in JOBS_SRC.split("def _split_chapters")[1]


def test_cancelled_is_not_running():
    assert 'stopped: ["cancelled", "paused"]' in APP
    assert 'if (QUEUE_BUCKETS.stopped.includes(status)) return "stopped";' in APP
    assert 'counts.error] = 0, stopped: 0' not in APP  # the map is written explicitly
    assert 'stopped: 0 }' in APP


def test_the_state_line_only_rebuilds_when_it_changes():
    body = APP[APP.index('const st = $("queueState");'):]
    body = body[:body.index("const box = $(\"queueActions\")")]
    assert "st.dataset.sig" in body and "st.replaceChildren()" in body


def test_download_now_obeys_an_empty_field():
    assert 'if ($("quickBtn")) $("quickBtn").disabled = empty;' in APP


def test_the_poll_backs_off_when_idle():
    assert "const JOBS_ACTIVE_MS = 1200, JOBS_IDLE_MS = 10000;" in APP
    assert "function scheduleJobsPoll(" in APP
    assert "scheduleJobsPoll(JOBS_ACTIVE_MS);" in APP
    assert "setInterval(refreshJobs, 1200)" not in APP


def test_sub_tabs_take_arrow_keys():
    body = APP[APP.index('for (const b of document.querySelectorAll(".subbtn"))'):]
    body = body[:body.index("if ($(\"url\"))")]
    assert 'e.key === "ArrowRight"' in body and 'e.key === "ArrowLeft"' in body
    assert "b.tabIndex = b.classList.contains(\"on\") ? 0 : -1;" in body


def test_escape_closes_any_dialog():
    assert 'const openCards = [...document.querySelectorAll(".overlay:not(.hidden)")]' in APP
    assert "closeModal(openCards[openCards.length - 1]);" in APP
    assert 'm !== $("whatsNewModal")' in APP      # its own branch records "seen"


def test_out_of_storage_has_a_sentence():
    body = APP[APP.index("function humanErr"):]
    body = body[:body.index("\n}\n") + 3]
    assert "no space left|errno 28" in body
    assert "out of storage" in body
