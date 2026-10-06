"""v0.37.7 — the readable queue.

Two device reports off the 2026-10-01 evening photos:

1. "When there's a queue, the number pushes the queue button" — the phone
   tab is a centered COLUMN (icon / label / badge); the badge is a flow
   child, so when the count appears the column grows and the centering
   shifts the tab's icon+label UP against its siblings (the photo shows
   the numbered Queue tab sitting visibly higher than Download/Settings).
   The badge must leave the flow: absolute, on the icon's corner, inert.
2. "Can you expand the card when you click on the queue card, so I can
   read at least the full title?" — a phone title ellipsises
   ("Japanese Wagyu...") and there is no hover to reveal it; a tap must
   unfold the whole title.
"""
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")


def _block(sel, text):
    i = text.index(sel)
    return text[i:text.index("}", i) + 1]


def _mobile_blocks():
    blocks, i = [], 0
    while True:
        i = CSS.find("@media (max-width: 899px)", i)
        if i == -1:
            return blocks
        end = CSS.find("\n}", i)
        blocks.append(CSS[i:end])
        i = end


def _phone_block(*wants):
    for seg in _mobile_blocks():
        if all(w in seg for w in wants):
            return seg
    raise AssertionError(f"no 899px block contains {wants}")


def test_the_queue_count_rides_the_icon_corner_out_of_flow():
    seg = _phone_block(".badge {")
    blk = _block(".badge {", seg)
    assert "position: absolute" in blk, blk
    assert "pointer-events: none" in blk, blk
    tab = _block(".tab {", seg)
    assert "position: relative" in tab, tab


def test_a_tap_unfolds_the_whole_title():
    base = _block(".jobtitle {", CSS)
    assert "cursor: pointer" in base, base
    open_blk = _block(".jobtitle.open {", CSS)
    assert "white-space: normal" in open_blk, open_blk
    assert "overflow: visible" in open_blk, open_blk
    # the open title needs the row's FULL width: beside the pills its box can
    # collapse to ~30px and the text wrapped one letter per line (verified
    # live in the 393px harness) — basis 100% + a wrapping row fix that
    assert "flex: 1 0 100%" in open_blk, open_blk
    assert ".job.open .jobtop { flex-wrap: wrap; }" in CSS
    # the handler lives in jobRow and toggles the class — on the row since
    # v0.45.8 (the whole card flips it; buttons stay buttons)
    assert "row.onclick" in JS
    assert 'title.classList.toggle("open")' in JS
