"""The two halves of suravidl update on different clocks — say so, and verify.

Unreleased: the engine advertises an API level and the extension it needs; an
older extension is refused in words instead of doing half a job. The engine
also hands out a support block a person can paste into a report, and refuses a
download that cannot fit on the drive.
"""
from __future__ import annotations

import http.server
import json
import threading
import time
from collections import namedtuple
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine import jobs as jobs_mod
from suravidl_engine.api import MIN_EXTENSION, create_app

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer secret-token-xyz"}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(FIXTURES), **kw)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield "http://127.0.0.1:%d" % srv.server_address[1]
    finally:
        srv.shutdown()


def make_app(tmp_path):
    return create_app(download_dir=tmp_path / "dl", auth_token="secret-token-xyz",
                      db_path=tmp_path / "jobs.db")


def test_health_advertises_the_contract(tmp_path):
    health = TestClient(make_app(tmp_path)).get("/health").json()
    assert health["ok"] is True
    assert health["api"] >= 2
    assert health["min_extension"] == MIN_EXTENSION
    assert "page_url" in health["features"]


def test_an_old_extension_is_refused_in_words(tmp_path, server):
    c = TestClient(make_app(tmp_path))
    r = c.post("/jobs", headers={**AUTH, "X-Suravidl-Extension": "0.5.1"},
               json={"url": f"{server}/tiny.mp4"})
    assert r.status_code == 409
    assert MIN_EXTENSION in r.json()["detail"]
    assert "update" in r.json()["detail"].lower()


def test_the_handoff_door_is_gated_too(tmp_path):
    c = TestClient(make_app(tmp_path))
    r = c.post("/handoff", headers={**AUTH, "X-Suravidl-Extension": "0.1.0"},
               json={"url": "https://example.com/v.mp4"})
    assert r.status_code == 409


def test_a_current_extension_passes(tmp_path, server):
    c = TestClient(make_app(tmp_path))
    r = c.post("/jobs", headers={**AUTH, "X-Suravidl-Extension": "0.5.32"},
               json={"url": f"{server}/tiny.mp4"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("queued", "downloading")


def test_no_header_still_works(tmp_path, server):
    """curl and the Android shell speak the same API without a version."""
    c = TestClient(make_app(tmp_path))
    assert c.post("/jobs", headers=AUTH,
                  json={"url": f"{server}/tiny.mp4"}).status_code == 200


def test_diagnostics_carries_no_secret(tmp_path):
    c = TestClient(make_app(tmp_path))
    d = c.get("/diagnostics",
              headers={**AUTH, "X-Suravidl-Extension": "0.5.32"}).json()
    assert d["engine"] and d["api"] >= 2
    assert d["extension"] == "0.5.32"
    assert d["min_extension"] == MIN_EXTENSION
    assert isinstance(d["jobs"]["recent"], list)
    blob = json.dumps(d)
    assert AUTH["Authorization"].split(" ")[1] not in blob
    assert "Bearer" not in blob


def test_diagnostics_keeps_hosts_and_drops_queries(tmp_path, server):
    c = TestClient(make_app(tmp_path))
    c.post("/jobs", headers=AUTH,
           json={"url": f"{server}/tiny.mp4?token=should-not-appear"})
    deadline = time.time() + 20
    while time.time() < deadline:
        if c.get("/diagnostics", headers=AUTH).json()["jobs"]:
            break
        time.sleep(0.2)
    d = c.get("/diagnostics", headers=AUTH).json()
    assert d["jobs"]["recent"], "the job that just ran is in the bundle"
    assert "should-not-appear" not in json.dumps(d)


def test_a_full_drive_is_refused_at_the_door(tmp_path, monkeypatch):
    Usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(jobs_mod.shutil, "disk_usage",
                        lambda _p: Usage(10**9, 10**9, 100 * 1024 * 1024))
    mgr = jobs_mod.JobManager(download_dir=tmp_path / "dl",
                              db_path=str(tmp_path / "jobs.db"))
    with pytest.raises(ValueError) as err:
        mgr.create("https://example.com/v.mp4")
    assert "MB free" in str(err.value)
