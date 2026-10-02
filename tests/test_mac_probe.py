"""The macOS motion probe (scripts/mac_motion_probe.py).

Thread under review: the v0.38.7 desktop "no animation" report — WKWebView
pauses CSS transitions + rAF when it decides the view is not visible, and an
alpha-0 / transparent window (exactly the v0.38.4 macOS shell) is documented
to report itself occluded. The probe answers it on the user's MacBook Air
without shipping any fix: same window recipe as the app, a CSS transition +
rAF counter + 100 ms timer chain for ~3 s, and a verdict the user can paste
back. The occlusion SPI (_setWindowOcclusionDetectionEnabled:) is checked
but never called here — the probe diagnoses, it does not treat.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROBE = (ROOT / "scripts" / "mac_motion_probe.py").read_text()


def test_the_probe_mirrors_the_app_window():
    assert 'transparent=sys.platform == "darwin"' in PROBE


def test_the_probe_measures_the_three_freezable_things():
    # what WebKit pauses when it thinks the view is occluded
    assert "visibilityState" in PROBE
    assert "requestAnimationFrame" in PROBE
    assert "transition" in PROBE and "getComputedStyle" in PROBE
    # and the timers that get throttled instead of stopped
    assert "setTimeout" in PROBE


def test_the_probe_asks_about_the_occlusion_spi_but_never_calls_it():
    assert "_setWindowOcclusionDetectionEnabled:" in PROBE
    assert "respondsToSelector_" in PROBE
    # diagnose, don't treat: the probe must not flip the SPI itself
    assert "setWindowOcclusionDetectionEnabled_(" not in PROBE


def test_the_verdicts_are_computed_from_a_payload():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from mac_motion_probe import analyse

    hidden = {
        "visibility": "hidden", "lateVisibility": "hidden",
        "raf": [0, 16, 33],           # three ticks, then silence
        "timers": [0, 1000, 2000],    # ~1/s: the classic throttle
        "samples": [[0, "matrix(1, 0, 0, 1, 0, 0)"],
                    [1000, "matrix(1, 0, 0, 1, 0, 0)"],
                    [3000, "matrix(1, 0, 0, 1, 220, 0)"]],
        "occlusion": 0, "spiWk": True, "spiWin": False,
    }
    lines = "\n".join(analyse(hidden))
    assert "hidden" in lines
    assert "FROZEN" in lines

    alive = {
        "visibility": "visible", "lateVisibility": "visible",
        "raf": list(range(0, 3000, 16)),   # ~60fps
        "timers": list(range(0, 3000, 100)),
        "samples": [[0, "matrix(1, 0, 0, 1, 0, 0)"],
                    [700, "matrix(1, 0, 0, 1, 110, 0)"],
                    [1400, "matrix(1, 0, 0, 1, 220, 0)"]],
        "occlusion": 2, "spiWk": True, "spiWin": False,
    }
    lines = "\n".join(analyse(alive))
    assert "visible" in lines
    assert "animating" in lines.lower()
