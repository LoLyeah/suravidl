"""v0.45.5 "the disguise" — the TikTok retries change their face.

The Android report (2026-10-05): "TikTok video download is still failed on
mobile" — the "Unexpected response from webpage request" refusal, three
identical retries, three identical refusals. A refusal is per-fingerprint;
each retry now wears a different user agent (the served-when-different
workaround yt-dlp/yt-dlp#17604 documents), while attempt one stays exactly
what the caller asked for.
"""
import types

import pytest
import yt_dlp

from suravidl_engine import extract

REFUSAL = ("ERROR: [TikTok] 7685267152395554066: Unexpected response from "
           "webpage request; please report this issue")


class _RecordingYDL:
    calls = []

    def __init__(self, opts, fails=2, message=None):
        self.fails = fails
        self.message = message or REFUSAL
        type(self).calls.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        if len(type(self).calls) <= self.fails:
            raise yt_dlp.utils.DownloadError(self.message)
        return {"id": "ok"}

    def sanitize_info(self, info):
        return info


def _install(monkeypatch, fails=2, message=None):
    _RecordingYDL.calls = []

    def build(opts):
        return _RecordingYDL(opts, fails=fails, message=message)

    monkeypatch.setattr(extract, "yt_dlp", types.SimpleNamespace(
        YoutubeDL=build, utils=yt_dlp.utils))
    return extract


def test_the_retries_change_their_face(monkeypatch):
    extract = _install(monkeypatch, fails=2)
    out = extract.extract_info({"http_headers": {"Accept-Language": "en"}},
                               "https://www.tiktok.com/@x/video/1",
                               download=False, sleep=lambda s: None)
    assert out == {"id": "ok"}
    o1, o2, o3 = _RecordingYDL.calls
    # attempt one is untouched — no UA conjured where the caller had none
    assert "User-Agent" not in (o1.get("http_headers") or {})
    # the retries wear the documented faces and keep the caller's headers
    assert o2["http_headers"]["User-Agent"].startswith(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0)")
    assert o3["http_headers"]["User-Agent"].endswith("OPR/118.0.0.0")
    assert o2["http_headers"]["Accept-Language"] == "en"
    assert extract.ATTEMPTS == len(extract.RETRY_USER_AGENTS)


def test_a_caller_ua_survives_attempt_one(monkeypatch):
    extract = _install(monkeypatch, fails=1)
    extract.extract_info({"http_headers": {"User-Agent": "Caller/1.0"}},
                         "https://vt.tiktok.com/abc/", download=False,
                         sleep=lambda s: None)
    assert _RecordingYDL.calls[0]["http_headers"]["User-Agent"] == "Caller/1.0"
    assert _RecordingYDL.calls[1]["http_headers"]["User-Agent"] != "Caller/1.0"


def test_non_tiktok_failures_never_wear_a_disguise(monkeypatch):
    extract = _install(monkeypatch, fails=99,
                       message="ERROR: [youtube] xyz: This video is unavailable")
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://youtube.com/watch?v=x",
                             download=False, sleep=lambda s: None)
    assert len(_RecordingYDL.calls) == 1
    assert "http_headers" not in _RecordingYDL.calls[0]
