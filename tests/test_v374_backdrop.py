"""v0.37.4 — the backdrop pass: one definition of the dialog overlay's frost.

The popup report ("What's new pop up doesn't have blur") took v0.37.3's fix
to the phone; the desktop veil stayed a flat dim. The frost moved to the
base .overlay rule — every host — and DESIGN.md carries the full material
spec so the next glass dispute has one authoritative sheet to point at.

Superseded by v0.45.3: the veil mattes to the tour ring's dim — no frost of
its own; the popup card is the room's only frost (the Popup Standard).
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


def test_the_veil_dims_without_frosting():
    """v0.45.3: the veil dims like the tour ring and carries no frost;
    the card is the only frost in the room."""
    blk = _block(".overlay {")
    assert "background: rgba(5,7,10,.55);" in blk
    assert "backdrop-filter" not in blk


def test_design_md_carries_the_material_spec():
    """DESIGN.md is the sheet the glass disputes point at: both finishes,
    both host radii, the overlay frost and the verification rule."""
    assert "blur(26px) saturate(165%) brightness(1.04)" in MD
    assert "blur(19px) saturate(165%)" in MD
    assert "blur(11px) saturate(120%)" in MD
    assert "rgba(5,7,10,.55)" in MD
    assert "The Measured-Blur Rule." in MD
