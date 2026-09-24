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


def test_format_selection_via_api(client, fixture_server):
    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4",
                                   "fmt": "best"}, headers=AUTH)
    assert r.status_code == 200
    jid = r.json()["id"]
    job = None
    for _ in range(200):
        job = client.get(f"/jobs/{jid}", headers=AUTH).json()
        if job["status"] in ("completed", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "completed", job


def test_invalid_format_errors_cleanly(client, fixture_server):
    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4",
                                   "fmt": "definitely-not-a-format"},
                    headers=AUTH)
    assert r.status_code == 200
    jid = r.json()["id"]
    job = None
    for _ in range(200):
        job = client.get(f"/jobs/{jid}", headers=AUTH).json()
        if job["status"] in ("completed", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "error", job
    assert "format" in (job["error"] or "").lower()


def test_cancel_and_retry_endpoints(tmp_path, fixture_server):
    import functools
    import http.server
    import threading

    from fastapi.testclient import TestClient

    import suravidl_engine.api as api

    class Throttled(http.server.SimpleHTTPRequestHandler):
        def copyfile(self, source, outputfile):
            while True:
                data = source.read(2048)
                if not data:
                    break
                outputfile.write(data)
                outputfile.flush()
                time.sleep(0.08)

        def log_message(self, *args):
            pass

    handler = functools.partial(Throttled, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    slow = f"http://127.0.0.1:{server.server_address[1]}"

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db", max_concurrent=1)
    with TestClient(app) as c:
        a = c.post("/jobs", json={"url": f"{slow}/tiny.mp4"},
                   headers=AUTH).json()
        b = c.post("/jobs", json={"url": f"{slow}/tiny.mp4"},
                   headers=AUTH).json()
        # b is queued behind a (single slot): instant cancel
        rr = c.post(f"/jobs/{b['id']}/cancel", headers=AUTH)
        assert rr.status_code == 200, rr.text
        assert rr.json()["status"] == "cancelled"

        # a is downloading: cancel lands at the next progress hook
        assert c.post(f"/jobs/{a['id']}/cancel", headers=AUTH).status_code == 200
        final = None
        for _ in range(200):
            final = c.get(f"/jobs/{a['id']}", headers=AUTH).json()
            if final["status"] in ("cancelled", "completed", "error"):
                break
            time.sleep(0.05)
        assert final["status"] == "cancelled", final

        # terminal job: cancel is 409, retry creates a fresh job
        assert c.post(f"/jobs/{a['id']}/cancel",
                      headers=AUTH).status_code == 409
        out = c.post(f"/jobs/{a['id']}/retry", headers=AUTH)
        assert out.status_code == 200, out.text
        assert out.json()["id"] != a["id"]

        # unknown ids 404
        assert c.post("/jobs/zzz/cancel", headers=AUTH).status_code == 404
        assert c.post("/jobs/zzz/retry", headers=AUTH).status_code == 404
        server.shutdown()
