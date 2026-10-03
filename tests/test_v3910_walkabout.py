"""v0.39.10: the walkabout — the dressing waits for the webview to exist.

The mac motion probe's second run caught the v0.39.9 miss: pywebview only
parents the WKWebView into the window when the FIRST navigation finishes
(`webView_didFinishNavigation_` -> `setContentView_`), so the start
callback walked an empty hierarchy — the calm never engaged and the native
glass never inserted, on every macOS run. The walk also gave up at
contentView instead of climbing the superview chain.

Now: the calm + the material dress on the `loaded` event (and once at
start, idempotently), the walk climbs, and the probe reports the view
classes it saw so a miss is diagnosable from one paste.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()
PROBE = (ROOT / "scripts" / "mac_motion_probe.py").read_text()
WHATSNEW = (ROOT / "src" / "suravidl_engine" / "whatsnew.py").read_text()


def test_the_dressing_runs_when_the_page_is_loaded():
    # pywebview parents the webview at didFinishNavigation — dressing must
    # wait for that, not for the GUI loop
    assert "events.loaded" in MAIN
    assert "def _dress(" in MAIN
    assert MAIN.index("events.loaded") < MAIN.index("_start_motion_probe")


def test_the_material_is_idempotent():
    # loaded fires per navigation; dressing twice must not stack materials
    assert "_find_material" in MAIN


def test_the_walk_climbs_the_superview_chain():
    assert "superview()" in MAIN.split("def _calm_page_visibility")[0]


def test_the_probe_walks_late_and_reports_what_it_saw():
    assert "retry" in PROBE.lower()
    assert '"views"' in PROBE
    assert "superview()" in PROBE


def test_the_walkabout_entry_retired_cleanly():
    # The walkabout shipped with 0.39.10 and was announced in its card.
    # The rolling card keeps ten entries and retires the oldest — v0.40.6
    # retired this one, so the announcement lives in git and the release
    # notes now, and this pin retires WITH the entry (policy: a feature
    # stays pinned by its living tests — this file's dressing pins;
    # verbatim-entry pins age out with the list). All this test still
    # guards is that the retirement left no half behind.
    assert '"version": "0.39.10"' not in WHATSNEW
    assert "The walkabout" not in WHATSNEW