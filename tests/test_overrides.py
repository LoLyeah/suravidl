"""Per-job option overrides — "this download only", without touching settings.

The UI's per-download block and named presets both end up here, so the rules
are: only a whitelist of per-job keys, validated exactly like settings, stored
with the job (so a retry re-runs what the user actually asked for), and merged
over the global settings when yt-dlp gets its options.
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
ACTIVE = ("queued", "downloading", "merging")


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

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        yield c


def _settle(c, jid):
    """Cancel and wait: never let a test race the download worker."""
    c.post(f"/jobs/{jid}/cancel", headers=AUTH)
    job = c.get(f"/jobs/{jid}", headers=AUTH).json()
    for _ in range(60):
        if job["status"] not in ACTIVE:
            return job
        time.sleep(0.05)
        job = c.get(f"/jobs/{jid}", headers=AUTH).json()
    return job


def test_overrides_are_stored_with_the_job_and_shown_to_clients(client):
    j = client.post("/jobs", headers=AUTH, json={
        "url": "http://example.invalid/v.mp4",
        "overrides": {"subtitles_mode": "sidecar", "subtitles_langs": "en, id"},
    }).json()
    assert j["overrides"] == {"subtitles_mode": "sidecar",
                              "subtitles_langs": "en, id"}
    # and the stored row agrees (the list endpoint re-reads from disk)
    listed = [x for x in client.get("/jobs", headers=AUTH).json()["jobs"]
              if x["id"] == j["id"]][0]
    assert listed["overrides"]["subtitles_langs"] == "en, id"
    _settle(client, j["id"])


def test_a_job_without_overrides_reports_none(client):
    j = client.post("/jobs", headers=AUTH,
                    json={"url": "http://example.invalid/v.mp4"}).json()
    assert j.get("overrides") in (None, {})
    _settle(client, j["id"])


def test_unknown_override_key_is_refused_before_the_job_exists(client):
    r = client.post("/jobs", headers=AUTH, json={
        "url": "http://example.invalid/v.mp4",
        "overrides": {"cookiefile": "/etc/passwd"},
    })
    assert r.status_code == 400
    assert "cookiefile" in r.json()["detail"]
    assert client.get("/jobs", headers=AUTH).json()["jobs"] == []


def test_app_level_keys_cannot_be_overridden_per_job(client):
    """download_dir/max_concurrent/theme are not a download's business."""
    for patch in ({"download_dir": "/tmp/elsewhere"}, {"max_concurrent": 8},
                  {"theme": "amoled"}, {"auto_resume": False}):
        r = client.post("/jobs", headers=AUTH,
                        json={"url": "http://example.invalid/v.mp4",
                              "overrides": patch})
        assert r.status_code == 400, patch


def test_override_values_are_validated_like_settings(client):
    for patch in ({"subtitles_mode": "burn"},
                  {"subtitles_langs": "en; rm -rf /"},
                  {"raw_args": "--exec touch /tmp/pwned"}):
        r = client.post("/jobs", headers=AUTH,
                        json={"url": "http://example.invalid/v.mp4",
                              "overrides": patch})
        assert r.status_code == 400, patch


def test_a_clamped_override_is_clamped_the_same_way(client):
    """fragments is clamped (1-16) in settings; a job gets the same treatment."""
    j = client.post("/jobs", headers=AUTH, json={
        "url": "http://example.invalid/v.mp4", "overrides": {"fragments": 99},
    }).json()
    assert j["overrides"] == {"fragments": 16}
    _settle(client, j["id"])


def test_retry_keeps_the_overrides(client):
    j = client.post("/jobs", headers=AUTH, json={
        "url": "http://example.invalid/v.mp4",
        "overrides": {"sponsorblock_mode": "remove"},
    }).json()
    _settle(client, j["id"])
    for _ in range(60):  # it errors on its own (dead host)
        cur = client.get(f"/jobs/{j['id']}", headers=AUTH).json()
        if cur["status"] in ("error", "cancelled"):
            break
        time.sleep(0.1)
    again = client.post(f"/jobs/{j['id']}/retry", headers=AUTH).json()
    assert again["overrides"] == {"sponsorblock_mode": "remove"}
    _settle(client, again["id"])


def test_an_override_really_reaches_ytdlp(client, fixture_server, tmp_path):
    """End to end: a per-job template names the file, global settings don't."""
    j = client.post("/jobs", headers=AUTH, json={
        "url": f"{fixture_server}/tiny.mp4",
        "overrides": {"filename_template": "only-this-job-%(ext)s"},
    }).json()
    for _ in range(200):
        cur = client.get(f"/jobs/{j['id']}", headers=AUTH).json()
        if cur["status"] in ("completed", "error"):
            break
        time.sleep(0.1)
    assert cur["status"] == "completed", cur
    assert cur["filepath"].endswith("only-this-job-mp4"), cur["filepath"]
    # and the global settings were not touched by it
    settings = client.get("/settings", headers=AUTH).json()
    assert settings["filename_template"] != "only-this-job-%(ext)s"
