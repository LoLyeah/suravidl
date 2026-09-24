"""HTTP API: FastAPI app over the JobManager (offline fixture server)."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture()
def client(tmp_path, fixture_server, monkeypatch):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path, auth_token="testtoken")
    with TestClient(app) as c:
        yield c


AUTH = {"Authorization": "Bearer testtoken"}


def test_health_is_open_but_jobs_require_auth(client):
    assert client.get("/health").json()["ok"] is True
    r = client.get("/jobs")
    assert r.status_code == 401
    r = client.get("/jobs", headers=AUTH)
    assert r.status_code == 200


def test_probe_endpoint_returns_metadata(client, fixture_server):
    r = client.post("/probe", json={"url": f"{fixture_server}/tiny.mp4"},
                    headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["ext"] == "mp4"
    assert body["formats"]


def test_full_download_flow_over_http(client, fixture_server, tmp_path):
    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4"},
                    headers=AUTH)
    assert r.status_code == 200
    job_id = r.json()["id"]

    job = None
    for _ in range(200):
        job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in ("completed", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "completed", job
    assert Path(job["filepath"]).exists()

    listing = client.get("/jobs", headers=AUTH).json()
    assert any(j["id"] == job_id for j in listing["jobs"])


def test_rejects_unauthenticated_submissions(client):
    r = client.post("/jobs", json={"url": "http://x/y.mp4"})
    assert r.status_code == 401
