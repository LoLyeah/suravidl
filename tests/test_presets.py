"""Audio-only presets: native passthrough, m4a extraction, mp3 conversion."""
import functools
import http.server
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer testtoken"}

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.fixture(scope="module")
def audio_server(tmp_path_factory):
    """Serves a real 1-second 440 Hz tone.m4a (made by the host ffmpeg)."""
    d = tmp_path_factory.mktemp("audio")
    if HAVE_FFMPEG:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             "sine=frequency=440:duration=1", "-c:a", "aac", str(d / "tone.m4a")],
            check=True, capture_output=True)
    else:
        (d / "tone.m4a").write_bytes(b"\x00" * 2048)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(d))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture()
def client(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path, auth_token="testtoken")
    with TestClient(app) as c:
        yield c


def wait_job(client, job_id, timeout=30.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in ("completed", "error", "cancelled"):
            return job
        time.sleep(0.15)
    return job


# -- option mapping ---------------------------------------------------------

def test_preset_opts_mapping():
    from suravidl_engine.jobs import preset_opts

    assert preset_opts(None) == {}

    native = preset_opts("audio-native")
    assert native["format"] == "bestaudio/best"
    assert "postprocessors" not in native  # no ffmpeg required anywhere

    m4a = preset_opts("audio-m4a")
    assert m4a["format"] == "bestaudio/best"
    assert m4a["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    assert m4a["postprocessors"][0]["preferredcodec"] == "m4a"

    mp3 = preset_opts("audio-mp3")
    assert mp3["postprocessors"][0]["preferredcodec"] == "mp3"
    assert mp3["postprocessors"][0]["preferredquality"] == "192"

    with pytest.raises(ValueError):
        preset_opts("not-a-preset")


def test_ffmpeg_location_only_set_when_env_present(monkeypatch):
    from suravidl_engine.jobs import ffmpeg_opts

    monkeypatch.delenv("SURAVIDL_FFMPEG", raising=False)
    assert ffmpeg_opts() == {}
    monkeypatch.setenv("SURAVIDL_FFMPEG", "/data/app/libffmpeg.so")
    assert ffmpeg_opts() == {"ffmpeg_location": "/data/app/libffmpeg.so"}


# -- API validation ---------------------------------------------------------

def test_job_rejects_preset_and_fmt_together(client, audio_server):
    r = client.post("/jobs", json={
        "url": f"{audio_server}/tone.m4a", "fmt": "best", "preset": "audio-mp3",
    }, headers=AUTH)
    assert r.status_code == 400
    assert "preset" in r.json()["detail"]


def test_job_rejects_unknown_preset(client, audio_server):
    r = client.post("/jobs", json={
        "url": f"{audio_server}/tone.m4a", "preset": "audio-ogg",
    }, headers=AUTH)
    assert r.status_code == 400
    assert "preset" in r.json()["detail"]


# -- real downloads ---------------------------------------------------------

def test_native_audio_download_completes_without_conversion(client, audio_server):
    r = client.post("/jobs", json={
        "url": f"{audio_server}/tone.m4a", "preset": "audio-native",
    }, headers=AUTH)
    assert r.status_code == 200
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    assert job["filepath"].endswith(".m4a")
    assert Path(job["filepath"]).exists()


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs host ffmpeg to convert")
def test_mp3_preset_converts_the_stream(client, audio_server, tmp_path):
    r = client.post("/jobs", json={
        "url": f"{audio_server}/tone.m4a", "preset": "audio-mp3",
    }, headers=AUTH)
    assert r.status_code == 200
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    out = Path(job["filepath"])
    assert out.suffix == ".mp3"
    assert out.exists() and out.stat().st_size > 0
    head = out.read_bytes()[:3]
    assert head == b"ID3" or (head[0] == 0xFF and head[1] & 0xE0 == 0xE0)


def test_m4a_preset_converts_the_stream(client, audio_server):
    if not HAVE_FFMPEG:
        pytest.skip("needs host ffmpeg")
    r = client.post("/jobs", json={
        "url": f"{audio_server}/tone.m4a", "preset": "audio-m4a",
    }, headers=AUTH)
    assert r.status_code == 200
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "completed", job.get("error")
    assert Path(job["filepath"]).suffix == ".m4a"


def test_retry_keeps_the_preset(client, audio_server):
    r = client.post("/jobs", json={
        "url": f"{audio_server}/missing.m4a", "preset": "audio-mp3",
    }, headers=AUTH)
    job = wait_job(client, r.json()["id"])
    assert job["status"] == "error"
    assert job["preset"] == "audio-mp3"

    r2 = client.post(f"/jobs/{job['id']}/retry", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["preset"] == "audio-mp3"
