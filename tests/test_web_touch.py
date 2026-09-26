"""The app must feel like an app on a phone, not like a web page in a frame.

Reported from Android: "there's always ugly blue square opacity" when tapping
any button, and every label could be selected and copied. Both were WebView
defaults we had never overridden:

- the tap highlight: a translucent plate the WebView paints over the tapped
  element, ignoring border-radius and our colours;
- text selection, which raises the selection handles and the Copy menu on
  long-press anywhere;
- and, behind the "always" part: `:hover` styles LATCH on a touch screen, so
  the last-tapped button kept its lighter, blue-tinted hover background until
  the next tap.

Hover is now for real pointers only, presses get their own feedback, and
chrome text stops being a document.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text()


def test_the_webview_tap_highlight_is_switched_off():
    assert "-webkit-tap-highlight-color: transparent" in CSS


def test_chrome_text_is_not_a_document_but_fields_are():
    assert "user-select: none" in CSS
    body = [ln for ln in CSS.splitlines() if ln.startswith("body {") and "user-select" in ln]
    assert body, "body must switch selection off"
    fields = CSS.split('input, textarea, select, [contenteditable="true"]', 1)[1][:200]
    assert "user-select: text" in fields, "fields you type in stay selectable"
    assert ".selectable" in fields, "and anything else worth copying can opt back in"


def test_hover_never_latches_on_a_touch_screen():
    """The stuck blue tint: every :hover rule must be pointer-only."""
    for line in CSS.splitlines():
        if ":hover" in line:
            assert line.strip().startswith("@media (hover: hover)"), \
                f"a hover rule can latch on touch: {line.strip()[:70]}"
    assert CSS.count("@media (hover: hover)") >= 10


def test_a_tap_still_gets_feedback_everywhere_tappable():
    active = CSS.split(".btn:active", 1)[1].split("}", 1)[0]
    for sel in (".get:active", ".ghost-sm:active", ".swatch:active",
                ".tab:active", ".stab:active"):
        assert sel in active, f"{sel} has no press state"
    assert ".optrow:active" in CSS
