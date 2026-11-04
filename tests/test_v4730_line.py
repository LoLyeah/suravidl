"""v0.47.30 "the line" — the source field is one line again.

v0.47.28 gave `.paste input` `flex: 1 1 220px` so it would not collapse in the
row. On a phone `.paste` becomes a COLUMN (`style.css:1497`), and in a column
the flex basis is the HEIGHT: the URL field rendered 220px tall (the owner's
screenshot). `flex: 1 1 auto` + a min-width keeps the row honest and the field
one line in both directions.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS_RAW = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
CSS = re.sub(r"/\*.*?\*/", "", CSS_RAW, flags=re.S)   # comments quote the trap


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    # retired by v0.49.3 "the ellipsis"; the behaviour keeps its own pins
    assert not any(e["title"].lower() == "the line" for e in ENTRIES)


def test_the_field_has_no_flex_basis():
    body = CSS[CSS.index(".paste input {"):]
    body = body[:body.index("\n}")]
    assert "flex: 1 1 auto" in body
    assert "flex-basis" not in body and "220px" not in body, (
        "a basis here becomes the field's height once .paste is a column")


def test_the_phone_layout_is_still_a_column():
    assert ".paste { flex-direction: column; }" in CSS
    assert ".paste .btn { width: 100%; }" in CSS
