"""v0.49.1 "the thumb" — the two adaptation gaps a width sweep found.

1. Every control honoured the 44px thumb floor except the fields: selects and
   inputs sat at 40px and 13-14px. iOS zooms the page when a field under 16px
   takes focus, and a select is the control a phone user hits most here.
2. A phone on its side is ~360px tall. The floating Save strip took a third of
   that and covered the scheme chips, so on short viewports it joins the flow.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.49.1" and e["title"].lower() == "the thumb"
               for e in ENTRIES)


def test_fields_join_the_thumb_floor():
    # the big coarse block is the second one; anchor on its first selector
    start = CSS.index('@media (pointer: coarse) {\n  .btn, .btn.sm')
    block = CSS[start:][:2200]
    assert "input[type=\"text\"], input[type=\"url\"]" in block
    assert "min-height: 44px; font-size: 16px;" in block


def test_a_short_viewport_drops_the_floating_save_strip():
    assert "@media (max-height: 480px)" in CSS
    block = CSS[CSS.index("@media (max-height: 480px)"):][:400]
    assert "#panel-settings .modal-foot" in block
    assert "#panel-ytdlp .foot-row" in block
    assert "position: static" in block


def test_the_floor_is_scoped_to_touch():
    """A mouse-driven desktop keeps the compact 13px field."""
    assert "input[type=\"url\"] { min-height: 44px" not in CSS.replace("input[type=\"url\"], input[type=\"search\"]", "")
