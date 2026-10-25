"""v0.47.12 "the whole" — without ffmpeg, pick a stream that is already whole.

Owner's macOS report (2026-10-24): an Instagram reel on a Mac with ffmpeg
installed failed with "the last step needs ffmpeg". Two causes, both fixed:

1. a Finder-launched app has no PATH, so a Homebrew ffmpeg was invisible —
   the resolver now also looks in the package managers' own prefixes;
2. when ffmpeg genuinely is absent, the DEFAULT pick was yt-dlp's
   bestvideo+bestaudio — two tracks only ffmpeg can join. The default now
   falls back to the best stream that needs no join, and says so.
"""
from pathlib import Path

from suravidl_engine import cut, download_opts as do
from suravidl_engine import jobs

ROOT = Path(__file__).resolve().parents[1]
JOBS_SRC = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text()


def test_with_ffmpeg_the_best_quality_stays(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.delenv("SURAVIDL_FFMPEG", raising=False)
    assert cut.ffmpeg_exe() == "/usr/bin/ffmpeg"
    assert jobs._default_format(True) is None, "yt-dlp's own best, merged"


def test_without_ffmpeg_the_default_is_a_whole_stream():
    assert jobs._default_format(False) == "best[ext=mp4]/best"


def test_the_download_path_asks_that_helper():
    assert "_default_format(bool(_ffmpeg_exe()))" in JOBS_SRC
    assert "NO_FFMPEG_PICK" in JOBS_SRC


def test_a_mac_app_finds_a_package_managers_ffmpeg(monkeypatch):
    monkeypatch.setenv("SURAVIDL_FFMPEG", "")
    monkeypatch.setattr(cut.sys, "platform", "darwin")
    monkeypatch.setattr(cut.shutil, "which", lambda name: None)
    monkeypatch.setattr(cut, "_MAC_FFMPEG", ("/opt/homebrew/bin/ffmpeg",))
    monkeypatch.setattr(cut.os.path, "isfile", lambda p: p == "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setattr(cut.os, "access", lambda p, mode: True)
    assert cut.ffmpeg_exe() == "/opt/homebrew/bin/ffmpeg"


def test_the_env_override_still_wins(monkeypatch):
    monkeypatch.setenv("SURAVIDL_FFMPEG", "/android/jniLibs/ffmpeg")
    assert cut.ffmpeg_exe() == "/android/jniLibs/ffmpeg"


def test_no_remux_without_ffmpeg(monkeypatch):
    monkeypatch.setattr(do, "ffmpeg_exe", lambda: "")
    opts = do.build_download_opts({"video_container": "mp4"}, "/tmp")
    keys = [p.get("key") for p in opts.get("postprocessors") or []]
    assert "FFmpegVideoRemuxer" not in keys, "a remux is an ffmpeg pass"
    assert any("needs ffmpeg" in n for n in opts.get("__sv_notices") or [])


def test_the_remux_returns_when_ffmpeg_does(monkeypatch):
    monkeypatch.setattr(do, "ffmpeg_exe", lambda: "/usr/bin/ffmpeg")
    opts = do.build_download_opts({"video_container": "mkv"}, "/tmp")
    keys = [p.get("key") for p in opts.get("postprocessors") or []]
    assert "FFmpegVideoRemuxer" in keys
