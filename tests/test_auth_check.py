"""Test-cookies endpoint: static verdicts, and a real extraction as proof."""
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

# a cookies.txt that is valid but long expired, and one that is current
EXPIRED = ("# Netscape HTTP Cookie File\n"
           "127.0.0.1\tFALSE\t/\tFALSE\t1000000000\tsuravidl_test\told\n")
CURRENT = ("# Netscape HTTP Cookie File\n"
           "127.0.0.1\tFALSE\t/\tFALSE\t2000000000\tsuravidl_test\thello123\n")


class CapturingHandler(http.server.SimpleHTTPRequestHandler):
    seen_cookies: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        type(self).seen_cookies.append(self.headers.get("Cookie", ""))
        super().do_GET()


@pytest.fixture()
def site():
    CapturingHandler.seen_cookies = []
    handler = functools.partial(CapturingHandler, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", CapturingHandler.seen_cookies
    srv.shutdown()


def make_app(tmp_path, **kw):
    return create_app(download_dir=tmp_path / "dl", auth_token="t",
                      db_path=tmp_path / "jobs.db", **kw)


def cookies_file(tmp_path, text):
    p = tmp_path / "cookies.txt"
    p.write_text(text)
    return p


def test_without_cookies_it_says_what_to_do(tmp_path):
    c = TestClient(make_app(tmp_path))
    r = c.post("/auth/check", json={}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["source"] == "none"
    assert "Settings" in body["message"]


def test_an_empty_file_is_not_mistaken_for_working_cookies(tmp_path):
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_file": str(cookies_file(tmp_path, ""))},
           headers=AUTH)
    body = c.post("/auth/check", json={}, headers=AUTH).json()
    assert body["ok"] is False
    assert "no cookies" in body["message"]
    assert body["cookies"]["count"] == 0


def test_a_file_of_expired_cookies_is_reported_as_such(tmp_path):
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_file": str(cookies_file(tmp_path, EXPIRED))},
           headers=AUTH)
    body = c.post("/auth/check", json={}, headers=AUTH).json()
    assert body["ok"] is False
    assert body["cookies"]["expired"] == 1 and body["cookies"]["count"] == 1
    assert "expired" in body["message"]


def test_a_current_file_passes_the_static_check_and_hides_no_values(tmp_path):
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_file": str(cookies_file(tmp_path, CURRENT))},
           headers=AUTH)
    body = c.post("/auth/check", json={}, headers=AUTH).json()
    assert body["ok"] is True and body["source"] == "file"
    assert body["cookies"]["domains"] == ["127.0.0.1"]
    assert_no_values(body)                  # no cookie value leaves the engine


def assert_no_values(body) -> None:
    """A cookie VALUE must never travel to the UI."""
    import json

    assert "hello123" not in json.dumps(body)


def test_a_url_proves_the_cookies_really_work(tmp_path, site):
    base, seen = site
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_file": str(cookies_file(tmp_path, CURRENT))},
           headers=AUTH)
    body = c.post("/auth/check", json={"url": f"{base}/tiny.mp4"},
                  headers=AUTH).json()
    assert body["ok"] is True, body
    assert body["url"] == f"{base}/tiny.mp4"
    assert "worked" in body["message"]
    # yt-dlp really sent the cookie: the server saw it
    assert any("suravidl_test=hello123" in ck for ck in seen)


def test_a_url_that_cannot_be_reached_reports_why_instead_of_raising(tmp_path):
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_file": str(cookies_file(tmp_path, CURRENT))},
           headers=AUTH)
    r = c.post("/auth/check", json={"url": "http://127.0.0.1:9/nothing.mp4"},
               headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["detail"]                      # yt-dlp's own words
    assert "did not get through" in body["message"]


def test_a_sign_in_wall_is_explained_as_stale_cookies(tmp_path, monkeypatch):
    """The point of the button: turn yt-dlp's error into the actual advice."""
    from suravidl_engine import auth
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_file": str(cookies_file(tmp_path, CURRENT))},
           headers=AUTH)

    def fake_probe(url, **kw):
        raise RuntimeError("Sign in to confirm you're not a bot. Use --cookies")

    monkeypatch.setattr("suravidl_engine.probe.probe", fake_probe)
    body = c.post("/auth/check", json={"url": "https://example.invalid/v"},
                  headers=AUTH).json()
    assert body["ok"] is False
    assert "still asked for a sign-in" in body["message"]
    assert "bot" in body["detail"]


def test_a_browser_source_is_not_called_working_without_a_url(tmp_path):
    c = TestClient(make_app(tmp_path))
    c.post("/settings", json={"cookies_from_browser": "chrome"}, headers=AUTH)
    body = c.post("/auth/check", json={}, headers=AUTH).json()
    assert body["source"] == "browser"
    assert body["ok"] is False            # unproven is not the same as working
    assert "paste one and test again" in body["message"]


def test_describe_cookies_file_counts_and_dates(tmp_path):
    from suravidl_engine.auth import describe_cookies_file

    p = cookies_file(tmp_path, CURRENT + EXPIRED)
    info = describe_cookies_file(p)
    assert info["count"] == 2 and info["expired"] == 1
    assert info["domains"] == ["127.0.0.1"] and info["newest"] == 2000000000
    missing = describe_cookies_file(tmp_path / "nope.txt")
    assert missing["exists"] is False and missing["count"] == 0
