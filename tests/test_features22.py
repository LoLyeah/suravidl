"""Feature batch v0.22.0 — from the Antigravity feature review.

Each test here was written before the feature existed (RED first). The review
that produced the list is docs/audits/2026-09-26-antigravity-features.md; the
verdicts below say which recommendation each test pins.
"""
from __future__ import annotations

import functools
import http.server
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

AUTH = {"Authorization": "Bearer testtoken"}
FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D102 - silence test output
        pass


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(_Quiet, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _client(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir(exist_ok=True)
    app = create_app(download_dir=dl, auth_token="testtoken",
                     db_path=tmp_path / "jobs.db")
    return TestClient(app)


def _wait(c, job_id, statuses=("completed", "error", "cancelled"), tries=400):
    job = {}
    for _ in range(tries):
        job = c.get(f"/jobs/{job_id}", headers=AUTH).json()
        if job["status"] in statuses:
            return job
        time.sleep(0.1)
    return job


def _probe_fixture(c, server, name="tiny.mp4"):
    r = c.post("/probe", json={"url": f"{server}/{name}"}, headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def _ffprobe(path, entry):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entry,
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout or "{}")


# -- 1. subfolder organization (review #1) ----------------------------------

def test_subfolders_by_site_puts_each_site_in_its_own_folder(tmp_path, server):
    with _client(tmp_path) as c:
        assert c.post("/settings", json={"subfolders": "site"},
                      headers=AUTH).status_code == 200
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                     headers=AUTH).json()
        done = _wait(c, job["id"])
        assert done["status"] == "completed", done
        f = Path(done["filepath"])
        assert f.parent.name.startswith("127.0.0.1"), f   # yt-dlp turns ":" into "_"
        assert f.is_file()


def test_subfolders_by_playlist_uses_the_list_title(tmp_path, server):
    with _client(tmp_path) as c:
        assert c.post("/settings", json={"subfolders": "playlist"},
                      headers=AUTH).status_code == 200
        job = c.post("/jobs", json={"url": f"{server}/playlist.html",
                                    "playlist_items": ""}, headers=AUTH).json()
        done = _wait(c, job["id"])
        assert done["status"] == "completed", done
        files = [Path(p) for p in done["files"] or []]
        assert len(files) == 2
        assert all(f.parent.name for f in files), files
        assert len({f.parent for f in files}) == 1  # all in ONE subfolder


def test_subfolders_off_keeps_everything_flat(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                     headers=AUTH).json()
        done = _wait(c, job["id"])
        assert Path(done["filepath"]).parent == Path(c.app.state.manager.download_dir)


def test_a_template_cannot_climb_out_of_the_download_folder(tmp_path):
    from suravidl_engine.settings import Settings

    s = Settings(path=tmp_path / "settings.json")
    for bad in ("../evil/%(title)s.%(ext)s", "/abs/%(title)s.%(ext)s",
                "a/../../evil.%(ext)s", "..\\evil.%(ext)s"):
        with pytest.raises(ValueError):
            s.update({"filename_template": bad})
    # a relative subfolder IS fine now (the review's ask)
    s.update({"filename_template": "channel/%(title).80B.%(ext)s"})
    assert s.get()["filename_template"] == "channel/%(title).80B.%(ext)s"


def test_deleting_a_subfolder_download_takes_the_empty_folder(tmp_path, server):
    with _client(tmp_path) as c:
        c.post("/settings", json={"subfolders": "site"}, headers=AUTH)
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                     headers=AUTH).json()
        done = _wait(c, job["id"])
        folder = Path(done["filepath"]).parent
        assert folder.is_dir()
        r = c.post(f"/jobs/{job['id']}/delete", headers=AUTH)
        assert r.status_code == 200, r.text
        assert not Path(done["filepath"]).exists()
        assert not folder.exists(), "the empty subfolder should not survive"


# -- 2. container / remux (review #3) ---------------------------------------

def test_container_option_sets_merge_and_remux(tmp_path):
    from suravidl_engine.download_opts import build_download_opts

    base = {"filename_template": "%(title)s.%(ext)s", "subfolders": "off"}
    auto = build_download_opts({**base, "video_container": "auto"}, tmp_path)
    assert "merge_output_format" not in auto
    assert not [p for p in auto.get("postprocessors") or []
                if p.get("key") == "FFmpegVideoRemuxer"]
    mp4 = build_download_opts({**base, "video_container": "mp4"}, tmp_path)
    assert mp4["merge_output_format"] == "mp4"
    remux = [p for p in mp4["postprocessors"] if p.get("key") == "FFmpegVideoRemuxer"]
    assert remux and remux[0]["preferedformat"] == "mp4"
    mkv = build_download_opts({**base, "video_container": "mkv"}, tmp_path)
    assert mkv["merge_output_format"] == "mkv"


def test_container_validation(tmp_path):
    from suravidl_engine.settings import Settings

    s = Settings(path=tmp_path / "settings.json")
    with pytest.raises(ValueError):
        s.update({"video_container": "avi"})
    s.update({"video_container": "mp4"})
    assert s.get()["video_container"] == "mp4"


@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_remuxing_actually_produces_an_mp4(tmp_path, server):
    """A webm fixture downloaded with container=mp4 must come out as mp4."""
    src = tmp_path / "clip.webm"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         "testsrc=size=160x120:rate=10:duration=2", "-pix_fmt", "yuv420p",
         str(src)], check=True, timeout=120)
    shutil.copy(src, FIXTURES / "clip-tmp.webm")
    try:
        with _client(tmp_path) as c:
            c.post("/settings", json={"video_container": "mp4"}, headers=AUTH)
            job = c.post("/jobs", json={"url": f"{server}/clip-tmp.webm"},
                         headers=AUTH).json()
            done = _wait(c, job["id"])
            assert done["status"] == "completed", done
            f = Path(done["filepath"])
            assert f.suffix == ".mp4", f
            meta = _ffprobe(f, "format=format_name")
            assert "mp4" in meta["format"]["format_name"]
    finally:
        (FIXTURES / "clip-tmp.webm").unlink(missing_ok=True)


# -- 3. clip / download sections (review #2) --------------------------------

def test_section_text_parses_and_normalizes():
    from suravidl_engine.download_opts import parse_sections

    assert parse_sections("1:30-2:45") == ("00:01:30", "00:02:45")
    assert parse_sections("*00:01:30-00:02:45") == ("00:01:30", "00:02:45")
    assert parse_sections("90-300") == ("00:01:30", "00:05:00")
    for bad in ("", "10:00", "5:00-1:00", "abc-def", "1:2:3:4-5:6:7:8"):
        with pytest.raises(ValueError):
            parse_sections(bad)


def test_clip_sets_download_ranges(tmp_path):
    from suravidl_engine.download_opts import build_download_opts

    opts = build_download_opts(
        {"filename_template": "%(title)s.%(ext)s", "download_sections": "00:00:01-00:00:04"},
        tmp_path)
    assert callable(opts["download_ranges"])
    assert opts["force_keyframes_at_cuts"] is True


def test_clip_is_a_per_job_override(tmp_path):
    from suravidl_engine.settings import validate_overrides

    assert validate_overrides({"download_sections": "0:10-0:20"}) == {
        "download_sections": "*00:00:10-00:00:20"}


@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_clipping_a_file_yields_a_shorter_video(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4",
                                    "overrides": {"download_sections": "0:01-0:02"}},
                     headers=AUTH).json()
        assert "id" in job, job
        done = _wait(c, job["id"])
        assert done["status"] == "completed", done
        meta = _ffprobe(done["filepath"], "format=duration")
        assert float(meta["format"]["duration"]) < 4.0, meta


# -- 4. audio presets (review #9) -------------------------------------------

def test_modern_audio_presets_exist():
    from suravidl_engine.jobs import AUDIO_PRESETS, preset_opts

    assert "audio-mp3-320" in AUDIO_PRESETS
    assert "audio-flac" in AUDIO_PRESETS
    assert "audio-opus" in AUDIO_PRESETS
    q = preset_opts("audio-mp3-320")["postprocessors"][0]
    assert q["preferredcodec"] == "mp3" and q["preferredquality"] == "320"
    assert preset_opts("audio-flac")["postprocessors"][0]["preferredcodec"] == "flac"
    assert preset_opts("audio-opus")["postprocessors"][0]["preferredcodec"] == "opus"


@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_mp3_320_download_has_320kbps(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tone.m4a",
                                    "preset": "audio-mp3-320"},
                     headers=AUTH).json()
        done = _wait(c, job["id"])
        assert done["status"] == "completed", done
        f = Path(done["filepath"])
        assert f.suffix == ".mp3", f
        meta = _ffprobe(f, "stream=codec_name,bit_rate")
        streams = meta.get("streams") or [{}]
        assert streams[0].get("codec_name") == "mp3"
        assert int(streams[0].get("bit_rate") or 0) > 300_000


# -- 5. batch queueing (review #5) ------------------------------------------

def test_batch_creates_one_job_per_link(tmp_path, server):
    with _client(tmp_path) as c:
        r = c.post("/jobs/batch", headers=AUTH, json={"urls": [
            f"{server}/tiny.mp4", f"{server}/tiny2.mp4", f"{server}/tone.m4a"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["jobs"]) == 3 and not body["skipped"]
        listed = c.get("/jobs", headers=AUTH).json()["jobs"]
        assert len(listed) == 3


def test_batch_keeps_going_when_one_link_is_bad(tmp_path, server):
    with _client(tmp_path) as c:
        r = c.post("/jobs/batch", headers=AUTH, json={"urls": [
            f"{server}/tiny.mp4", "   ", "not a url at all\n", f"{server}/tiny2.mp4"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["jobs"]) == 2
        assert body["skipped"], "the bad links must be reported, not swallowed"


def test_batch_is_capped(tmp_path, server):
    with _client(tmp_path) as c:
        r = c.post("/jobs/batch", headers=AUTH,
                   json={"urls": [f"{server}/tiny.mp4"] * 21})
        assert r.status_code == 400
        assert "at most" in r.json()["detail"].lower()


def test_batch_respects_the_raw_args_gate(tmp_path, server):
    with _client(tmp_path) as c:
        r = c.post("/jobs/batch", headers=AUTH, json={
            "urls": [f"{server}/tiny.mp4"], "raw_args": "--no-mtime"})
        assert r.status_code == 400
        assert "disabled" in r.json()["detail"].lower()


# -- 6. archive: ignore + inspect + forget (review #7) ----------------------

def test_archive_skips_and_ignore_archive_re_downloads(tmp_path, server):
    with _client(tmp_path) as c:
        c.post("/settings", json={"archive": True}, headers=AUTH)
        first = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                       headers=AUTH).json()
        done = _wait(c, first["id"])
        assert done["status"] == "completed", done

        again = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                       headers=AUTH).json()
        second = _wait(c, again["id"])
        assert "archive" in (second.get("note") or "").lower(), second

        forced = c.post("/jobs", json={
            "url": f"{server}/tiny.mp4",
            "overrides": {"archive_ignore": True}}, headers=AUTH).json()
        third = _wait(c, forced["id"])
        assert third["status"] == "completed", third
        assert "archive" not in (third.get("note") or "").lower()
        assert Path(third["filepath"]).is_file()


def test_archive_can_be_listed_and_forgotten(tmp_path, server):
    with _client(tmp_path) as c:
        c.post("/settings", json={"archive": True}, headers=AUTH)
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                     headers=AUTH).json()
        _wait(c, job["id"])
        body = c.get("/archive", headers=AUTH).json()
        assert body["count"] >= 1 and body["entries"], body
        entry = body["entries"][0]
        r = c.post("/archive/forget", json={"entry": entry}, headers=AUTH)
        assert r.status_code == 200 and r.json()["removed"] == 1
        after = c.get("/archive", headers=AUTH).json()
        assert entry not in after["entries"]


# -- 7. in-app preview player (review #10) ----------------------------------

def test_a_finished_file_can_be_streamed_with_range_support(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                     headers=AUTH).json()
        done = _wait(c, job["id"])
        r = c.get(f"/jobs/{job['id']}/stream", headers={**AUTH, "Range": "bytes=0-499"})
        assert r.status_code == 206, (r.status_code, r.text[:200])
        assert len(r.content) == 500
        body = c.get(f"/jobs/{job['id']}/stream", headers=AUTH)
        assert body.status_code == 200
        assert body.content[:8] == Path(done["filepath"]).read_bytes()[:8]


def test_the_range_handler_is_ours_not_the_response_class(tmp_path, server):
    """The Android build gets starlette 0.27 (via fastapi 0.99.1), whose
    FileResponse ignores Range outright — verified in a scratch venv: the
    whole body came back with 200 and no Content-Range, so the in-app player
    could not seek on the phone while the desktop build was fine. Range must
    therefore be implemented in `api.py`; this pins that it is.
    """
    import inspect

    import suravidl_engine.api as api_mod
    from suravidl_engine.api import create_app

    app = create_app(tmp_path, auth_token="t")
    route = next(r for r in app.routes
                 if getattr(r, "path", "") == "/jobs/{job_id}/stream")
    src = inspect.getsource(route.endpoint)
    assert "_range_span" in src and "Accept-Ranges" in src, \
        "the stream endpoint must answer Range itself"
    assert not hasattr(api_mod, "FileResponse"), \
        "api.py must not hand files to FileResponse: its Range support "\
        "depends on the starlette version, and Android pins an old one"


def test_range_parsing_edges(tmp_path):
    from suravidl_engine.api import _range_span
    size = 1000
    assert _range_span(size, None) is None
    assert _range_span(size, "") is None
    assert _range_span(size, "bytes=abc") is None            # unknown: whole file
    assert _range_span(size, "bytes=0-499") == (0, 499)
    assert _range_span(size, "bytes=500-") == (500, 999)     # open-ended
    assert _range_span(size, "bytes=-100") == (900, 999)     # suffix
    assert _range_span(size, "bytes=-5000") == (0, 999)      # suffix past the start
    assert _range_span(size, "bytes=900-99999") == (900, 999)  # clamped to EOF
    for bad in ("bytes=1000-", "bytes=50-10", "bytes=-0"):
        try:
            _range_span(size, bad)
        except ValueError:
            pass
        else:                                                # pragma: no cover
            raise AssertionError(f"{bad} should be unsatisfiable")


def test_unsatisfiable_ranges_get_416_and_whole_files_get_200(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"},
                     headers=AUTH).json()
        done = _wait(c, job["id"])
        size = Path(done["filepath"]).stat().st_size
        whole = c.get(f"/jobs/{job['id']}/stream", headers=AUTH)
        assert whole.status_code == 200 and len(whole.content) == size
        assert whole.headers["accept-ranges"] == "bytes"
        # exact bytes, not just the length: a seek that replays from byte 0
        # looks fine by length only when the range happens to start there
        want = Path(done["filepath"]).read_bytes()[200:400]
        part = c.get(f"/jobs/{job['id']}/stream",
                     headers={**AUTH, "Range": "bytes=200-399"})
        assert part.status_code == 206 and part.content == want
        assert part.headers["content-range"] == f"bytes 200-399/{size}"
        assert part.headers["content-length"] == "200"
        tail = c.get(f"/jobs/{job['id']}/stream",
                     headers={**AUTH, "Range": "bytes=-50"})
        assert tail.status_code == 206 and len(tail.content) == 50
        over = c.get(f"/jobs/{job['id']}/stream",
                     headers={**AUTH, "Range": f"bytes={size + 10}-"})
        assert over.status_code == 416
        assert over.headers["content-range"] == f"bytes */{size}"


def test_stream_refuses_unfinished_and_outside_files(tmp_path, server):
    with _client(tmp_path) as c:
        r = c.post("/jobs", json={"url": "http://127.0.0.1:1/x.mp4"}, headers=AUTH)
        if r.status_code == 200:
            assert c.get(f"/jobs/{r.json()['id']}/stream",
                         headers=AUTH).status_code in (409, 404)
        # a job row pointing outside the download folder must not stream — the
        # row is what the engine trusts, so tamper with the row itself
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret")
        mgr = c.app.state.manager
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"}, headers=AUTH).json()
        with mgr._db_lock:
            mgr._jobs[job["id"]]["status"] = "completed"
            mgr._jobs[job["id"]]["filepath"] = str(secret)
            mgr._jobs[job["id"]]["files"] = [str(secret)]
        assert c.get(f"/jobs/{job['id']}/stream", headers=AUTH).status_code in (403, 404)


# -- 8. probe extras the UI can now use (review #4 + #8) --------------------

def test_probe_payload_carries_chapters_subtitles_and_live(tmp_path, monkeypatch):
    """The engine has always returned the full info dict; these are the keys
    the review says the UI ignores — pin them so a slimmed payload cannot
    silently drop them."""
    import suravidl_engine.probe as probe_mod

    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def sanitize_info(self, info):
            return info

        def extract_info(self, url, download=False):
            return {
                "id": "abc", "title": "Live thing", "ext": "mp4",
                "is_live": True, "live_status": "is_live", "duration": 3600,
                "chapters": [{"title": "Intro", "start_time": 0.0, "end_time": 60.0}],
                "subtitles": {"en": [{"ext": "vtt"}], "id": [{"ext": "vtt"}]},
                "automatic_captions": {"ja": [{"ext": "vtt"}]},
                "formats": [{"format_id": "x", "ext": "mp4", "url": "http://x"}],
            }

    monkeypatch.setattr(probe_mod.yt_dlp, "YoutubeDL", FakeYDL)
    out = probe_mod.probe("http://example.com/live")
    assert out["is_live"] is True and out["live_status"] == "is_live"
    assert out["chapters"][0]["title"] == "Intro"
    assert set(out["subtitles"]) == {"en", "id"}
    assert set(out["automatic_captions"]) == {"ja"}


def test_subtitles_can_be_converted_to_srt(tmp_path):
    from suravidl_engine.download_opts import build_download_opts

    opts = build_download_opts({
        "filename_template": "%(title)s.%(ext)s",
        "subtitles_mode": "sidecar", "subtitles_langs": "en",
        "subtitles_to_srt": True}, tmp_path)
    conv = [p for p in opts["postprocessors"] if p.get("key") == "FFmpegSubtitlesConvertor"]
    assert conv and conv[0]["format"] == "srt"
    assert opts["subtitlesformat"] == "srt"
    plain = build_download_opts({
        "filename_template": "%(title)s.%(ext)s",
        "subtitles_mode": "sidecar", "subtitles_langs": "en",
        "subtitles_to_srt": False}, tmp_path)
    assert not [p for p in plain.get("postprocessors") or []
                if p.get("key") == "FFmpegSubtitlesConvertor"]


# -- 9. the UI actually exposes the new features ----------------------------
# The engine tests above prove the behaviour; these pin the wiring, because a
# feature nobody can reach is not shipped.

def test_the_ui_exposes_every_v22_feature():
    html = (ROOT / "src/suravidl_engine/web/index.html").read_text()
    js = (ROOT / "src/suravidl_engine/web/app.js").read_text()
    for ident in ("setSubfolders", "setContainer", "setSubSrt", "setLiveFromStart",
                  "archiveField",
                  "archiveShow", "archiveList", "batchRow", "batchBtn",
                  "audioMore", "ovClipStart", "ovClipEnd", "ovContainer",
                  "ovArchive", "liveRow", "subsRow", "chapterRow",
                  "playModal", "playBody", "playClose"):
        assert f'id="{ident}"' in html, ident
    # the stream URL carries the page's own token (a <video> cannot send a header)
    assert "/stream?token=" in js
    # batch detection + the two new endpoints are wired
    assert '"/jobs/batch"' in js and '"/archive"' in js and '"/archive/forget"' in js


# -- 10. pause / resume (review #6) ------------------------------------------

class _SlowHandler(http.server.SimpleHTTPRequestHandler):
    """Serve one URL slowly and with range support, so a download is still
    running when the test pauses it. (SimpleHTTPRequestHandler already does
    ranges for real files; this one dribbles on purpose.)"""

    payload = b"\x00" * 1_400_000
    offsets: list[int] = []

    def log_message(self, *a):        # keep the test output quiet
        pass

    def do_GET(self):
        if not self.path.startswith("/slow.mp4"):
            self.send_error(404)
            return
        size = len(self.payload)
        m = re.match(r"bytes=(\d+)-", self.headers.get("Range") or "")
        start = int(m.group(1)) if m else 0
        _SlowHandler.offsets.append(start)
        body = self.payload[start:]
        self.send_response(206 if start else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        if start:
            self.send_header("Content-Range", f"bytes {start}-{size - 1}/{size}")
        self.end_headers()
        step = 64 * 1024
        for i in range(0, len(body), step):
            try:
                self.wfile.write(body[i:i + step])
            except Exception:       # the client went away — that is the point
                return
            time.sleep(0.12)


@pytest.mark.skipif(not HAS_FFMPEG, reason="the download path needs ffmpeg")
def test_pause_keeps_the_bytes_and_resume_continues(tmp_path):
    _SlowHandler.offsets = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/slow.mp4"
    try:
        with _client(tmp_path) as c:
            job = c.post("/jobs", json={"url": url}, headers=AUTH).json()
            for _ in range(300):            # wait until bytes are on disk
                cur = c.get(f"/jobs/{job['id']}", headers=AUTH).json()
                prog = cur.get("progress") or {}
                if cur["status"] == "downloading" and prog.get("downloaded_bytes"):
                    break
                time.sleep(0.05)
            p = c.post(f"/jobs/{job['id']}/pause", headers=AUTH)
            assert p.status_code == 200, p.text
            assert p.json()["status"] == "paused"
            parts = list(Path(tmp_path).rglob("*.part"))
            assert parts, "pausing must keep the partial file"
            assert parts[0].stat().st_size > 0
            time.sleep(0.8)                 # the worker must really stop
            still = c.get(f"/jobs/{job['id']}", headers=AUTH).json()
            assert still["status"] == "paused", still
            assert "paused" in (still.get("error") or "")
            left = list(Path(tmp_path).rglob("*.part"))
            assert left, "the partial file is still there after the pause"
            # resume: a new row that continues from the bytes already on disk
            r = c.post(f"/jobs/{job['id']}/resume", headers=AUTH)
            assert r.status_code == 200, r.text
            done = _wait(c, r.json()["id"])
            assert done["status"] == "completed", done
            assert Path(done["filepath"]).stat().st_size == len(_SlowHandler.payload)
            assert _SlowHandler.offsets[-1] > 0, \
                "resume must continue, not start from zero"
    finally:
        srv.shutdown()


def test_pausing_a_queued_job_keeps_it_out_of_the_worker(tmp_path, server):
    with _client(tmp_path) as c:
        c.post("/settings", json={"max_concurrent": 1}, headers=AUTH)
        first = c.post("/jobs", json={"url": f"{server}/tiny.mp4"}, headers=AUTH).json()
        second = c.post("/jobs", json={"url": f"{server}/tiny2.mp4"}, headers=AUTH).json()
        p = c.post(f"/jobs/{second['id']}/pause", headers=AUTH)
        assert p.status_code == 200, p.text
        assert p.json()["status"] == "paused"
        _wait(c, first["id"])
        time.sleep(0.6)
        after = c.get(f"/jobs/{second['id']}", headers=AUTH).json()
        assert after["status"] == "paused", after
        # resume puts it back in the queue and it finishes
        r = c.post(f"/jobs/{second['id']}/resume", headers=AUTH)
        done = _wait(c, r.json()["id"])
        assert done["status"] == "completed", done


def test_pause_and_resume_refuse_the_wrong_states(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"}, headers=AUTH).json()
        done = _wait(c, job["id"])
        assert done["status"] == "completed"
        assert c.post(f"/jobs/{job['id']}/pause", headers=AUTH).status_code == 409
        assert c.post(f"/jobs/{job['id']}/resume", headers=AUTH).status_code == 409


# -- 11. edit & retry (review #11) -------------------------------------------

def _fail_it(c, job_id, message="HTTP Error 403: Forbidden"):
    """Put a job in the error state a real failure would leave it in."""
    mgr = c.app.state.manager
    with mgr._db_lock:
        mgr._jobs[job_id]["status"] = "error"
        mgr._jobs[job_id]["error"] = message


def test_retry_can_carry_edits(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4",
                                    "overrides": {"video_container": "mp4"}},
                     headers=AUTH).json()
        _wait(c, job["id"])
        _fail_it(c, job["id"])
        r = c.post(f"/jobs/{job['id']}/retry", headers=AUTH, json={
            "fmt": "best",
            "overrides": {"video_container": "mkv"}})
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["id"] != job["id"]
        assert new["fmt"] == "best"
        assert new["overrides"]["video_container"] == "mkv"
        assert _wait(c, new["id"])["status"] == "completed"


def test_retry_without_a_body_reuses_the_original_request(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4",
                                    "overrides": {"subtitles_mode": "sidecar"}},
                     headers=AUTH).json()
        _wait(c, job["id"])
        _fail_it(c, job["id"])
        r = c.post(f"/jobs/{job['id']}/retry", headers=AUTH)
        assert r.status_code == 200, r.text
        assert r.json()["overrides"]["subtitles_mode"] == "sidecar"


def test_the_raw_args_gate_holds_on_a_retry_with_edits(tmp_path, server):
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": f"{server}/tiny.mp4"}, headers=AUTH).json()
        _wait(c, job["id"])
        _fail_it(c, job["id"])
        r = c.post(f"/jobs/{job['id']}/retry", headers=AUTH,
                   json={"raw_args": "--exec whoami"})
        assert r.status_code == 400
        assert "disabled" in r.json()["detail"].lower()


# -- 12. live streams (review #8) --------------------------------------------

def test_live_from_start_is_plumbed(tmp_path):
    from suravidl_engine.download_opts import build_download_opts

    assert build_download_opts({"live_from_start": True},
                               tmp_path)["live_from_start"] is True
    assert "live_from_start" not in build_download_opts({}, tmp_path)
    # a per-download override may switch it either way
    from suravidl_engine.settings import validate_overrides

    assert validate_overrides({"live_from_start": True}) == {"live_from_start": True}
