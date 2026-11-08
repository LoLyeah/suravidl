"""v0.49.9 "the formality" — no download of a link the app has not read.

The owner pressed "Download now" on a link nothing had probed: the app made the
job, the engine refused it ("no extractor knows this page"), and the toast
offered a Retry that could only fail again. A URL says nothing about whether it
can be downloaded, so the start controls now wait for a probe of THAT link.

Also fixed: a successful probe never cleared PROBE_FAILED_URL — re-probing the
same link kept the gate armed even though it read fine.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.49.9"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the formality"
    assert len(ENTRIES) == 10


def test_the_permission_is_the_read():
    assert "let PROBE_OK_URL" in APP
    assert "PROBE_OK_URL = url;" in APP
    assert "const unread = !empty && !refused && PROBE_OK_URL !== url;" in APP
    assert "const dead = empty || refused || unread;" in APP


def test_a_successful_probe_lifts_an_old_refusal():
    block = APP[APP.index("function renderProbe(url, info) {"):]
    block = block[:block.index("\n}", block.index("syncStartState();"))]
    assert 'PROBE_FAILED_URL = "";' in block
    assert "PROBE_OK_URL = url;" in block
    assert "syncStartState();" in block


def test_both_start_doors_refuse_with_words():
    for fn in ("async function quickStart()", "async function commitTake(btn)"):
        block = APP[APP.index(fn):]
        block = block[:block.index("\n}", block.index("return"))]
        assert "PROBE_OK_URL !== url" in block, fn
        assert "Probe first — the app has to read the link before it can download it" in block, fn


def test_a_browser_only_failure_offers_no_retry():
    block = APP[APP.index("function onFailed(j) {"):]
    block = block[:block.index("toast(t(\"Couldn't download")]
    assert "const dead = browserOnlySay(why);" in block
    assert "Open in the browser" in block
    # the retry lives in the else branch
    assert block.index("} else {") < block.index('label: t("Retry")')


def test_the_line_is_translated():
    assert '"Probe first — the app has to read the link before it can download it": "Cek dulu' in APP
