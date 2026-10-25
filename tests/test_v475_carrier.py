"""v0.47.5 "the carrier" — image-wrapped segments are refused with the way
out, and "auto" picks the container the requested job needs.

The 2026-10-18 reanime report: the HD-2 server serves every segment as a
RIFF/WEBP carrier (opaque payload, no EXT-X-KEY at all — its player
unwraps it in wasm). The engine downloaded the carriers and died at the
merge with "Error opening output files: Invalid argument". The first
segment is now peeked before anything downloads: a carrier fails the job
at once, with the guidance that actually helps (use the other server).
And the container policy: auto + subtitles=embed → MKV, where embedding is
a copy and not a lossy encode.
"""
import base64
import functools
import http.server
import subprocess
import threading
import time

import pytest

from suravidl_engine import cut
from suravidl_engine.download_opts import build_download_opts
from suravidl_engine.jobs import JobManager
from suravidl_engine.settings import DEFAULTS

XOR = b"0123456789abcdef0123456789abcdef"
KEY_B64 = base64.b64encode(XOR).decode()
REF = "https://flixcloud.cc/"

pytestmark = pytest.mark.skipif(not cut.ffmpeg_exe(),
                                reason="no ffmpeg on this box")


def _scramble(text: str) -> str:
    raw = text.encode()
    out = bytes(b ^ XOR[i % len(XOR)] for i, b in enumerate(raw))
    return base64.b64encode(out).decode()


def _carrier_rig(tmp_path):
    """One rendition whose segments are image carriers, playlist veiled."""
    d = tmp_path / "cdn"
    v = d / "video"
    v.mkdir(parents=True)
    subprocess.run(
        [cut.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=10", "-t", "2",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-f", "hls", "-hls_time", "1", "-hls_playlist_type", "vod",
         "-hls_segment_filename", str(v / "seg%d.png"),
         str(v / "index.m3u8")], check=True)
    # the disguise: every segment wears a fake RIFF/WEBP header, like HD-2
    for seg in v.glob("seg*.png"):
        seg.write_bytes(b"RIFF\x00\x00\x00\x00WEBP" + seg.read_bytes())
    (v / "index.m3u8").write_text(_scramble((v / "index.m3u8").read_text()))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(d))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", srv


def _manager(dd):
    def dopts(dir_, raw_args=None, overrides=None):
        s = {**DEFAULTS, "download_dir": str(dir_)}
        return build_download_opts(s, dir_, raw_args=raw_args)
    return JobManager(download_dir=dd, db_path=dd / "jobs.db", max_concurrent=1,
                      download_opts=dopts)


def _wait(mgr, jid, timeout=60.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = mgr.get(jid)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.2)
    raise TimeoutError(mgr.get(jid)["status"])


def test_a_carrier_server_is_refused_before_the_download(tmp_path):
    base, srv = _carrier_rig(tmp_path)
    try:
        dd = tmp_path / "dl"
        dd.mkdir()
        mgr = _manager(dd)
        job = mgr.create(f"{base}/video/index.m3u8",
                         extra_headers={"referer": REF}, xor_key=KEY_B64)
        done = _wait(mgr, job["id"])
        assert done["status"] == "error"
        err = done.get("error") or ""
        assert "wraps its video segments in fake images" in err
        assert "HD-1" in err
        # the refusal is early: no media file was even started
        assert not [p for p in dd.iterdir()
                    if p.suffix in (".mp4", ".mkv", ".ts", ".part")]
    finally:
        srv.shutdown()


def test_auto_container_picks_mkv_for_embedded_subtitles():
    s = {**DEFAULTS, "subtitles_mode": "embed", "video_container": "auto"}
    opts = build_download_opts(s, "/tmp")
    assert opts["merge_output_format"] == "mkv"
    assert any("auto picked MKV" in n for n in opts.get("__sv_notices", []))


def test_an_explicit_container_still_wins():
    s = {**DEFAULTS, "subtitles_mode": "embed", "video_container": "mp4"}
    opts = build_download_opts(s, "/tmp")
    assert opts["merge_output_format"] == "mp4"
    assert not any("auto picked MKV" in n for n in opts.get("__sv_notices", []))


def test_plain_auto_is_untouched():
    s = {**DEFAULTS, "subtitles_mode": "off", "video_container": "auto"}
    opts = build_download_opts(s, "/tmp")
    assert "merge_output_format" not in opts


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__, whatsnew

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # retired by v0.47.15 "the spare": the card is rolling, and the
    # behaviour this release pinned is covered by the tests above
    assert "0.47.5" not in [e["version"] for e in whatsnew.ENTRIES]
    assert "the carrier" not in [e["title"].lower() for e in whatsnew.ENTRIES]
