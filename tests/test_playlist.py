"""Playlists end to end: probe detection, item ranges, multi-file results.

The fixture page carries two <video> tags, which yt-dlp's generic extractor
turns into a real two-entry playlist — no network, no mocks.
"""
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
def dl_dir(tmp_path):
    d = tmp_path / "dl"
    d.mkdir()
    return d


@pytest.fixture()
def client(tmp_path, dl_dir):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=dl_dir, auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        yield c


class SlowHandler(http.server.SimpleHTTPRequestHandler):
    """Delays every response so per-item progress is observable."""

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(FIXTURES), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        time.sleep(0.6)
        super().do_GET()


@pytest.fixture(scope="module")
def slow_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def wait_job(client, job_id, timeout=60.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in ("completed", "error", "cancelled"):
            return job
        time.sleep(0.15)
    return job


def files_in(d):
    return sorted(p.name for p in Path(d).iterdir() if p.is_file())


# -- probe ------------------------------------------------------------------

def test_probe_detects_a_playlist(client, fixture_server):
    body = client.post("/probe", json={"url": f"{fixture_server}/playlist.html"},
                       headers=AUTH).json()
    assert body["playlist"] is True
    assert body["count"] == 2
    assert len(body["entries"]) == 2
    assert [e["url"].rsplit("/", 1)[-1] for e in body["entries"]] == \
        ["tiny.mp4", "tiny2.mp4"]


def test_probe_single_video_still_reports_formats(client, fixture_server):
    body = client.post("/probe", json={"url": f"{fixture_server}/tiny.mp4"},
                       headers=AUTH).json()
    assert body["playlist"] is False
    assert body["formats"]


# -- downloads --------------------------------------------------------------

def test_playlist_range_downloads_only_the_selected_item(client, fixture_server, dl_dir):
    r = client.post("/jobs", json={
        "url": f"{fixture_server}/playlist.html", "playlist_items": "2-2",
    }, headers=AUTH)
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    files = files_in(dl_dir)
    assert len(files) == 1 and "(2)" in files[0], files
    assert job["filepath"] == str(dl_dir)


def test_playlist_all_items(client, fixture_server, dl_dir):
    r = client.post("/jobs", json={
        "url": f"{fixture_server}/playlist.html", "playlist_items": "",
    }, headers=AUTH)
    assert r.status_code == 200
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    files = files_in(dl_dir)
    assert len(files) == 2 and all(n.endswith(".mp4") for n in files), files
    assert job["playlist_count"] == 2


def test_playlist_url_without_explicit_request_stays_single(client, fixture_server, dl_dir):
    """Safety: a playlist URL without playlist_items must not mass-download."""
    r = client.post("/jobs", json={"url": f"{fixture_server}/playlist.html"},
                    headers=AUTH)
    assert r.status_code == 200
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    files = files_in(dl_dir)
    assert len(files) == 1 and "(1)" in files[0], files


def test_playlist_progress_reports_item_index(client, slow_server, dl_dir):
    r = client.post("/jobs", json={"url": f"{slow_server}/playlist.html",
                                   "playlist_items": ""}, headers=AUTH)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    seen = set()
    job = None
    deadline = time.time() + 60
    while time.time() < deadline:
        job = client.get(f"/jobs/{jid}", headers=AUTH).json()
        prog = job.get("progress") or {}
        if prog.get("playlist_index"):
            seen.add(prog["playlist_index"])
        if job["status"] in ("completed", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "completed", job.get("error")
    assert 2 in seen, f"second item never reported as downloading: {seen}"
    assert job["playlist_count"] == 2


def test_playlist_items_survive_retry(client, fixture_server):
    r = client.post("/jobs", json={
        "url": f"{fixture_server}/missing.html", "playlist_items": "1-3",
    }, headers=AUTH)
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "error"
    assert job["playlist_items"] == "1-3"

    r2 = client.post(f"/jobs/{job['id']}/retry", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["playlist_items"] == "1-3"


def test_bad_playlist_items_rejected(client, fixture_server):
    for bad in ("abc", "1-2;3", "../1", "1..3"):
        r = client.post("/jobs", json={
            "url": f"{fixture_server}/playlist.html", "playlist_items": bad,
        }, headers=AUTH)
        assert r.status_code == 400, (bad, r.status_code)
