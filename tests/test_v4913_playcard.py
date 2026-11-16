"""v0.49.13 "the take" — the play sheet on a phone.

Field report: on Android the sheet's head held a six-line title, a time range
and four buttons in one flex row. The buttons squeezed to ~78px, "Cut this
take" broke across two lines, and the title ran under the controls.

The fix is a phone-width block scoped to #playModal: title on its own line
(clamped to two), the four buttons in a two-by-two grid, each label whole.
Verified in a real browser at 390x844 and 360x640 — no horizontal overflow,
buttons 151px each at 360 — not just by reading the CSS.
"""
from __future__ import annotations

import pathlib
import re

from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()


def phone_block() -> str:
    start = CSS.index("@media (max-width: 560px) {\n  .overlay { padding: 10px; }")
    depth = 0
    for i, ch in enumerate(CSS[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return CSS[start:i]
    raise AssertionError("the phone block never closes")


def test_the_notes_name_this_release():
    assert ENTRIES[0]["version"] == "0.49.13"
    assert ENTRIES[0]["title"].lower() == "the take"


def test_the_head_becomes_a_two_by_two():
    block = phone_block()
    assert "#playModal .modal-head" in block
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in block


def test_the_title_takes_its_own_line_and_stops_at_two():
    block = phone_block()
    head = block[block.index("#playModal .modal-head .title"):]
    assert "grid-column: 1 / -1;" in head
    assert "-webkit-line-clamp: 2;" in head
    assert "overflow-wrap: anywhere;" in head


def test_every_button_keeps_its_words_whole():
    block = phone_block()
    btns = block[block.index("#playModal .modal-head .btn"):]
    assert "white-space: nowrap;" in btns
    assert "width: 100%;" in btns


def test_the_picture_leaves_room_for_the_controls():
    assert ".player-video { max-height: 56vh; }" in phone_block()


def test_the_sheet_still_carries_the_four_controls():
    for ident in ("markIn", "markOut", "cutTake", "playClose"):
        assert f'id="{ident}"' in HTML


def test_the_block_is_scoped_to_the_play_sheet():
    """Other modals carry one button — they must keep their single row."""
    block = phone_block()
    assert ".modal-head {" not in block.replace("#playModal .modal-head", "")
    assert not re.search(r"^\s{2}\.modal-head\s*\{", block, re.M)
