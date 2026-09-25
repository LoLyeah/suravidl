"""Raw yt-dlp arguments (Advanced tier): parsing, guarding, and E2E effect."""
import functools
import http.server
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

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
def dl_dir(tmp_path):
    d = tmp_path / "dl"
    d.mkdir()
    return d


@pytest.fixture()
def client(tmp_path, dl_dir):
    app = create_app(download_dir=dl_dir, auth_token="testtoken",
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


# -- parsing ----------------------------------------------------------------

def test_parse_is_minimal_and_sane():
    from suravidl_engine.download_opts import parse_raw_args

    opts = parse_raw_args("--retries 3")
    assert opts == {"retries": 3}, opts

    opts = parse_raw_args("--write-info-json --no-mtime")
    assert opts.get("writeinfojson") is True
    # defaults from the CLI parse must NOT leak into the engine's options
    for untouched in ("noplaylist", "quiet", "extract_flat", "paths", "simulate"):
        assert untouched not in opts, (untouched, opts)


def test_parse_denies_engine_breaking_flags():
    from suravidl_engine.download_opts import parse_raw_args

    for raw, marker in (
        ("--exec echo boom", "--exec"),
        ("--exec-before-download echo boom", "--exec-before-download"),
        ("--batch-file /tmp/list.txt", "--batch-file"),
        ("--simulate", "--simulate"),
        ("--skip-download", "--skip-download"),
        ("--load-info-json /tmp/x.json", "--load-info-json"),
        ("--config-locations /tmp/x.conf", "--config-locations"),
        ("--download-archive /tmp/a.txt", "--download-archive"),
        ("--dump-json", "--dump-json"),
        ("--external-downloader aria2c", "--external-downloader"),
        ("--cookies /tmp/c.txt", "--cookies"),
    ):
        with pytest.raises(ValueError) as err:
            parse_raw_args(raw)
        assert marker in str(err.value), (raw, str(err.value))


def test_parse_rejects_garbage():
    from suravidl_engine.download_opts import parse_raw_args

    with pytest.raises(ValueError):
        parse_raw_args("--definitely-not-an-option")
    with pytest.raises(ValueError):
        parse_raw_args("--format 'unterminated")
    assert parse_raw_args("") == {}


def test_build_opts_applies_raw_args_only_when_enabled():
    from suravidl_engine.download_opts import build_download_opts

    base = {"raw_args_enabled": False, "raw_args": "--write-info-json"}
    assert "writeinfojson" not in build_download_opts(base, "/dl")
    on = {"raw_args_enabled": True, "raw_args": "--write-info-json"}
    assert build_download_opts(on, "/dl")["writeinfojson"] is True


def test_denied_args_rejected_at_the_door(client, fixture_server, dl_dir):
    """Refused flags must never reach a job: refused at save and at create."""
    r = client.post("/settings", json={"raw_args_enabled": True,
                                       "raw_args": "--exec echo boom"},
                    headers=AUTH)
    assert r.status_code == 400
    assert "--exec" in r.json()["detail"]

    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4",
                                   "raw_args": "--exec echo boom"},
                    headers=AUTH)
    assert r.status_code == 400
    assert "--exec" in r.json()["detail"]


# -- API surface -------------------------------------------------------------

def test_per_job_raw_args_only_when_enabled(client, fixture_server, dl_dir):
    # disabled globally -> explicit per-job args are refused loudly
    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4",
                                   "raw_args": "--write-info-json"},
                    headers=AUTH)
    assert r.status_code == 400
    assert "disabled" in r.json()["detail"].lower()

    client.post("/settings", json={"raw_args_enabled": True}, headers=AUTH)
    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4",
                                   "raw_args": "--write-info-json"},
                    headers=AUTH)
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    assert any("info.json" in p.name for p in dl_dir.iterdir())


def test_raw_args_enabled_from_settings_apply_to_jobs(client, fixture_server, dl_dir):
    client.post("/settings", json={"raw_args_enabled": True,
                                   "raw_args": "--write-info-json"},
                headers=AUTH)
    r = client.post("/jobs", json={"url": f"{fixture_server}/tiny.mp4"},
                    headers=AUTH)
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    assert job["raw_args"] == "--write-info-json"
    assert any(p.name.endswith(".info.json") for p in dl_dir.iterdir())


def test_raw_args_survive_retry(client, fixture_server):
    client.post("/settings", json={"raw_args_enabled": True}, headers=AUTH)
    r = client.post("/jobs", json={"url": f"{fixture_server}/missing.mp4",
                                   "raw_args": "--write-info-json"},
                    headers=AUTH)
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "error"
    assert job["raw_args"] == "--write-info-json"
    r2 = client.post(f"/jobs/{job['id']}/retry", headers=AUTH)
    assert r2.json()["raw_args"] == "--write-info-json"


def test_settings_validation(client):
    assert client.post("/settings", json={"raw_args": "--write-info-json"},
                       headers=AUTH).status_code == 200
    assert client.post("/settings", json={"raw_args": "x" * 2000},
                       headers=AUTH).status_code == 400
    s = client.get("/settings", headers=AUTH).json()
    assert s["raw_args_enabled"] is False


# -- option catalogue --------------------------------------------------------

def test_options_catalogue_endpoint(client):
    r = client.get("/options", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 300, body["count"]
    by_name = {o["name"]: o for o in body["options"]}
    assert "--proxy" in by_name
    assert by_name["--proxy"]["group"].lower().startswith("network")
    assert by_name["--proxy"]["help"]
    assert any(o["group"].lower().startswith("sponsorblock")
               for o in body["options"])


def test_options_endpoint_requires_auth(client):
    assert client.get("/options").status_code in (401, 403)
