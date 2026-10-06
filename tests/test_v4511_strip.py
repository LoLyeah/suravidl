"""v0.45.11 "the strip" — every frost that silently didn't render, fixed.

Report (Windows, 2026-10-06): "no blur behind the save button". The strip
computed `blur(14px)` and rendered nothing: Chromium refuses a
backdrop-filter whose ancestry holds a backdrop root — an ancestor with
its own backdrop-filter (the settings card) AND, critically, an ancestor
whose opacity fade finishes but RETAINS (`animation-fill-mode: both`
keeps the element "animating" forever in the compositor). Every tab fade,
the dialog fade and the sub-panel fade were exactly that, so the Save
strip, the queue transport, the popup cards and the FAQ cards were all
flat in Chromium (WebKit differed — which is why Mac checks passed).
Verified with a stripe-tile variance rig: stripes behind the strip read
variance 9021 (crisp through) before, 1475 (blurred) after.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text(encoding="utf-8")


def _block(marker, text=CSS):
    i = text.index(marker)
    start = text.index("{", i)
    depth, j = 0, start
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces after " + marker)


def test_ancestor_fades_do_not_retain():
    """fill: none — a finished fade that keeps filling roots the subtree,
    and Chromium then refuses every backdrop-filter beneath it."""
    for rule in (".tab-in { animation: tabIn var(--t-fast) var(--e-out) none; }",
                 ".spanel-in { animation: spanelIn var(--t-fast) var(--e-out) none; }"):
        assert rule in CSS
    ov = _block(".overlay {")
    assert "fade var(--t-base) var(--e-out) none" in ov
    assert "backdrop-filter" not in ov          # still the frostless stage
    md = _block("\n.modal {")
    assert "modalIn var(--t-base) var(--e-out) none" in md


def test_no_retained_fill_on_the_ancestor_fades():
    assert "tabIn var(--t-fast) var(--e-out) both" not in CSS
    assert "spanelIn var(--t-fast) var(--e-out) both" not in CSS
    assert "fade var(--t-base) var(--e-out) both" not in CSS
    assert "modalIn var(--t-base) var(--e-out) both" not in CSS


def test_the_settings_card_yields_its_blur_to_the_strip():
    """Nested backdrop-filters are refused in Chromium: the card's own blur
    (decorative over the flat room) goes so the strip's can render."""
    blk = _block("#panel-settings .card {")
    assert "backdrop-filter: none" in blk
    strip = _block("#panel-settings .modal-foot {")
    assert "backdrop-filter: var(--glass-blur)" in strip
    assert CSS.index("#panel-settings .card {") > CSS.index("#panel-settings .modal-foot {")


def test_the_story_is_recorded_where_the_next_hand_touches_it():
    assert "fill: none on every ancestor fade" in CSS
    assert "backdrop root" in CSS
