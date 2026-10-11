"""v0.46.5 "the desk" — Download's three jobs, named.

The discoverability fix: batch and follow were guests in one long
column, invisible unless you knew. Now Link (default) · Batch · Watch
list are named sub-tabs of the Download desk; a multi-link paste in
Link carries into Batch instead of being eaten by the probe; the Watch
list label carries a quiet count. Same UI core, so Android inherits it.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(
    encoding="utf-8")

NLBRACE = "\n}"


def test_the_desk_names_its_three_jobs():
    assert 'id="subNav"' in HTML
    for btn in ("subLinkBtn", "subBatchBtn", "subFollowsBtn"):
        assert f'id="{btn}"' in HTML, btn
    assert HTML.count('class="subbtn') == 3
    for sub in ('data-sub="link"', 'data-sub="batch"', 'data-sub="follows"'):
        assert sub in HTML, sub


def test_link_is_the_default_and_the_others_start_hidden():
    assert 'class="subbtn on" id="subLinkBtn"' in HTML
    assert 'class="subpanel" id="subLink"' in HTML
    assert 'class="subpanel hidden" id="subBatch"' in HTML
    assert 'class="subpanel hidden" id="subFollows"' in HTML


def test_batch_owns_its_own_box_and_rooms_are_whole():
    # the textarea exists, and batchRow/batchList live INSIDE subBatch
    assert 'id="batchUrls"' in HTML and "<textarea" in HTML
    i_sub = HTML.index('id="subBatch"')
    i_row = HTML.index('id="batchRow"')
    i_list = HTML.index('id="batchList"')
    i_follows = HTML.index('id="subFollows"')
    assert i_sub < i_row < i_list < i_follows, "batch gear must sit in subBatch"
    assert 'id="followsCard"' in HTML
    assert HTML.index('id="subFollows"') < HTML.index('id="followsCard"')
    # the paste card no longer carries any batch gear
    paste = HTML[HTML.index('class="card paste-card"'):HTML.index('id="subBatch"')]
    assert 'id="batchRow"' not in paste and 'id="batchList"' not in paste


def test_a_multi_link_paste_carries_instead_of_being_eaten():
    assert 'id="multiHint"' in HTML and 'id="multiGoBatch"' in HTML
    assert "function renderMultiHint()" in APP
    # the carry: value moves to the batch box, Link empties, Batch opens
    seg = APP[APP.index('$("multiGoBatch").onclick'):]
    seg = seg[:seg.index("};")]
    assert '$("batchUrls").value = carry' in seg
    assert 'showSub("batch")' in seg
    # a batch row tapped goes the single-link way IN the Link room
    seg2 = APP[APP.index("function bulkRow("):]
    seg2 = seg2[:seg2.index("function probeInto")]
    assert 'showSub("link")' in seg2


def test_the_batch_row_never_paints_at_load():
    """renderBatchRow reads BULK, whose `let` runs later in the file: an
    eager call at init dies in TDZ and takes the whole script — and the
    sub-nav — down with it. The row paints on input and on room open."""
    i = APP.index("function initBatch(")
    seg = APP[i:APP.index("let BULK", i)]
    assert "renderMultiHint();" in seg, "the hint may compute at init (no BULK)"
    # the eager pair was the exact bug shape; renderBatchRow may still appear
    # inside the onclick handlers (they run after load, never at init)
    assert "renderMultiHint();\n  renderBatchRow();" not in seg, \
        "the batch row must never paint at load — BULK is TDZ until its section"
    # and the room-open paint exists where it belongs
    sub = APP[APP.index("function showSub("):]
    sub = sub[:sub.index(NLBRACE)]
    assert 'if (SUBTAB === "batch") renderBatchRow();' in sub


def test_the_batch_machinery_reads_the_batch_box():
    seg = APP[APP.index("function pastedTokens()"):]
    seg = seg[:seg.index(NLBRACE)]
    assert "batchUrls" in seg, "the paste source must be the batch box"
    assert '$("url").value' not in seg
    # the check-preview invalidation rides the same box
    assert 'batchUrls").addEventListener("input", clearBulkPreview)' in APP
    assert "showSub(b.dataset.sub)" in APP


def test_show_sub_toggles_panels_buttons_and_aria():
    seg = APP[APP.index("function showSub("):]
    seg = seg[:seg.index(NLBRACE)]
    assert '["link", "batch", "follows"]' in seg
    assert 'classList.toggle("hidden", !on)' in seg
    assert "aria-selected" in seg
    assert "renderFollows()" in seg and "renderBatchRow()" in seg


def test_the_watch_list_label_carries_a_quiet_count():
    seg = APP[APP.index("function renderFollows("):]
    seg = seg[:seg.index(NLBRACE)]
    assert "subFollowCount" in seg
    assert "FOLLOWS.length ? String(FOLLOWS.length)" in seg


def test_the_subnav_is_thumb_viable():
    assert ".subnav" in CSS and ".subbtn" in CSS
    assert "@media (pointer: coarse) { .subbtn { min-height: 44px; } }" in CSS
    assert "flex: 1 1 0" in CSS, "segments share the width on phones"
    assert "@media (hover: hover) { .subbtn:hover" in CSS, \
        "hover must be guarded for touch"


def test_the_desk_speaks_indonesian_too():
    for pair in ('"Link": "Tautan"', '"Open Batch": "Buka Batch"',
                 '"Download modes": "Mode unduhan"'):
        assert pair in APP, pair
