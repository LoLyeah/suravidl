"""v0.45.3 "the summons" — the tour card becomes the popup standard.

Blessed on the Mac (2026-10-05): "this is the perfect blur and
transparency ratio... make it the standard for pop up." (Remembered: this
is the durable spec — DESIGN.md's Popup Standard + these pins.)

The cards already shared one recipe; the veil was the difference — since
v0.37.4 it stacked its own frost over the card's and smeared the room
flat. The veil now dims like the tour ring (rgba(5,7,10,.55), no frost):
the room stays sharp-dimmed, the popup card is the room's only frost,
and all six .overlay dialogs inherit the tour card's material untouched.

v0.45.10 "the ring" then moved the dim itself onto the card's own shadow
(the ring's mechanism exactly), so the card blurs the REAL room instead
of the darkened layer between — the veil as a layer made every popup read
a shade darker than the tour card (2026-10-06 Windows report).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text(encoding="utf-8")
MD = (ROOT / "DESIGN.md").read_text(encoding="utf-8")


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


MATERIAL = [
    "var(--glass-bg-strong)",
    "1px solid var(--glass-border)",
    "backdrop-filter: var(--glass-blur);",
    "-webkit-backdrop-filter: var(--glass-blur);",
    "background-image: var(--glass-gloss);",
    "box-shadow: var(--shadow), inset 0 1px 0 var(--glass-hi)",
]


def test_the_veil_dims_like_the_ring_without_frosting():
    """v0.45.10: the veil rides the card's own shadow — the ring's exact
    mechanism — so the card blurs the real room, not a darkened copy."""
    blk = _block(".overlay {")
    assert "background: transparent;" in blk
    assert "backdrop-filter" not in blk
    veil = "0 0 0 100vmax rgba(5, 7, 10, .55)"
    assert veil in _block("\n.modal {")   # the card carries the dim now
    assert veil in _block(".tour-ring {")  # one value, one mechanism


def test_the_popup_cards_share_one_recipe():
    """The tour card and every dialog card carry the same six lines — the
    blessed blur + transparency ratio. Drift in either is a failed standard."""
    for marker in ("\n.modal {", "\n.tour-card {"):   # line-start: the @supports
        blk = _block(marker)                            # fallback list names them too
        for part in MATERIAL:
            assert part in blk, f"{marker} lost '{part}'"


def test_design_md_recorded_the_standard():
    assert "The Popup Standard." in MD
    assert "rgba(5,7,10,.55)" in MD
