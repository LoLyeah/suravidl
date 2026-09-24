"""Jobs: background download with progress + error states (offline fixture server)."""
import functools
import http.server
import subprocess
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


def wait_done(mgr, job_id, timeout=30):
    for _ in range(int(timeout * 10)):
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error"):
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


def test_download_job_completes_with_progress_and_file(tmp_path, fixture_server):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    assert job["status"] == "queued"

    j = wait_done(mgr, job["id"])
    assert j["status"] == "completed", j
    assert j["progress"]["downloaded_bytes"] > 0
    assert j["filepath"] and Path(j["filepath"]).exists()

    # The downloaded file is a real playable video
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1", j["filepath"]],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert 1.0 <= float(out.stdout.strip().split("=")[1]) <= 5.0


def test_download_job_error_on_bad_url(tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create("http://127.0.0.1:1/nonexistent.mp4")
    j = wait_done(mgr, job["id"])
    assert j["status"] == "error"
    assert j["error"], "expected an error message"


def test_hls_job_merges_to_playable_file(tmp_path, fixture_server):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create(f"{fixture_server}/hls/index.m3u8")
    j = wait_done(mgr, job["id"], timeout=60)
    assert j["status"] == "completed", j
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "default=nw=1", j["filepath"]],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert "codec_name" in out.stdout
