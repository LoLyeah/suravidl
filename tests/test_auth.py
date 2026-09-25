"""Cookie auth (age-restricted / private videos): settings -> yt-dlp opts -> requests."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer t"}

COOKIE_NAME = "suravidl_test"
COOKIE_VALUE = "hello123"
NETSCAPE = ("# Netscape HTTP Cookie File\n"
            "127.0.0.1\tFALSE\t/\tFALSE\t2000000000\t"
            f"{COOKIE_NAME}\t{COOKIE_VALUE}\n")


class CapturingHandler(http.server.SimpleHTTPRequestHandler):
    seen_cookies: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        type(self).seen_cookies.append(self.headers.get("Cookie", ""))
        super().do_GET()


@pytest.fixture()
def cookie_server():
    CapturingHandler.seen_cookies = []
    handler = functools.partial(CapturingHandler, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", CapturingHandler.seen_cookies
    srv.shutdown()


def make_app(tmp_path, **kw):
    return create_app(download_dir=tmp_path / "dl", auth_token="t",
                      db_path=tmp_path / "jobs.db", **kw)


def cookies_file(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text(NETSCAPE)
    return p


def _wait(c, job_id, timeout=30):
    deadline = time.time() + timeout
    j = None
    while time.time() < deadline:
        j = c.get(f"/jobs/{job_id}", headers=AUTH).json()
        if j["status"] in ("completed", "error", "interrupted", "cancelled"):
            return j
        time.sleep(0.2)
    return j


def test_cookie_session_copies_and_cleans_up(tmp_path):
    from suravidl_engine.auth import cookie_session

    src = cookies_file(tmp_path)
    with cookie_session({"cookies_file": str(src), "cookies_from_browser": ""}) as opts:
        tmp_copy = Path(opts["cookiefile"])
        assert tmp_copy.is_file()
        assert tmp_copy != src
        assert tmp_copy.read_text() == NETSCAPE
        assert "cookiesfrombrowser" not in opts
    assert not tmp_copy.exists()          # removed after the run
    assert src.read_text() == NETSCAPE    # the user's file is never written to


def test_cookie_session_browser_spec():
    from suravidl_engine.auth import cookie_session

    with cookie_session({"cookies_file": "", "cookies_from_browser": "chrome"}) as opts:
        assert opts["cookiesfrombrowser"][0] == "chrome"
    with cookie_session({"cookies_file": "", "cookies_from_browser": ""}) as opts:
        assert opts == {}


def test_invalid_browser_rejected_on_save(tmp_path):
    c = TestClient(make_app(tmp_path))
    r = c.post("/settings", headers=AUTH, json={"cookies_from_browser": "netscrape"})
    assert r.status_code == 400
    assert "browser" in r.json()["detail"].lower()


def test_missing_cookie_file_rejected_on_save(tmp_path):
    c = TestClient(make_app(tmp_path))
    r = c.post("/settings", headers=AUTH,
               json={"cookies_file": str(tmp_path / "nope.txt")})
    assert r.status_code == 400
    ok = c.post("/settings", headers=AUTH,
                json={"cookies_file": str(cookies_file(tmp_path))})
    assert ok.status_code == 200
    assert ok.json()["cookies_file"].endswith("cookies.txt")


def test_download_sends_cookie_from_file(tmp_path, cookie_server):
    url, seen = cookie_server
    c = TestClient(make_app(tmp_path))
    c.post("/settings", headers=AUTH, json={"cookies_file": str(cookies_file(tmp_path))})
    job = c.post("/jobs", headers=AUTH, json={"url": f"{url}/tiny.mp4"}).json()
    j = _wait(c, job["id"])
    assert j["status"] == "completed", j
    assert any(f"{COOKIE_NAME}={COOKIE_VALUE}" in ck for ck in seen), seen


def test_probe_sends_cookie_from_file(tmp_path, cookie_server):
    url, seen = cookie_server
    c = TestClient(make_app(tmp_path))
    c.post("/settings", headers=AUTH, json={"cookies_file": str(cookies_file(tmp_path))})
    r = c.post("/probe", headers=AUTH, json={"url": f"{url}/tiny.mp4"})
    assert r.status_code == 200
    assert any(f"{COOKIE_NAME}={COOKIE_VALUE}" in ck for ck in seen), seen


def test_pick_file_endpoint(tmp_path):
    app = make_app(tmp_path)   # browser/headless: no desktop actions
    c = TestClient(app)
    assert c.post("/app/pick-file", headers=AUTH).status_code == 501

    app2 = make_app(tmp_path,
                    desktop_actions={"pick_file": lambda: "/tmp/picked-cookies.txt"})
    c2 = TestClient(app2)
    r = c2.post("/app/pick-file", headers=AUTH)
    assert r.status_code == 200 and r.json()["path"] == "/tmp/picked-cookies.txt"

    app3 = make_app(tmp_path, desktop_actions={"pick_file": lambda: 1 / 0})
    c3 = TestClient(app3)
    r3 = c3.post("/app/pick-file", headers=AUTH)
    assert r3.status_code == 200 and r3.json()["path"] is None
