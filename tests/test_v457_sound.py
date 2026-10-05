"""v0.45.7 "the sound" — TikTok picks keep the video's own soundtrack.

The report (2026-10-05): "the audio cut after a minute" on
https://vt.tiktok.com/ZSbQpgRQC/ — a 10:33 video whose saved file went
silent at 1:00. yt-dlp's TikTok `audio` format is `music.playUrl`: the
video's SOUND as a separate file, a ~60 s preview for licensed songs and
no duration attached, so a `bv*+ba` pick merges sixty seconds of song
under ten minutes of video. The video's complete soundtrack lives inside
the muxed formats; excluding the music file from the audio side makes the
pick fall back to those (TikTok offers no other audio-only stream today).
"""
import types

import yt_dlp

from suravidl_engine import download_opts, extract
from suravidl_engine.download_opts import QUALITY_BY_FMT, tiktok_safe_format

VIDEO_MP4_1080 = ("bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080][ext=mp4]"
                  "/bv*[height<=1080]+ba/b[height<=1080]/b")


def _accepts(fmt):
    yt_dlp.YoutubeDL({"quiet": True}).build_format_selector(fmt)


def test_every_pick_rewrites_and_stays_valid():
    for fmt in QUALITY_BY_FMT:
        safe = tiktok_safe_format(fmt)
        assert "+ba[format_id!=audio]/" in safe or "+ba[format_id!=audio][" in safe, fmt
        assert "+ba/" not in safe and "+ba[" not in safe.replace("+ba[format_id!=audio]", ""), safe
        _accepts(safe)   # yt-dlp's own parser, on the result
        _accepts(fmt)    # ...and on the original, which must not have moved


def test_the_mp4_intents_rewrite_both_ladders():
    safe = tiktok_safe_format(VIDEO_MP4_1080)
    assert "+ba[format_id!=audio][ext=m4a]" in safe
    assert "+ba[format_id!=audio]/b[height<=1080]" in safe
    _accepts(safe)


def test_audio_and_custom_expressions_pass_untouched():
    for fmt in ("bestaudio/best", "137+bestaudio/best", "best", "137", "bv*/b"):
        assert tiktok_safe_format(fmt) == fmt, fmt


def test_no_pick_becomes_the_safe_best():
    safe = tiktok_safe_format(None)
    assert safe == "bv*+ba[format_id!=audio]/b"
    _accepts(safe)


class _RecordingYDL:
    calls = []

    def __init__(self, opts):
        type(self).calls.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return {"id": "ok"}

    def sanitize_info(self, info):
        return info


def _install(monkeypatch):
    _RecordingYDL.calls = []
    monkeypatch.setattr(extract, "yt_dlp", types.SimpleNamespace(
        YoutubeDL=lambda opts: _RecordingYDL(opts), utils=yt_dlp.utils))


def test_only_tiktok_urls_get_the_rewrite(monkeypatch):
    _install(monkeypatch)
    extract.extract_info({"format": "bv*+ba/b"}, "https://vt.tiktok.com/ZSbQpgRQC/",
                         download=False, sleep=lambda s: None)
    assert _RecordingYDL.calls[0]["format"] == "bv*+ba[format_id!=audio]/b"

    extract.extract_info({"format": "bv*+ba/b"}, "https://www.youtube.com/watch?v=x",
                         download=False, sleep=lambda s: None)
    assert _RecordingYDL.calls[1]["format"] == "bv*+ba/b"

    extract.extract_info({"format": "bestaudio/best"}, "https://tiktok.com/@x/video/1",
                         download=False, sleep=lambda s: None)
    assert _RecordingYDL.calls[2]["format"] == "bestaudio/best"

    extract.extract_info({}, "https://vm.tiktok.com/abc/",
                         download=False, sleep=lambda s: None)
    assert _RecordingYDL.calls[3]["format"] == "bv*+ba[format_id!=audio]/b"

    extract.extract_info({}, "https://www.youtube.com/watch?v=x",
                         download=False, sleep=lambda s: None)
    assert "format" not in _RecordingYDL.calls[4]
