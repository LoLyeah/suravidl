"""v0.47.25 "the dissolve" — the frost is the thing that must not move.

v0.47.24 replaced the panel's opacity fade with a `::after` wash. Argon's
second pass rejected it, and the objections were checkable and right: the
transport (`z-index: 30`) and the save strip (`3`) painted above the veil's
`z-index: 1`, so pinned furniture stayed bright while cards dimmed; the veil
was `background: var(--bg)`, which over white cards in the light theme flashed
beige; and at `--t-fast` with e-out it was spent in two frames.

The rule that survives all of it: a glass plate must never sit under an
opacity < 1 ancestor, and a plank painted over the page is a different effect
wearing the fade's name. So the plates stay at opacity 1 and only their
CONTENTS dissolve in — measured: no opaque ancestor at any point in the
switch, card backdrop-filter still `blur(14px) saturate(1.15)`.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS_RAW = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
CSS = re.sub(r"/\*.*?\*/", "", CSS_RAW, flags=re.S)
JS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    # retired by v0.48.3 "the follow"; the behaviour keeps its own tests
    assert not any(e["title"].lower() == "the dissolve" for e in ENTRIES)


def test_no_plate_is_faded():
    """Neither the panel nor a card may animate opacity: the first roots the
    glass, the second fades the frost itself."""
    assert "@keyframes tabIn" not in CSS
    assert "@keyframes spanelIn" not in CSS
    assert re.search(r"\.tab-in\s*\{[^}]*opacity", CSS) is None
    assert re.search(r"\.card\s*\{[^}]*animation", CSS) is None


def test_only_the_contents_dissolve():
    assert "@keyframes contentIn { from { opacity: 0; } }" in CSS
    block = CSS[CSS.index(".tab-in > :not(.card)"):]
    block = block[:block.index("@keyframes")]
    assert ".tab-in > :not(.card):not(.transport):not(.bins)" in block
    assert ".tab-in .card > *" in block
    assert ".spanel-in > :not(.card)" in block
    assert ".spanel-in .card > *" in block
    assert "animation: contentIn var(--t-fast) var(--e-out) none" in block


def test_the_veil_is_gone():
    """The v0.47.24 wash: punched under pinned furniture, beige in the light
    theme, a rectangle of --bg over rounded cards."""
    assert "tabWash" not in CSS and "spanelWash" not in CSS
    assert ".tab-in::after" not in CSS
    assert "background: var(--bg); border-radius: inherit" not in CSS


def test_pinned_furniture_is_not_faded():
    """The transport and the save strip stay put — they are where the eye
    rests on a phone, and fading them was the shearing Argon caught."""
    assert "not(.transport)" in CSS


def test_no_retained_animation_fill():
    for bad in ("fill: both", "fill: forwards", "fill: backwards"):
        assert bad not in CSS


def test_the_switch_still_marks_the_arrival():
    assert 'markArrival(incoming, "tab-in")' in JS   # one-shot since v0.47.26
    assert "spanel-in" in JS
