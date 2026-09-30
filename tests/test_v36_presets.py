"""v0.36.0 — a default preset: the permanent answer lives in Settings.

"Kept as is, if the user wants more permanent solution they can go to the
settings. Maybe add presets in the settings to?" — the one-shot block stays;
this adds the default. Settings → Presets can name one preset that rides
every NEW download, while anything a download itself says stays on top: an
explicit preset's format wins, a quality pick wins, per-download fields win,
and the default's bundle still fills in the rest.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text(encoding="utf-8")
AUTH = {"Authorization": "Bearer testtoken"}


@pytest.fixture()
def client(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db",
                         settings_path=tmp_path / "settings.json",
                         cache_dir=tmp_path / "cache")
    return TestClient(app)


def _save_preset(c, name, patch):
    r = c.post("/presets", json={"name": name, "patch": patch}, headers=AUTH)
    assert r.status_code == 200, r.text


def _set_default(c, name):
    r = c.post("/settings", json={"default_preset": name}, headers=AUTH)
    assert r.status_code == 200, r.text


def _job(c, **body):
    r = c.post("/jobs", json={"url": "http://127.0.0.1:9/x", **body},
               headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


# -- the default rides new downloads ----------------------------------------

def test_a_plain_job_rides_the_default_preset(client):
    _save_preset(client, "subs kit",
                 {"subtitles_mode": "sidecar", "subtitles_langs": "en"})
    _set_default(client, "subs kit")
    job = _job(client)
    assert job["preset"] is None
    assert job["overrides"]["subtitles_mode"] == "sidecar"
    assert job["overrides"]["subtitles_langs"] == "en"


def test_the_defaults_format_intent_yields_to_an_explicit_pick(client):
    _save_preset(client, "m4a kit",
                 {"preset": "audio-m4a", "sponsorblock_mode": "mark"})
    _set_default(client, "m4a kit")
    intent_job = _job(client)
    assert intent_job["preset"] == "audio-m4a"          # nothing competed
    assert intent_job["overrides"]["sponsorblock_mode"] == "mark"
    fmt_job = _job(client, fmt="137")
    assert fmt_job["preset"] is None                    # the pick wins…
    assert fmt_job["overrides"]["sponsorblock_mode"] == "mark"   # …bundle stays


def test_an_explicit_preset_beats_the_default_intent_and_keeps_its_bundle(client):
    _save_preset(client, "m4a kit",
                 {"preset": "audio-m4a", "sponsorblock_mode": "mark"})
    _set_default(client, "m4a kit")
    job = _job(client, preset="audio-mp3")
    assert job["preset"] == "audio-mp3"
    assert job["overrides"]["sponsorblock_mode"] == "mark"


def test_per_download_fields_beat_the_defaults_bundle(client):
    _save_preset(client, "subs kit",
                 {"subtitles_mode": "sidecar", "subtitles_langs": "en"})
    _set_default(client, "subs kit")
    job = _job(client, overrides={"subtitles_mode": "off"})
    assert job["overrides"]["subtitles_mode"] == "off"      # the newer word
    assert job["overrides"]["subtitles_langs"] == "en"      # the rest rides


def test_a_deleted_default_quietly_stops_riding(client):
    _save_preset(client, "gone soon", {"subtitles_mode": "sidecar"})
    _set_default(client, "gone soon")
    r = client.delete("/presets/gone%20soon", headers=AUTH)
    assert r.status_code == 200, r.text
    job = _job(client)          # a stale setting must never brick /jobs
    assert job["preset"] is None
    assert job.get("overrides") in (None, {})


# -- the boundaries ---------------------------------------------------------

def test_settings_refuse_an_unknown_default(client):
    r = client.post("/settings", json={"default_preset": "does not exist"},
                    headers=AUTH)
    assert r.status_code == 400
    assert "unknown preset" in r.json()["detail"]
    # and nothing was stored
    assert client.get("/settings", headers=AUTH).json()["default_preset"] == ""


def test_a_job_cannot_set_the_default_preset(client):
    r = client.post("/jobs",
                    json={"url": "http://127.0.0.1:9/x",
                          "overrides": {"default_preset": "x"}},
                    headers=AUTH)
    assert r.status_code == 400
    assert "default_preset" in r.json()["detail"]


def test_default_preset_is_settings_level_not_per_job():
    from suravidl_engine.settings import DEFAULTS, PER_JOB_KEYS

    assert "default_preset" in DEFAULTS
    assert "default_preset" not in PER_JOB_KEYS


# -- the settings UI --------------------------------------------------------

def test_the_settings_tab_offers_the_default_preset():
    assert 'id="defaultPreset"' in HTML
    assert "Default preset" in HTML


def test_the_select_follows_the_preset_list_and_saves_on_change():
    assert "function renderDefaultPreset" in APP
    # repainted whenever the preset list is (save/delete/load), before the
    # empty-list early return, so it exists even with only built-ins
    body = APP.split("function renderPresetList", 1)[1].split("\nfunction ", 1)[0]
    assert "renderDefaultPreset()" in body
    seg = APP.split("function renderDefaultPreset", 1)[1].split("\nfunction ", 1)[0]
    assert "default_preset" in seg
    assert '"/settings"' in seg and "onchange" in seg
