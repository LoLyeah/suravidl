"""Cancel (queued+running) and retry of terminal jobs, incl. headers reuse."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class ThrottledHandler(http.server.SimpleHTTPRequestHandler):
    """Dribbles files out slowly so 'downloading' state is observable."""

    chunk_size = 2048
    delay = 0.08

    def copyfile(self, source, outputfile):
        while True:
            data = source.read(self.chunk_size)
            if not data:
                break
            outputfile.write(data)
            outputfile.flush()
            time.sleep(self.delay)

    def log_message(self, *args):
        pass


class HeaderGateHandler(http.server.SimpleHTTPRequestHandler):
    required_ua = "suravidl-retry-agent/1.0"

    def do_GET(self):
        if self.headers.get("User-Agent") != self.required_ua:
            self.send_error(403, "bad agent")
            return
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def slow_server():
    handler = functools.partial(ThrottledHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def gated_server():
    handler = functools.partial(HeaderGateHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _wait(mgr, job_id, states, timeout=30):
    for _ in range(int(timeout * 10)):
        j = mgr.get(job_id)
        if j["status"] in states:
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


def test_cancel_queued_job(slow_server, tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl", max_concurrent=1)
    blocker = mgr.create(f"{slow_server}/tiny.mp4")  # occupies the only slot
    queued = mgr.create(f"{slow_server}/tiny.mp4")
    assert mgr.get(queued["id"])["status"] == "queued"

    out = mgr.cancel(queued["id"])
    assert out["status"] == "cancelled"
    # blocker keeps running; the cancelled one must never start
    time.sleep(0.5)
    assert mgr.get(queued["id"])["status"] == "cancelled"


def test_cancel_running_job(slow_server, tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl", max_concurrent=1)
    job = mgr.create(f"{slow_server}/tiny.mp4")
    _wait(mgr, job["id"], states=("downloading",), timeout=10)
    out = mgr.cancel(job["id"])
    assert out["status"] == "cancelled"

    final = _wait(mgr, job["id"], states=("cancelled", "error", "completed"),
                  timeout=15)
    assert final["status"] == "cancelled", final


class FlakyHandler(http.server.SimpleHTTPRequestHandler):
    """Fails the first request with 503, serves normally afterwards."""

    first = True

    def do_GET(self):
        if FlakyHandler.first:
            FlakyHandler.first = False
            self.send_error(503, "transient")
            return
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def flaky_server():
    handler = functools.partial(FlakyHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_retry_recovers_transient_failure(tmp_path, flaky_server):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl")
    job = mgr.create(f"{flaky_server}/tiny.mp4")  # first attempt hits the 503
    _wait(mgr, job["id"], states=("error",))

    retried = mgr.retry(job["id"])
    assert retried["id"] != job["id"]
    assert retried["url"] == job["url"]
    final = _wait(mgr, retried["id"], states=("completed", "error"))
    assert final["status"] == "completed", final


def test_retry_reuses_captured_headers(tmp_path, gated_server):
    import sqlite3

    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{gated_server}/tiny.mp4",
                     extra_headers={"User-Agent": HeaderGateHandler.required_ua})
    j = _wait(mgr, job["id"], states=("completed", "error"))
    assert j["status"] == "completed"  # headers worked and were persisted

    # simulate crash: job back to active state, then retry from history
    con = sqlite3.connect(db)
    con.execute("UPDATE jobs SET status='downloading' WHERE id=?", (job["id"],))
    con.commit()
    con.close()
    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)

    j2 = mgr2.retry(job["id"])
    final = _wait(mgr2, j2["id"], states=("completed", "error"))
    # retry only succeeds because the captured UA was persisted and reused
    assert final["status"] == "completed", final


def test_retry_rejects_active_or_completed(tmp_path, slow_server):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl")
    job = mgr.create(f"{slow_server}/tiny.mp4")
    j = _wait(mgr, job["id"], states=("completed", "error"))
    with pytest.raises(ValueError):
        mgr.retry(job["id"])
