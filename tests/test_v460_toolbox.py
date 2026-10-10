"""v0.46.0 "the toolbox" — the paste list gets eyes; the bug report gets
a bundle.

Two features, one release. The batch door itself has existed since
v0.40.5 (paste several links, queue all, hear about failures after) —
what it never had was a look before the leap: per-link probing, real
names, ticks, and each link's own honest refusal in place. The other
half is diagnostics: one paste instead of five screenshots — versions,
the ffmpeg probe, redacted settings, the log tail — with redaction done
engine-side and PROVEN by sentinel secrets that must appear nowhere.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine import diagnostics
from suravidl_engine.api import create_app

ROOT = Path(__file__).resolve().parents[1]
APPJS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
INDEX = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")

AUTH = {"Authorization": "Bearer t"}


def _client(tmp_path):
    app = create_app(download_dir=tmp_path / "dl", auth_token="t",
                     db_path=tmp_path / "jobs.db")
    return TestClient(app)


# -- diagnostics: redaction is the whole game --------------------------------

def test_sentinel_secrets_appear_nowhere_in_the_bundle():
    settings = {
        "api_token": "SENTINEL_TOKEN_9f3",
        "auth": "SENTINEL_AUTH_1",
        "cookies": "sessionid=SENTINEL_COOKIE_77",
        "nested": {"db_password": "SENTINEL_PW_42", "note": "fine"},
        "url_with_secret": "https://cdn/watch?token=SENTINEL_QUERY_1&x=1",
        "keepme": "ordinary setting",
    }
    logs = ["downloading https://x?sig=SENTINEL_SIG_5", "an ordinary line"]
    jobs = [{"status": "failed", "title": "clip",
             "error": "boom token=SENTINEL_ERRSEC"}]
    blob = json.dumps(diagnostics.build_payload(
        settings=settings, logs=logs, jobs=jobs))
    for sentinel in ("SENTINEL_TOKEN_9f3", "SENTINEL_AUTH_1",
                     "SENTINEL_COOKIE_77", "SENTINEL_PW_42",
                     "SENTINEL_QUERY_1", "SENTINEL_SIG_5",
                     "SENTINEL_ERRSEC"):
        assert sentinel not in blob, sentinel
    # and the redaction is surgical: the ordinary things survive
    assert "ordinary setting" in blob
    assert "an ordinary line" in blob
    payload = json.loads(blob)
    assert payload["settings"]["api_token"] == "***"
    assert payload["jobs"]["recent"][0]["error"].startswith("boom")


def test_the_endpoint_answers_with_the_bundle(tmp_path):
    with _client(tmp_path) as c:
        r = c.get("/diagnostics")
        assert r.status_code == 401          # the token is the wall, always
        got = c.get("/diagnostics", headers=AUTH)
        assert got.status_code == 200
        body = got.json()
        for key in ("engine", "yt-dlp", "python", "platform", "ffmpeg",
                    "jobs", "settings", "logs", "note"):
            assert key in body, key
        assert body["engine"] == __import__(
            "suravidl_engine").__version__
        # the ffmpeg block is probed, not guessed (path is always there)
        assert "path" in body["ffmpeg"]
        assert set(body["ffmpeg"]["can_encode"]) == {"mov_text", "aac",
                                                     "libmp3lame"}


# -- the paste list's eyes ---------------------------------------------------

def test_the_paste_list_looks_before_it_leaps():
    # the check pass exists, is bounded, and honours ticks
    assert "async function checkBatch()" in APPJS
    assert "async function probeInto(it)" in APPJS
    assert 'BULK.filter((x) => x.ticked)' in APPJS
    # three-at-a-time, as promised on screen
    assert "await Promise.all([worker(), worker(), worker()])" in APPJS
    # a failing check is honest and unticked, but re-tickable
    assert "checked and refused" in APPJS
    assert 'id="batchCheck"' in INDEX and 'id="batchList"' in INDEX


def test_the_diagnostics_door_exists_on_both_sides():
    assert 'id="diagOpen"' in INDEX and 'id="diagModal"' in INDEX
    assert "function initDiagnostics()" in APPJS
    assert 'api("/diagnostics")' in APPJS
    # the strings are translated, like every other door's
    assert "Salin diagnostik" in APPJS
