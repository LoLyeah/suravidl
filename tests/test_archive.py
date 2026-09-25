"""Archive setting end to end: re-downloading a known URL must be skipped."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer testtoken"}


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture()
def client(tmp_path):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir()
    app = api.create_app(download_dir=d, auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        yield c


def wait_job(client, job_id, timeout=60.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in ("completed", "error", "cancelled"):
            return job
        time.sleep(0.15)
    return job


def test_archive_skips_second_download(client, fixture_server, tmp_path):
    r = client.post("/settings", json={"archive": True}, headers=AUTH)
    assert r.status_code == 200, r.text

    url = f"{fixture_server}/tiny.mp4"
    job1 = wait_job(client, client.post("/jobs", json={"url": url},
                                        headers=AUTH).json()["id"])
    assert job1["status"] == "completed", job1.get("error")
    f = Path(job1["filepath"])
    assert f.is_file()

    archive = tmp_path / "archive.txt"
    assert archive.exists() and archive.read_text().strip()

    job2 = wait_job(client, client.post("/jobs", json={"url": url},
                                        headers=AUTH).json()["id"])
    assert job2["status"] == "completed", job2.get("error")
    # the engine reports the skip explicitly instead of pretending
    assert job2.get("note") == "already in the archive — skipped"


def test_archive_off_by_default_creates_no_archive(client, fixture_server, tmp_path):
    url = f"{fixture_server}/tiny.mp4"
    job1 = wait_job(client, client.post("/jobs", json={"url": url},
                                        headers=AUTH).json()["id"])
    assert job1["status"] == "completed"
    assert not (tmp_path / "archive.txt").exists()

    # and a deleted file is re-downloaded happily
    Path(job1["filepath"]).unlink()
    job2 = wait_job(client, client.post("/jobs", json={"url": url},
                                        headers=AUTH).json()["id"])
    assert job2["status"] == "completed"
    assert Path(job2["filepath"]).is_file()
