"""Security: cookie values and secrets must never sit readable at rest."""
import functools
import http.server
import os
import sqlite3
import stat
import threading
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
COOKIE_NAME = "session"
COOKIE_VALUE = "supersecret123"


class EchoHandler(http.server.SimpleHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        type(self).seen.append(self.headers.get("Cookie", ""))
        super().do_GET()


@pytest.fixture()
def echo_server():
    EchoHandler.seen = []
    handler = functools.partial(EchoHandler, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", EchoHandler.seen
    srv.shutdown()


def _wait(mgr, job_id, timeout=30):
    deadline = time.time() + timeout
    j = None
    while time.time() < deadline:
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error", "interrupted", "cancelled"):
            return j
        time.sleep(0.2)
    return j


def test_temp_cookie_copy_is_private(tmp_path):
    from suravidl_engine.auth import cookie_session

    src = tmp_path / "cookies.txt"
    src.write_text("# Netscape HTTP Cookie File\n"
                   "127.0.0.1\tFALSE\t/\tFALSE\t2000000000\tk\tv\n")
    with cookie_session({"cookies_file": str(src),
                         "cookies_from_browser": ""}) as opts:
        copy = Path(opts["cookiefile"])
        mode = stat.S_IMODE(os.stat(copy).st_mode)
        dmode = stat.S_IMODE(os.stat(copy.parent).st_mode)
    assert mode == 0o600, oct(mode)
    assert dmode == 0o700, oct(dmode)


def test_jobs_db_never_stores_cookie_values(tmp_path, echo_server):
    """The job DB on disk must not contain the cookie after a download."""
    from suravidl_engine.jobs import JobManager

    url, seen = echo_server
    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create(f"{url}/tiny.mp4",
                     extra_headers={"Cookie": f"{COOKIE_NAME}={COOKIE_VALUE}",
                                    "User-Agent": "ua/1.0"})
    j = _wait(mgr, job["id"])
    assert j["status"] == "completed", j
    # the download really did carry the cookie
    assert any(COOKIE_VALUE in c for c in seen), seen
    # ... but the db file does not, even as raw bytes
    assert COOKIE_VALUE.encode() not in db.read_bytes()
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600


def test_restart_scrubs_cookie_rows_from_older_versions(tmp_path):
    """Rows written by ≤0.10.0 carried cookies; opening the db must scrub them."""
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db)
    job = mgr.create("http://example.invalid/x.mp4",
                     extra_headers={"Cookie": f"{COOKIE_NAME}={COOKIE_VALUE}"})
    # simulate an old version: write the raw cookie straight into the db
    con = sqlite3.connect(db)
    con.execute("UPDATE jobs SET headers=? WHERE id=?",
                (f'{{"Cookie": "{COOKIE_NAME}={COOKIE_VALUE}"}}', job["id"]))
    con.commit()
    con.close()
    assert COOKIE_VALUE.encode() in db.read_bytes()

    mgr2 = JobManager(download_dir=tmp_path / "dl", db_path=db)
    assert COOKIE_VALUE.encode() not in db.read_bytes()
    # the job survives with the cookie dropped entirely (not a placeholder)
    assert mgr2.get(job["id"])["headers"] in (None, {})


def test_api_never_returns_cookie_values(tmp_path, echo_server):
    from fastapi.testclient import TestClient

    from suravidl_engine.api import create_app

    url, _ = echo_server
    c = TestClient(create_app(download_dir=tmp_path / "dl", auth_token="t",
                              db_path=tmp_path / "jobs.db"))
    auth = {"Authorization": "Bearer t"}
    r = c.post("/jobs", headers=auth, json={
        "url": f"{url}/tiny.mp4",
        "headers": {"Cookie": f"{COOKIE_NAME}={COOKIE_VALUE}"}})
    assert r.status_code == 200
    assert COOKIE_VALUE not in r.text
    assert COOKIE_VALUE not in c.get("/jobs", headers=auth).text
    assert COOKIE_VALUE not in c.get(f"/jobs/{r.json()['id']}", headers=auth).text


def test_in_session_retry_keeps_using_the_cookie(tmp_path, echo_server):
    """Redaction is at-rest + API only — the live job still authenticates."""
    from suravidl_engine.jobs import JobManager

    url, seen = echo_server
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    # 404 -> job errors (retryable), but the cookie is still sent on the way in
    job = mgr.create(f"{url}/missing.mp4",
                     extra_headers={"Cookie": f"{COOKIE_NAME}={COOKIE_VALUE}"})
    j = _wait(mgr, job["id"])
    assert j["status"] == "error", j
    assert any(COOKIE_VALUE in c for c in seen), seen
    seen.clear()
    mgr.retry(job["id"])          # retry reuses the in-memory headers
    deadline = time.time() + 20
    while not seen and time.time() < deadline:
        time.sleep(0.1)
    assert any(COOKIE_VALUE in c for c in seen), seen


def test_token_and_settings_files_are_private(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from suravidl_engine.__main__ import load_or_create_token
    from suravidl_engine.settings import Settings

    tok = load_or_create_token()
    assert tok
    tp = tmp_path / ".suravidl" / "token"
    assert stat.S_IMODE(os.stat(tp).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tp.parent).st_mode) == 0o700

    s = Settings(path=tmp_path / ".suravidl" / "settings.json",
                 default_download_dir=tmp_path / "dl")
    s.update({"max_concurrent": 3})
    assert stat.S_IMODE(os.stat(s.path).st_mode) == 0o600
