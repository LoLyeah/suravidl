"""v0.37.5 — the bar comes home.

The 2026-10-01 report: "there's no liquid glass effect aka the blur in the
'best available' card" (photo: the storage block's text crisp THROUGH the
bar) and "where's the animation for 'this download only' opening and
closing?".

The blur: the transport has carried the same glass tokens all along — but
since v0.37.1 it sits `position: fixed` on phones, and THIS WebView stops
compositing a backdrop pass for fixed layers over scrolling content (the
device photo's text behind the bar is crisp). The edge-energy "proof" of
2026-09-30 was taken through v0.37.1's near-opaque fill — it measured the
dim, not the blur. The geometry that DID blur on the device is in-flow:
v0.36's in-deck bar. So the phone bar rides sticky-in-flow again (which
also cannot overlap the footer by construction — the collision in the same
photo).

The animation: "This download only" was a bare <details> — it popped. Now
its body is a max-height+opacity door driven by the toggle event, stopped
instant by prefers-reduced-motion (which clamps the transition itself).
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text(encoding="utf-8")
JS = (ROOT / "src/suravidl_engine/web/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text(encoding="utf-8")


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


def _mobile_seg(text=CSS, want=".transport {"):
    """The stylesheet has several (max-width: 899px) blocks; return the one
    containing the wanted rule."""
    parts = text.split("@media (max-width: 899px)")
    for i in range(1, len(parts)):
        seg = parts[i].split("\n@media", 1)[0]
        if want in seg:
            return seg
    return parts[1].split("\n@media", 1)[0]


def test_the_phone_transport_rides_in_flow():
    """Fixed layers over scrolling content lose their backdrop pass on this
    WebView — the bar rides sticky in the deck's flow, like the bar that
    blurred on the device. In flow also cannot overlap the footer."""
    blk = _block(".transport {", _mobile_seg())
    assert "position: sticky" in blk
    assert "position: fixed" not in blk
    assert "--tabbar-h" in blk  # still parked above the tab bar


def test_the_transport_keeps_its_glass():
    """The material was never the bug; keep it pinned: real blur tokens on
    the bar, webkit prefix beside the property, @supports fallback intact."""
    base = _block(".transport {")
    assert "backdrop-filter: var(--glass-blur)" in base
    assert "-webkit-backdrop-filter: var(--glass-blur)" in base
    assert "@supports not ((backdrop-filter" in CSS


def test_the_bay_opens_with_a_door():
    """'This download only' grows and settles instead of popping: the body
    animates max-height + opacity from the details toggle event."""
    body_css = _block("#ovBlock .bay-body")
    assert "max-height" in body_css and "overflow: hidden" in body_css
    assert "transition" in body_css
    # the door is wired in JS: summary clicks are intercepted so <details>
    # never snaps its content — the wrapper transitions instead
    assert "wireBayDoor(" in JS
    assert "preventDefault()" in JS
    # the bay's content is wrapped so the door has something to close
    assert 'id="ovBody"' in HTML


def test_the_door_respects_reduced_motion():
    """The global reduced-motion clamp (.001s) makes the door instant —
    the rule exists; the door must not bypass it with its own animation."""
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    door = _block("#ovBlock .bay-body")
    assert "@keyframes" not in door


def test_transport_padding_is_not_a_fixed_overlay_anymore():
    """The 190px footer leg existed so the fixed bar could hover above the
    end of the page; in flow, the bar scrolls home — the leg shrinks."""
    leg = _block("footer.meta {", _mobile_seg())
    assert "190px" not in leg
