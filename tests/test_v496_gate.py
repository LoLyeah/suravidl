"""v0.49.6 "the gate" — no start control for a link the probe refused.

The owner pasted a page with no extractor, the probe said so, and both
"Download now" and START stayed live: two buttons that would only fail.

The gate is narrow on purpose — it fires only when the engine calls the link
UNSUPPORTED (the browser-and-Scan route is the answer). A 403 or a TLS failure
is "could not read it now"; a retry with cookies or another network is still
legitimate, so those stay live. Editing the box clears the refusal.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.49.6"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the gate"
    assert len(ENTRIES) == 10


def test_a_refused_link_arms_the_gate():
    assert "let PROBE_FAILED_URL" in APP
    assert "PROBE_FAILED_URL = unsupported ? url : \"\";" in APP
    assert 'const unsupported = d.unsupported === true || /unsupported url/i.test(msg || "");' in APP


def test_both_start_controls_die_together():
    fn = APP[APP.index("function syncStartState()"):]
    fn = fn[:fn.index("\n}")]
    assert '$("bestBtn").disabled = dead;' in fn
    assert '$("quickBtn").disabled = dead;' in fn
    assert 'for (const id of ["quickBtn", "bestBtn"])' in fn


def test_no_path_queues_a_refused_link():
    assert 'if (url === PROBE_FAILED_URL) {' in APP


def test_editing_the_box_clears_the_gate():
    assert 'PROBE_FAILED_URL = "";       // a new link is an unknown link' in APP
