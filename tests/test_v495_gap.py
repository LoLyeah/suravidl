"""v0.49.5 "the gap" — the hint block touched the transport.

Measured the Download page's vertical rhythm at 412: paste→scopes 16,
scopes→hint 16, hint→transport **0**, transport→the-only row 16. The dashed
hint's bottom edge sat exactly on the TAKE plate, so the owner's circle was a
missing margin, not a tight one.

Also heard the sub-nav's 14px against a page that runs on 16.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.49.5"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the gap"
    assert len(ENTRIES) == 10


def test_the_hint_keeps_its_distance():
    assert "#dlEmpty { margin-bottom: 16px; }" in CSS


def test_the_subnav_speaks_the_page_scale():
    assert "margin: 0 0 16px; border-bottom: 1px solid var(--line-soft); }" in CSS
