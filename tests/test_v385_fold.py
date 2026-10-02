"""v0.38.5 — the fold.

Two reports on the expanded receipt card (phone screenshot, 2026-10-01):
1. "No animation when the card is expanding or retracting?" — the receipt
   swapped via display: none → grid, which cannot animate. It now folds
   through grid-template-rows 0fr → 1fr with an opacity crossfade
   (requires an inner wrapper with min-height: 0 — jdgrid).
2. "When expanding you don't need the /stor... near the open button" — the
   compact ellipsised path in the actions row is redundant once the
   receipt carries the full one; it yields when the card is open.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


# ---------- 1. the receipt folds, it does not swap ----------
def test_the_receipt_folds_through_grid_rows():
    assert "grid-template-rows: 0fr" in CSS, "collapsed: zero-height row"
    assert "grid-template-rows: 1fr" in CSS, "open: full-height row"
    assert ".jdetails { display: none; }" not in CSS, \
        "a display swap cannot animate"


def test_the_fold_is_a_transition_not_a_swap():
    i = CSS.find(".jdetails {")
    assert "transition" in CSS[i:i + 400]
    assert "opacity" in CSS[i:i + 400]


def test_the_inner_wrapper_makes_the_rows_shrinkable():
    # grid-template-rows: 0fr only collapses if the row's children can
    # shrink: overflow hidden + min-height 0 on the inner grid
    i = CSS.find(".jdgrid")
    assert i != -1
    assert "overflow: hidden" in CSS[i:i + 200]
    assert "min-height: 0" in CSS[i:i + 200]
    assert '"jdgrid"' in APP          # the receipt rows are built inside it


# ---------- 2. the compact path yields to the receipt ----------
def test_the_compact_path_yields_when_the_card_is_open():
    assert ".job.open .path { display: none; }" in CSS


# ---------- the fold respects the reduced-motion floor ----------
def test_reduced_motion_clamps_the_fold():
    assert "transition-duration: .001s !important" in CSS


# ---------- the v0.38.2 receipt contract stays intact ----------
def test_the_receipt_still_carries_size_and_location():
    assert '"jdpath"' in APP
    assert "humanBytes(j.size_bytes)" in APP
    assert ".job.open .jdetails" in CSS