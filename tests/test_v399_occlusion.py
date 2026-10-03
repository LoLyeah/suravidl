"""v0.39.9: the calm — the desktop shell stops flinching at its own window.

The mac motion probe answered (2026-10-02, the user's MacBook Air):
`document.visibilityState === 'hidden'` inside the app's own window while
the OS says the window is VISIBLE and rAF still ticks 60/s — the WebKit
freeze shape (CSS transitions are skipped in hidden documents; the element
jumped straight to its end state, "STUCK — transform never left 220").
The field-proven cure (liquidx/webviewscreensaver, the Sonoma screensaver
fix) is the WKWebView SPI `_setWindowOcclusionDetectionEnabled: NO`.

The probe also caught two of our own bugs on the way:
- pywebview wraps WKWebView in a `WebKitHost` SUBCLASS, so the app's
  name-based walk (`type(view).__name__ == "WKWebView"`) never matched —
  the v0.38.4 native glass insertion has been a silent no-op on macOS.
- the probe itself had the same walk, and added the transition class
  before the element's first style flush (the skip-transition race).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()
PROBE = (ROOT / "scripts" / "mac_motion_probe.py").read_text()
WHATSNEW = (ROOT / "src" / "suravidl_engine" / "whatsnew.py").read_text()


def test_the_shell_finds_the_wrapped_webview():
    """The walk matches the class AND its pywebview subclass."""
    assert "lookUpClass(\"WKWebView\")" in MAIN
    assert "isKindOfClass_" in MAIN


def test_the_shell_flips_the_occlusion_spi_gated_and_fail_soft():
    # the SPI the screensaver fix proved out
    assert '"_setWindowOcclusionDetectionEnabled:"' in MAIN
    # PyObjC hides underscore selectors: the call goes through objc_msgSend
    assert "objc_msgSend" in MAIN and "pyobjc_id" in MAIN
    assert "sel_registerName" in MAIN
    # gated, darwin-only, and a throw may never take the window down
    assert "respondsToSelector_" in MAIN
    assert "def _calm_page_visibility(" in MAIN
    assert 'sys.platform != "darwin"' in MAIN


def test_the_calm_runs_in_the_start_callback():
    assert "_calm_page_visibility(window)" in MAIN


def test_the_shell_never_touches_the_deprecated_transparency_path():
    # the deprecation warning the user's run surfaced is pywebview's
    # setValue_forKey_('drawsTransparentBackground') — we never add more
    assert "_setDrawsTransparentBackground" not in MAIN


def test_the_probe_walks_the_same_way_and_races_no_more():
    assert "lookUpClass(\"WKWebView\")" in PROBE
    assert "isKindOfClass_" in PROBE
    # the first sample lands before the class is added, and the class is
    # added inside the first rAF (after a style flush), not at parse time
    assert "P.samples.push([0" in PROBE
    assert "classList.add('go')" in PROBE
    assert PROBE.index("requestAnimationFrame(function first()") < PROBE.index(
        "classList.add('go')")


def test_the_verdict_names_the_two_hidden_shapes():
    assert "hidden at load only" in PROBE
    assert "persistently hidden" in PROBE


def test_the_calm_entry_retired_cleanly():
    # The calm shipped with 0.39.9 and was announced in its card. The
    # rolling card keeps ten entries and retires the oldest — v0.40.5
    # retired this one, so the announcement lives in git and the release
    # notes now, and this pin retires WITH the entry (policy: a feature
    # stays pinned by its living tests — the occlusion probes in this
    # file; verbatim-entry pins age out with the list). All this test
    # still guards is that the retirement left no half behind.
    assert '"version": "0.39.9"' not in WHATSNEW
    assert "The calm" not in WHATSNEW