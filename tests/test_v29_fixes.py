"""The cache gets its own button; the built-in presets grow up (v0.29.0).

Two asks (2026-09-28, with a screenshot of the Device panel):

1. "Why not make 'delete cache' as a different button?" Right — v0.24.9 had
   bolted the cache sweep onto BOTH file deletes ("the app cache was the
   piece with no owner"), and the hint had to explain the side effect. The
   endpoint half of the split (and the stand-down guard) lives in
   tests/test_files.py; this file pins the UI half — one button, one job,
   one promise each.

2. "Also add more built in presets pls." The built-ins were seven audio
   intents; the video side was missing. New: two MP4-compatibility intents
   (H.264+AAC preferred, capped, remuxed so the file opens anywhere) and
   three everyday bundles (English subs sidecar/embedded, metadata + cover
   art). A built-in patch preset now expands exactly like a saved one.
"""
import functools
import http.server
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer testtoken"}
HAVE_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.fixture(scope="module")
def video_server(tmp_path_factory):
    """A real 1-second MP4 (made by the host ffmpeg) over real HTTP: the
    remux intent needs a stream ffmpeg can actually read."""
    d = tmp_path_factory.mktemp("video")
    if HAVE_FFMPEG:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=1",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", str(d / "clip.mp4")], check=True, capture_output=True)
    else:
        (d / "clip.mp4").write_bytes(b"\x00" * 2048)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(d))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _client(tmp_path, **kw):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db",
                         cache_dir=kw.pop("cache_dir", tmp_path / "cache"), **kw)
    return TestClient(app)


def wait_job(c, job_id, timeout=30.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        job = c.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in ("completed", "error", "cancelled"):
            return job
        time.sleep(0.15)
    return job


# -- 1. the UI: one button, one job -----------------------------------------

def test_the_ui_offers_a_separate_cache_button():
    root = Path(__file__).parent.parent
    html = (root / "src/suravidl_engine/web/index.html").read_text()
    app = (root / "src/suravidl_engine/web/app.js").read_text()

    assert 'id="clearCacheBtn"' in html, "the cache needs its own button"
    assert '$("clearCacheBtn").onclick' in app
    assert '"/cache/clear"' in app, "wired to its own endpoint"
    # the file deletes no longer bundle it, and the hint no longer says so
    assert "The app cache is cleared too." not in app
    assert "Both also clear the app cache" not in html
    assert '"Clear app cache" frees only the player data' in html
    # the old "empty folder → cache-only dialog" fallback is gone: that flow
    # is the cache button now
    flow = app.split("const clearFiles = async (keepGallery)")[1].split('$("clearCacheBtn")')[0]
    assert "cacheBytes" not in flow, "file deletes must not reason about the cache"


# -- 2. the new built-in presets --------------------------------------------

def test_the_mp4_intents_map_to_real_yt_dlp_options():
    import yt_dlp

    from suravidl_engine.jobs import preset_opts

    for name, cap in (("video-mp4-1080", "1080"), ("video-mp4-720", "720")):
        opts = preset_opts(name)
        # yt-dlp's own parser accepts the expression, unchanged
        parsed = yt_dlp.parse_options(["-f", opts["format"]]).ydl_opts
        assert parsed["format"] == opts["format"], name
        assert f"[height<={cap}]" in opts["format"]
        # compatibility first, then the app's usual ladder, always ending in /b
        assert "[vcodec^=avc1]" in opts["format"] and "[ext=m4a]" in opts["format"]
        assert "+ba" in opts["format"] and opts["format"].endswith("/b")
        assert opts["merge_output_format"] == "mp4"
        pp = opts["postprocessors"]
        assert pp and pp[0]["key"] == "FFmpegVideoRemuxer"
        assert pp[0]["preferedformat"] == "mp4"


def test_a_silent_video_still_strips_the_pairing_from_an_intent():
    from suravidl_engine.download_opts import strip_audio_pairing
    from suravidl_engine.jobs import preset_opts

    silent = strip_audio_pairing(preset_opts("video-mp4-1080")["format"])
    assert "+ba" not in silent and silent  # a valid ladder remains


def test_the_new_builtins_are_listed_with_descriptions(tmp_path):
    with _client(tmp_path) as c:
        got = {p["name"]: p for p in c.get("/presets", headers=AUTH).json()["presets"]}
    for name in ("video-mp4-1080", "video-mp4-720", "subs-en-sidecar",
                 "subs-en-embed", "metadata-cover"):
        assert got[name]["builtin"] is True, name
        assert got[name]["description"], f"{name} must explain itself in the UI"
    # the list GREW (7 audio intents + 5 new) and nothing was lost
    builtins = [p for p in got.values() if p["builtin"]]
    assert len(builtins) == 12
    assert got["subs-en-sidecar"]["patch"]["subtitles_to_srt"] is True
    assert got["metadata-cover"]["patch"] == {"embed_metadata": True,
                                              "embed_thumbnail": True}


def test_a_builtin_patch_preset_expands_like_a_saved_one(tmp_path):
    """Before v0.29.0 the API expanded only USER presets; a built-in that is
    not a bare intent would have been refused as an unknown preset."""
    with _client(tmp_path) as c:
        j = c.post("/jobs", headers=AUTH, json={
            "url": "http://example.invalid/v.mp4", "preset": "subs-en-sidecar",
        }).json()
        assert j["preset"] is None
        assert j["overrides"] == {"subtitles_mode": "sidecar",
                                  "subtitles_langs": "en",
                                  "subtitles_to_srt": True}
        c.post(f"/jobs/{j['id']}/cancel", headers=AUTH)

        j2 = c.post("/jobs", headers=AUTH, json={
            "url": "http://example.invalid/v.mp4", "preset": "video-mp4-720",
        }).json()
        assert j2["preset"] == "video-mp4-720"
        assert j2["overrides"] is None
        c.post(f"/jobs/{j2['id']}/cancel", headers=AUTH)


@pytest.mark.skipif(not HAVE_FFMPEG, reason="remux needs ffmpeg")
def test_a_video_preset_downloads_end_to_end(tmp_path, video_server):
    with _client(tmp_path) as c:
        r = c.post("/jobs", headers=AUTH, json={
            "url": f"{video_server}/clip.mp4", "preset": "video-mp4-720",
        })
        assert r.status_code == 200, r.text
        job = wait_job(c, r.json()["id"])
        assert job["status"] == "completed", job.get("error")
        out = Path(job["filepath"])
        assert out.exists() and out.suffix == ".mp4"
        assert job["preset"] == "video-mp4-720"


def test_the_preset_picker_understands_video_intents():
    root = Path(__file__).parent.parent
    app = (root / "src/suravidl_engine/web/app.js").read_text()
    assert 'replace(/^(audio|video)-/, "")' in app, \
        "the options chip must shorten video intents the way it does audio"
