"""v0.39.3: the filed-takes rail keeps its contents inside itself.

Reported live (2026-10-02, Windows): the rail's meta line showed a whole
Windows path — split("/") finds no separator in "C:\\Users\\Han\\...", so the
basename came back whole — and nothing clipped it: the line slid out of the
236px rail, under the queue card, and bled through the glass right into the
card's title row. Two fixes pinned here: every basename goes through one
separator-aware helper, and the rail's boxes clip.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src" / "suravidl_engine" / "web"
JS = (WEB / "app.js").read_text()
CSS = (WEB / "style.css").read_text()


def test_the_rail_never_paints_outside_itself():
    """An escaping line must be clipped at the rail, not painted under the
    next panel (the glass made it visible as a ghost in the card title)."""
    bin_block = CSS.split(".bin {")[1].split("}")[0]
    assert "overflow: hidden" in bin_block, "the rail item clips what it carries"
    meta_block = CSS.split(".bin-meta")[1].split("}")[0]
    assert "overflow: hidden" in meta_block, "the meta line is clipped"
    assert "text-overflow: ellipsis" in meta_block, "…and says so with an ellipsis"
    assert "white-space: nowrap" in meta_block


def test_basenames_survive_windows_paths():
    """One helper, separator-aware; no call site keeps the old split('/')."""
    assert "function baseName(" in JS
    assert "split(/[" + "\\\\" + "/]/)" in JS, "the helper splits both separators"
    assert 'split("/").pop()' not in JS, "no site may keep the slash-only split"
