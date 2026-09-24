"""Captured browser headers must reach yt-dlp (extension handoff requirement)."""
import functools
import http.server
import threading

import pytest

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


class HeaderGateHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the fixtures dir only to a specific User-Agent; 403 otherwise."""

    required_ua = "vidl-test-agent/1.0"

    def do_GET(self):
        if self.headers.get("User-Agent") != self.required_ua:
            self.send_error(403, "bad agent")
            return
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture()
def gated_server():
    handler = functools.partial(HeaderGateHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_probe_without_headers_is_blocked(gated_server):
    from vidl_engine.probe import probe

    with pytest.raises(Exception):
        probe(f"{gated_server}/tiny.mp4")


def test_probe_with_captured_headers_succeeds(gated_server):
    from vidl_engine.probe import probe

    info = probe(f"{gated_server}/tiny.mp4",
                 extra_headers={"User-Agent": HeaderGateHandler.required_ua})
    assert info["ext"] == "mp4"


def test_download_job_with_captured_headers_succeeds(tmp_path, gated_server):
    import time
    from pathlib import Path

    from vidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create(f"{gated_server}/tiny.mp4",
                     extra_headers={"User-Agent": HeaderGateHandler.required_ua})
    for _ in range(200):
        j = mgr.get(job["id"])
        if j["status"] in ("completed", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "completed", j
    assert Path(j["filepath"]).exists()
