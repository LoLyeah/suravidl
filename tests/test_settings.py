"""Settings API: defaults, persistence, validation, live effects."""
import http.server
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer t"}


class SlowHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(FIXTURES), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        time.sleep(0.8)
        super().do_GET()


@pytest.fixture()
def fixture_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def make_app(tmp_path, **kw):
    return create_app(download_dir=tmp_path / "dl", auth_token="t",
                      db_path=tmp_path / "jobs.db", **kw)


def test_settings_defaults(tmp_path):
    c = TestClient(make_app(tmp_path))
    s = c.get("/settings", headers=AUTH).json()
    assert s["max_concurrent"] == 2
    assert s["open_dir_on_complete"] is False
    assert s["auto_resume"] is True
    assert s["download_dir"] == str(tmp_path / "dl")
    assert s["theme"] == "dark"
    assert s["glass"] == "frosted"


def test_theme_and_glass_validation(tmp_path):
    c = TestClient(make_app(tmp_path))
    # valid values round-trip and persist
    r = c.post("/settings", headers=AUTH,
               json={"theme": "amoled", "glass": "liquid"})
    assert r.status_code == 200
    assert r.json()["theme"] == "amoled"
    assert r.json()["glass"] == "liquid"
    c2 = TestClient(make_app(tmp_path))
    s2 = c2.get("/settings", headers=AUTH).json()
    assert s2["theme"] == "amoled" and s2["glass"] == "liquid"
    # light is valid too
    assert c.post("/settings", headers=AUTH,
                  json={"theme": "light"}).json()["theme"] == "light"
    # junk is rejected
    assert c.post("/settings", headers=AUTH,
                  json={"theme": "neon"}).status_code == 400
    assert c.post("/settings", headers=AUTH,
                  json={"glass": "bubbly"}).status_code == 400


def test_settings_update_persist_and_validate(tmp_path):
    c = TestClient(make_app(tmp_path))
    new_dir = tmp_path / "elsewhere"
    r = c.post("/settings", headers=AUTH, json={
        "download_dir": str(new_dir), "max_concurrent": 3,
        "open_dir_on_complete": True})
    assert r.status_code == 200
    assert r.json()["max_concurrent"] == 3

    # persisted across a fresh app on the same db path
    c2 = TestClient(make_app(tmp_path))
    s2 = c2.get("/settings", headers=AUTH).json()
    assert s2["download_dir"] == str(new_dir)
    assert s2["open_dir_on_complete"] is True

    # validation
    assert c.post("/settings", headers=AUTH,
                  json={"nope": 1}).status_code == 400
    assert c.post("/settings", headers=AUTH,
                  json={"download_dir": "relative/path"}).status_code == 400
    assert c.post("/settings", headers=AUTH,
                  json={"max_concurrent": 99}).json()["max_concurrent"] == 4


def test_download_dir_change_applies_to_new_jobs(tmp_path, fixture_server):
    c = TestClient(make_app(tmp_path))
    new_dir = tmp_path / "moved"
    c.post("/settings", headers=AUTH, json={"download_dir": str(new_dir)})
    job = c.post("/jobs", headers=AUTH,
                 json={"url": f"{fixture_server}/tiny.mp4"}).json()
    deadline = time.time() + 30
    while time.time() < deadline:
        j = c.get(f"/jobs/{job['id']}", headers=AUTH).json()
        if j["status"] in ("completed", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "completed", j
    assert str(new_dir) in j["filepath"]
    assert (new_dir / "tiny.mp4").exists()


def test_max_concurrent_change_applies_live(tmp_path):
    """The concurrency gate must wake waiters when capacity is raised."""
    import threading as _t

    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl", db_path=None,
                     max_concurrent=1)
    started: list[str] = []
    release = _t.Event()

    def fake_execute(job, fmt, headers):
        started.append(job["id"])
        release.wait(timeout=10)

    mgr._execute = fake_execute
    mgr.create("http://example.invalid/1.mp4")
    mgr.create("http://example.invalid/2.mp4")

    deadline = time.time() + 5
    while not started and time.time() < deadline:
        time.sleep(0.05)
    assert len(started) == 1, "first job should start"

    time.sleep(0.3)  # give the second job a chance to (incorrectly) start
    assert len(started) == 1, "second job must wait behind capacity=1"

    mgr.set_capacity(2)
    deadline = time.time() + 5
    while len(started) < 2 and time.time() < deadline:
        time.sleep(0.05)
    assert len(started) == 2, "raising capacity must start the waiter"
    release.set()
