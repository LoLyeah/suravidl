"""v0.45.10 "the ring" — the veil rides the card, the tour ring's own way.

The report (2026-10-06, Windows): the What's-new and FAQ cards "have
different blur and transparency" than the tour card although the recipes
match. Reproduced in Chrome over identical content: the veil was a LAYER
between room and card, so every popup blurred a darkened copy of the room
(flat grey), while the tour card floats over the room itself. The dim now
rides the card's own shadow — exactly the tour ring's mechanism
(0 0 0 100vmax) — and a shadow is not part of its own element's backdrop,
so the card blurs the REAL room again.
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


def test_one_veil_value_in_the_ring_and_the_card():
    """The whole point of the round: the same dim, the same mechanism."""
    veil = "0 0 0 100vmax rgba(5, 7, 10, .55)"
    assert veil in _block(".tour-ring {")
    assert veil in _block("\n.modal {")


def test_the_overlay_is_a_frostless_transparent_stage():
    blk = _block(".overlay {")
    assert "background: transparent;" in blk
    assert "backdrop-filter" not in blk


def test_the_drop_shadow_paints_above_the_veil():
    """The card's own depth shadow sits over the dim, like the ring's card."""
    blk = _block("\n.modal {")
    seg = blk[blk.index("box-shadow:"):blk.index("box-shadow:") + 220]
    assert seg.index("var(--shadow)") < seg.index("100vmax")


def test_every_dialog_is_a_modal_in_an_overlay():
    html = (ROOT / "src/suravidl_engine/web/index.html").read_text(encoding="utf-8")
    for dialog in ("confirmModal", "folderModal", "playModal", "whatsNewModal",
                   "logModal", "faqModal"):
        i = html.index(f'id="{dialog}"')
        seg = html[i:i + 300]
        assert 'class="overlay' in seg, dialog
        assert 'class="modal' in seg, dialog


def test_host_overrides_ride_the_card_too():
    light = _block('html[data-theme="light"] .modal {')
    assert "0 0 0 100vmax rgba(30, 29, 24, .30)" in light
    android = _block('html[data-host="android"] .modal {')
    assert "0 0 0 100vmax rgba(3, 5, 12, .72)" in android
