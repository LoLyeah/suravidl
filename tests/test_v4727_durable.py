"""v0.47.27 "the flush" — a terminal state is on disk before it is visible.

The failure that started this: `test_failed_job_persists_with_error` saw
`interrupted` where the job had errored. `_wait` reads the in-memory dict, so
a status assigned there is visible immediately — while the row was still
`downloading` until the `finally` block saved it. A JobManager constructed in
that window sweeps active rows to `interrupted`, and the failure is gone.

The invariant: the row is written from a snapshot BEFORE the shared dict is
updated. This test proves the ordering by watching the dict at save time.
"""
import pathlib
import sqlite3
import time

from suravidl_engine import __version__
from suravidl_engine.jobs import JobManager
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["title"].lower() == "the flush" for e in ENTRIES)


def _wait(mgr, job_id, timeout=30):
    for _ in range(int(timeout * 10)):
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


def test_the_row_is_written_before_the_dict_changes(tmp_path):
    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    seen = []
    real = mgr._save

    def spy(job):
        # what the rest of the process can see at the moment of the write
        live = mgr.get(job["id"])["status"]
        seen.append((job["status"], live))
        return real(job)

    mgr._save = spy
    job = mgr.create("http://127.0.0.1:1/nope.mp4")
    j = _wait(mgr, job["id"])
    assert j["status"] == "error"

    terminal = [(saved, live) for saved, live in seen
                if saved in ("error", "cancelled", "completed")]
    assert terminal, "the terminal state never reached _save"
    ordered = [(saved, live) for saved, live in terminal if live != saved]
    assert ordered, (
        "every terminal save happened after the dict already showed it — "
        "a second manager could sweep the row to 'interrupted' first")
    saved, live_at_write = ordered[0]
    assert live_at_write in ("queued", "downloading", "paused")


def test_a_manager_opened_right_after_the_end_state_reads_the_same(tmp_path):
    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create("http://127.0.0.1:1/nope.mp4")
    j = _wait(mgr, job["id"])
    assert j["status"] == "error"

    row = sqlite3.connect(db).execute(
        "SELECT status, error FROM jobs WHERE id=?", (job["id"],)).fetchone()
    assert row[0] == "error", "the row still said %r when the job was already over" % row[0]
    assert row[1]


def test_every_terminal_transition_goes_through_the_helper():
    """No terminal status may be assigned to the shared dict directly."""
    for line in JOBS.splitlines():
        stripped = line.strip()
        for terminal in ('"completed"', '"error"', '"cancelled"'):
            if stripped.startswith('job["status"] = ' + terminal):
                assert False, "terminal status must go through _publish_terminal: " + stripped
