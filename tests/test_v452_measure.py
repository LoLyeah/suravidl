"""v0.45.2 "the measure" — the deck stops changing size; the Save strip
frosts what scrolls beneath it.

Two reports on the released desktop (2026-10-05):

1. "Regression, the setting cards length always changing for some reason."
   The deck (main) carried `margin: 0 auto` for centering, but the shell is
   a flex column — and in the flex cross axis, auto margins make the item
   FIT-CONTENT. So the deck was sized by the visible panel's content: every
   sub-tab (and every tab) resized it. The fix pins `width: 100%` beside
   every centered `main` rule; the invariant below keeps it pinned.

2. "Give more blurred background behind the save button." Rows scroll
   beneath the sticky Save strip; on desktop the strip now frosts them
   with the material blur. Phones keep their flat strip (composite cost
   over the tab bar) and Android keeps its no-blur concession.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text()


def test_the_deck_never_shrink_wraps():
    """A centered deck (margin: 0 auto) must pin its width — in a flex
    column, auto margins alone size it to the visible panel's content."""
    found = 0
    for m in re.finditer(r"main \{([^}]*)\}", CSS):
        body = m.group(1)
        if "margin: 0 auto" in body:
            found += 1
            assert "width: 100%" in body, \
                f"a centered main rule lost its width pin: {body.strip()[:120]}"
    assert found >= 2, "both the 900px and 1080px decks carry the centering"
    assert "main { width: 100%; max-width: 1240px; margin: 0 auto; }" in CSS


def test_the_save_strip_frosts_on_desktop():
    foot = CSS.split("#panel-settings .modal-foot {")[1].split("}")[0]
    assert "backdrop-filter: var(--glass-blur);" in foot
    assert "-webkit-backdrop-filter: var(--glass-blur);" in foot
    assert "border-bottom-left-radius: 20px" in foot, "corners stay round"


def test_phones_and_android_keep_the_flat_strip():
    chunks = CSS.split("#panel-settings .modal-foot {")
    assert len(chunks) >= 3, "base + phone + android rules all exist"
    phone = chunks[2].split("}")[0]   # the max-width:899 block
    assert "backdrop-filter: none" in phone and "-webkit-backdrop-filter: none" in phone
    android = chunks[3].split("}")[0]
    assert "backdrop-filter: none" in android
    assert "background: var(--panel-solid);" in android
