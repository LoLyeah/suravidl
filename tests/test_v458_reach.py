"""v0.45.8 "the reach" — the whole job card flips the fold, not one word.

The report (2026-10-06, phone): expanding a queue card worked only from
the title text at the top left — the pills, the stamp, the empty middle
and the path row did nothing, because the toggle was wired to the title
span alone. The row carries the handler now, with a guard that stands
aside for anything doing its own job (buttons, links, fields, the error
text with its own tap).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def _row_block():
    i = APP.find("function jobRow(j)")
    j = APP.find("row.append(top);", i)
    assert i != -1 and j != -1
    return APP[i:j]


def test_the_row_carries_the_flip_with_a_guard():
    seg = _row_block()
    assert "const flip = () =>" in seg
    assert "row.onclick = (e) =>" in seg
    guard = seg.split("row.onclick", 1)[1].split("};", 1)[0]
    assert "closest(" in guard
    for bit in ("button", "a,", "input", "select", "textarea", ".jerr"):
        assert bit in guard, bit
    # no double flip: a title click must bubble into the row handler alone
    assert "title.onclick" not in seg


def test_the_keyboard_path_stays_on_the_title():
    seg = _row_block()
    assert "title.tabIndex = 0" in seg
    assert "title.onkeydown" in seg
    tail = seg.split("title.onkeydown", 1)[1]
    assert "flip()" in tail


def test_the_card_reads_as_tappable():
    i = CSS.find(".job {")
    blk = CSS[i:CSS.find("}", i)]
    assert "cursor: pointer" in blk, blk
    # and the title keeps its own cue + focus ring
    ti = CSS.find(".jobtitle {")
    assert "cursor: pointer" in CSS[ti:ti + 220]
    assert ".jobtitle:focus-visible" in CSS
