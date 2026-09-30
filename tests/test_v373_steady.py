"""v0.37.3 — the steady pass: three reports off the phone screenshots.

1. "the start best is stuck after tab switching" — the tab arrival animated
   `transform: translateY(4px)`, so the panel became a containing block for
   its `position: fixed` transport: after every switch the bar re-anchored
   to the panel and hung over the content (reproduced live: content-relative
   y 405 that moved with scroll, vs 699 pinned to the viewport).
2. "What's new pop up doesn't have blur" — the full-screen overlay was a
   flat veil; the popup's backdrop frosts now (v0.37.4 moved it to the
   base rule, every host).
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


def test_the_overlay_frosts_the_backdrop():
    """The popup report ("doesn't have blur") ends here: the veil carries a
    real backdrop pass — one definition on the base rule (v0.37.4); the
    android-era override is gone."""
    blk = _block(".overlay {")
    assert "backdrop-filter: blur(" in blk
    assert "-webkit-backdrop-filter: blur(" in blk
    assert 'html[data-host="android"] .overlay {' not in CSS


def test_the_chosen_tab_wears_a_squircle_outline():
    """One line is gone: the active tab is a rounded outline. Pinned by the
    exact cell (three 899px blocks exist — region splits caught the wrong
    one, harness lesson)."""
    cell = """  .tab {
    flex: 1; flex-direction: column; gap: 2px;
    padding: 5px 4px;
    border: 1px solid transparent; border-radius: 15px;
    min-height: 44px; justify-content: center;
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
    seg = CSS.split(".transport {\n    position: fixed", 1)[1].split("}")[0]
    assert "gap: 10px;" in seg
