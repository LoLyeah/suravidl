"""v0.47.24 "the wash" — a tab switch must not put an opacity fade above glass.

Measured in Chrome on a glass card over a striped backdrop: edge energy 0.24
while the card can blur, 52.19 the moment any ancestor sits at opacity < 1.
`will-change: backdrop-filter`, `translateZ(0)` and `isolation: isolate` do
not help — the spec makes the ancestor a backdrop root for the whole
animation, so every frost beneath it goes flat and snaps back at the end
("the blur is gone and then abruptly appears"). The arrival is therefore a
wash pseudo-element, which is painted over the panel but is never an
ancestor of the cards.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS_RAW = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
# comments quote the very tokens this file forbids ("a retained (fill: both)")
CSS = re.sub(r"/\*.*?\*/", "", CSS_RAW, flags=re.S)
JS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.47.24"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the wash"
    assert len(ENTRIES) == 10
    for item in ENTRIES[0]["items"]:
        assert 0 < len(item) <= 220


def test_no_panel_fades_itself():
    """The law: an opacity (or filter) animation on a panel is a backdrop
    root, and every backdrop-filter beneath it dies for the duration."""
    assert "@keyframes tabIn" not in CSS
    assert "@keyframes spanelIn" not in CSS
    assert "animation: tabIn" not in CSS
    assert "animation: spanelIn" not in CSS
    assert re.search(r"\.tab-in\s*\{[^}]*opacity", CSS) is None
    assert re.search(r"\.spanel-in\s*\{[^}]*opacity", CSS) is None


def test_the_arrival_is_a_wash_that_clears():
    block = CSS[CSS.index(".tab-in::after"):]
    block = block[:block.index("\n}")]
    assert "position: absolute" in block
    assert "pointer-events: none" in block       # never eats the click
    assert "background: var(--bg)" in block
    assert "opacity: 0" in block                 # rests invisible
    assert "animation: tabWash" in block
    # a `from` with no `to` settles at the element's own opacity (1) — an
    # opaque slab over the panel, which is what the first cut of this did
    frames = CSS[CSS.index("@keyframes tabWash"):].splitlines()[0]
    assert "from { opacity: .45" in frames
    assert "to { opacity: 0" in frames


def test_the_sub_tabs_get_the_same_treatment():
    assert ".spanel-in::after" in CSS
    frames = CSS[CSS.index("@keyframes spanelWash"):].splitlines()[0]
    assert "from { opacity: .45" in frames and "to { opacity: 0" in frames


def test_no_retained_animation_fill():
    """v0.45.11: `fill: both` keeps the element animating for ever, which is
    the same backdrop root with no end."""
    for bad in ("fill: both", "fill: forwards", "fill:backwards", "fill: backwards"):
        assert bad not in CSS


def test_the_switch_still_marks_the_arrival():
    assert 'incoming.classList.add("tab-in")' in JS
    assert 'classList.add("spanel-in")' in JS or "spanel-in" in JS
