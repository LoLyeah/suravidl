"""v0.37.3 — the steady pass: three reports off the phone screenshots.

1. "the start best is stuck after tab switching" — the tab arrival animated
   `transform: translateY(4px)`, so the panel became a containing block for
   its `position: fixed` transport: after every switch the bar re-anchored
   to the panel and hung over the content (reproduced live: content-relative
   y 405 that moved with scroll, vs 699 pinned to the viewport).
2. "What's new pop up doesn't have blur" — the full-screen overlay was a
   flat veil; v0.37.4–v0.45.2 frosted the veil itself. v0.45.3 supersedes:
   the veil dims only (the tour ring's look); the popup card is the room's
   only frost. v0.45.10: the dim rides the card's own shadow — the ring's
   mechanism — and the card blurs the real room.
3. "the chosen Bottom bar tab needs a squircle outline instead of just one
   line" — the 2px top hairline became a rounded outline.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def _block(marker, text=CSS):
    """The text from `marker` through its matching closing brace."""
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


def test_the_tab_arrival_never_transforms_the_panel():
    """A transform on the panel makes it a containing block for fixed
    children — the transport re-anchored to the page and got stuck."""
    into = _block("@keyframes tabIn")
    assert "opacity" in into
    assert "transform" not in into
    assert "translateY" not in into


def test_the_veil_dims_and_leaves_the_frost_to_the_card():
    """v0.45.3 (the Popup Standard) with v0.45.10's mechanism: the veil
    rides the card's own shadow, no frost anywhere on it. The android host
    re-values the veil's COLOR only (its dense veil), nothing else."""
    blk = _block(".overlay {")
    assert "background: transparent;" in blk
    assert "backdrop-filter" not in blk
    veil = _block('html[data-host="android"] .modal {')
    assert "0 0 0 100vmax rgba(3, 5, 12, .72)" in veil


def test_the_chosen_tab_wears_a_squircle_outline():
    """One line is gone: the active tab is a rounded outline. Pinned by the
    exact cell (three 899px blocks exist — region splits caught the wrong
    one, harness lesson)."""
    cell = """  .tab {
    flex: 1; flex-direction: column; gap: 2px;
    padding: 5px 4px;
    border: 1px solid transparent; border-radius: 15px;
    min-height: 44px; justify-content: center; position: relative;
    transition: color var(--t-fast) ease, background var(--t-fast) ease,
                border-color var(--t-fast) ease;
  }"""
    assert cell in CSS, "the phone tab is not the squircle cell"
    assert ".tab.active { border-color: var(--accent-line); background: var(--glass-bg); }" in CSS
    assert "border-top-color: var(--accent);" not in CSS, "the hairline is back"


def test_the_take_readout_keeps_its_room_on_a_phone():
    """"best available" survives a 393px row: the reading gives up a little
    size (12px) and the transport a little gap (10px)."""
    assert ".transport .take .reading { font-size: 12px; }" in CSS
    seg = CSS.split(".transport {\n    /* sticky in the deck's flow", 1)[1].split("}")[0]
    assert "gap: 10px;" in seg
