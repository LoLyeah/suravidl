"""Jobs must survive engine restarts (SQLite persistence)."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _wait(mgr, job_id, timeout=30):
    for _ in range(int(timeout * 10)):
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


def test_completed_job_survives_manager_restart(tmp_path, fixture_server):
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    j = _wait(mgr, job["id"])
    assert j["status"] == "completed"

    # "restart": fresh manager over the same db
    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)
    history = {x["id"]: x for x in mgr2.list()}
    assert job["id"] in history
    assert history[job["id"]]["status"] == "completed"
    assert history[job["id"]]["filepath"] == j["filepath"]


def test_incomplete_job_marked_interrupted_after_restart(tmp_path, fixture_server):
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    _wait(mgr, job["id"])

    # simulate a crash mid-job: row left in "downloading"
    import sqlite3

    con = sqlite3.connect(db)
    con.execute("UPDATE jobs SET status='downloading' WHERE id=?", (job["id"],))
    con.commit()
    con.close()

    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)
    j = mgr2.get(job["id"])
    assert j["status"] == "interrupted"
    assert "restart" in j["error"].lower()


def test_failed_job_persists_with_error(tmp_path):
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create("http://127.0.0.1:1/nope.mp4")
    j = _wait(mgr, job["id"])
    assert j["status"] == "error"

    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)
    j2 = mgr2.get(job["id"])
    assert j2["status"] == "error"
    assert j2["error"]


def _seed_stale_downloading(db, job_id):
    import sqlite3

    con = sqlite3.connect(db)
    con.execute("UPDATE jobs SET status='downloading' WHERE id=?", (job_id,))
    con.commit()
    con.close()


def test_auto_resume_requeues_interrupted_jobs(tmp_path, fixture_server):
    """With auto_resume, jobs cut off by a crash restart on their own."""
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    _wait(mgr, job["id"])
    _seed_stale_downloading(db, job["id"])

    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db, auto_resume=True)
    # it must not stay interrupted: it is re-queued/running/completed right away
    assert mgr2.get(job["id"])["status"] != "interrupted"
    j = _wait(mgr2, job["id"])
    assert j["status"] == "completed", j
    assert j["filepath"]


def test_auto_resume_off_keeps_interrupted(tmp_path, fixture_server):
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    _wait(mgr, job["id"])
    _seed_stale_downloading(db, job["id"])

    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)
    j = mgr2.get(job["id"])
    assert j["status"] == "interrupted"


def test_resume_interrupted_returns_ids(tmp_path, fixture_server):
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    _wait(mgr, job["id"])
    _seed_stale_downloading(db, job["id"])

    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)
    assert mgr2.resume_interrupted() == [job["id"]]
    j = _wait(mgr2, job["id"])
    assert j["status"] == "completed", j
