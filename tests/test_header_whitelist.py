"""Captured browser headers are whitelisted before reaching yt-dlp."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class EchoHeaderHandler(http.server.SimpleHTTPRequestHandler):
    """Appends the raw User-Agent it received to a log list for assertions."""

    seen = []

    def do_GET(self):
        EchoHeaderHandler.seen.append(dict(self.headers))
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture()
def echo_server():
    EchoHeaderHandler.seen = []
    handler = functools.partial(EchoHeaderHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _wait_done(mgr, job_id, timeout=30):
    for _ in range(int(timeout * 10)):
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


def test_whitelist_passes_cookie_and_ua(echo_server, tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl")
    job = mgr.create(
        f"{echo_server}/tiny.mp4",
        extra_headers={
            "User-Agent": "suravidl-m3/1.0",
            "Cookie": "session=abc123",
            "Referer": "https://example.com/watch",
            "Origin": "https://example.com",
        })
    j = _wait_done(mgr, job["id"])
    assert j["status"] == "completed", j
    ua = next((h.get("User-Agent") for h in EchoHeaderHandler.seen if h.get("User-Agent")), None)
    cookie = next((h.get("Cookie") for h in EchoHeaderHandler.seen if h.get("Cookie")), None)
    assert ua == "suravidl-m3/1.0", EchoHeaderHandler.seen
    assert cookie == "session=abc123", EchoHeaderHandler.seen


def test_dangerous_headers_are_stripped(echo_server, tmp_path):
    """Host-mangling headers must never reach yt-dlp from extension capture."""
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl")
    job = mgr.create(
        f"{echo_server}/tiny.mp4",
        extra_headers={
            "Host": "evil.example.com",
            "X-Evil": "1",
            "User-Agent": "suravidl-m3/1.0",
        })
    j = _wait_done(mgr, job["id"])
    assert j["status"] == "completed", j
    for h in EchoHeaderHandler.seen:
        assert h.get("X-Evil") is None
        assert h.get("Host") != "evil.example.com"
