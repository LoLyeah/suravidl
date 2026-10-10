"""v0.45.32 "the slideshow" — a TikTok photo post says so.

Owner report (2026-10-10): pasted a vt.tiktok.com share link, the app said
"no extractor knows this page". The link resolves fine — to
/@user/photo/<id>, a slideshow of images with a music track, which yt-dlp
has no extractor for (verified against the newest release, then
2026.08.19). "No extractor" was true but useless: it sent the owner
hunting for a broken thing that was never a video. The engine now
recognizes the resolved /photo/ address inside yt-dlp's own error text
(the input may be a short link, so the text is the only place it
appears) and answers with what it actually is; the app renders its own
matching sentence, translated.
"""
from pathlib import Path

from suravidl_engine.auth import (UNSUPPORTED_HINT, UNSUPPORTED_PHOTO_HINT,
                                  unsupported_error)

ROOT = Path(__file__).resolve().parents[1]
APPJS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")


def test_a_tiktok_photo_post_gets_its_own_sentence():
    text = ("ERROR: Unsupported URL: https://www.tiktok.com/@marius_thegreat1/"
            "photo/7682515265854213409?_r=1&_t=ZS-x")
    got = unsupported_error(text)
    assert got and got["unsupported"] is True
    assert got["hint"] == UNSUPPORTED_PHOTO_HINT
    assert "photo post" in got["hint"] and "slideshow" in got["hint"]
    assert got["hint"] != UNSUPPORTED_HINT


def test_an_ordinary_unsupported_url_keeps_the_generic_hint():
    got = unsupported_error("ERROR: Unsupported URL: https://example.com/x")
    assert got and got["unsupported"] is True
    assert got["hint"] == UNSUPPORTED_HINT


def test_a_tiktok_video_url_is_not_flagged_as_a_slideshow():
    got = unsupported_error(
        "ERROR: Unsupported URL: https://www.tiktok.com/@u/video/12345")
    assert got and got["hint"] == UNSUPPORTED_HINT


def test_non_unsupported_text_stays_none():
    assert unsupported_error("ERROR: HTTP Error 403: Forbidden") is None
    assert unsupported_error("") is None


def test_the_app_renders_it_and_translates_it():
    # both arms (engine verdict + plain text) carry the branch
    assert APPJS.count("TikTok photo post") >= 2
    # and the exact sentence has an Indonesian entry in the same
    # dictionary that holds its "no extractor" sibling
    assert "ini postingan foto TikTok" in APPJS
