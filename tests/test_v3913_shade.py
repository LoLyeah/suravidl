"""v0.39.13 "the shade" — the native shell sits on a wash; the toast lane
learns the desktop's furniture.

Two reports on the first real macOS glass (2026-10-03):

1. "Can you make the background more solid until the background barely
   visible?" The darwin page stepped fully aside for the native material
   since v0.38.4, so the desktop wallpaper read at full strength through
   every surface. The body now carries a near-opaque tint of the theme's
   room (--darwin-wash): the wallpaper reads as a hint behind the glass.
   Alpha stays >= .86 — the worst case (a white wallpaper spot under the
   dark theme) must keep body-vs-text contrast at 4.5:1.

2. "Why is the toast floating? Why isn't it adaptive like Android?" The
   desktop lane was two fixed lifts (86px everywhere, 150px on Settings),
   so a tall stack hovered mid-air. syncToastLane() had a desktop gate and
   skipped its measurement; the gate is gone — the lane clears the really
   docked furniture at every width and falls back to the corner.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text()
APP = (WEB / "app.js").read_text()


def test_the_darwin_page_carries_its_own_wash():
    """The page keeps its room tone; the material shows through as a hint."""
    assert ('html[data-host="darwin-glass"] body { background: '
            'var(--darwin-wash, transparent); }') in CSS
    washes = re.findall(r"--darwin-wash:\s*rgba\(([\d\s,.]+)\)", CSS)
    assert len(washes) == 3, "one wash per theme block"
    for w in washes:
        alpha = float(w.split(",")[3])
        assert alpha >= .86, f"wash {w} lets the wallpaper past the contrast floor"
        assert alpha <= .95, f"wash {w} hides the material entirely"


def test_the_toast_lane_measures_on_every_width():
    """No desktop gate: the same measurement runs in a 420px phone and a
    1600px desktop window; nothing docked means the CSS fallback."""
    fn = APP.split("function syncToastLane() {")[1].split("\n}")[0]
    assert "matchMedia" not in fn
    assert "899px" not in fn
    assert '".transport, #panel-settings .modal-foot"' in fn   # same furniture list
    assert "if (r.bottom < vh - 140) continue;" in fn            # docked-only
    assert ('host.style.bottom = top === Infinity ? "" : '
            'Math.round(vh - (top - 8)) + "px";') in fn


def test_the_lane_falls_back_to_the_corner_and_keeps_the_phone_rule():
    """Desktop fallback: the corner. Phones keep the tab-bar fallback. The
    old fixed lifts are gone for good."""
    assert "#toasts {\n  position: fixed; right: 16px; bottom: 24px; z-index: 60;" in CSS
    assert "bottom: 86px" not in CSS
    assert 'body[data-tab="settings"] #toasts' not in CSS
    assert "bottom: calc(var(--tabbar-h) + 12px + env(safe-area-inset-bottom));" in CSS
