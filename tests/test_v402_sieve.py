"""v0.40.2 "the sieve" — the queue grows a view filter: All / Active / Filed /
Errors, a counted line when a view hides everything, and a way back.

RED first: the chips do not exist on 0.40.1.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text()
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text()
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text()


def _seg(source, start, end="\nfunction "):
    body = source.split(start)[1]
    return body.split(end, 1)[0]


def test_the_queue_gains_a_filter_row():
    assert 'id="queueFilters"' in HTML
    for f in ("all", "active", "filed", "error"):
        assert f'data-qfilter="{f}"' in HTML, f
    # "All" is the default view
    assert 'class="btn sm pick" data-qfilter="all" aria-pressed="true"' in HTML
    # the counted line owns a way back
    assert 'id="filterEmpty"' in HTML and 'id="filterAll"' in HTML


def test_the_buckets_keep_filed_and_failed_apart():
    const = _seg(APP, "const QUEUE_BUCKETS = {", end="\nlet QFILTER")
    assert "filed" in const and '"completed"' in const
    assert "error" in const and '"interrupted"' in const
    seg = _seg(APP, "function queueBucket(")
    assert 'return "filed"' in seg and 'return "error"' in seg
    assert 'return "active"' in seg, \
        "anything not filed and not failed is still in play"


def test_the_sieve_hides_rows_and_counts_what_it_hid():
    assert 'let QFILTER = "all";' in APP
    seg = _seg(APP, "function applyQueueFilter(")
    assert 'classList.toggle("hidden"' in seg, "rows hide, they do not leave"
    assert "filterEmpty" in seg
    assert "hidden by this filter" in seg, \
        "a filtered view must never read as an empty queue"
    assert '"1 job hidden' in seg, "the count speaks English at one"


def test_rows_carry_their_status_for_the_sieve():
    assert APP.count("row.dataset.status = j.status") == 2, \
        "both the new-row and the in-place path stamp the status"


def test_every_poll_and_every_click_reapplies_the_sieve():
    ref = _seg(APP, "async function refreshJobs(", end="\nasync function ")
    assert "applyQueueFilter()" in ref, "a poll repaint must keep the view"
    assert '$("queueFilters")' in ref, "the chips follow the queue's emptiness"
    wire = _seg(APP, "function wireQueueFilters(")
    assert "QFILTER = btn.dataset.qfilter" in wire
    assert 'setAttribute("aria-pressed"' in wire
    assert "wireQueueFilters();" in APP, "and the boot wires it"


def test_the_sieve_has_a_style():
    assert "#queueFilters" in CSS
    assert "#filterEmpty" in CSS
