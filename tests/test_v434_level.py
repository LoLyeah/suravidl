"""v0.43.4 "the level" — the toast lane sits at a true offset.

syncToastLane measures the lane's bottom edge: 8px above whatever is
really docked (the transport, the settings Save strip) or the phone's
tab-bar fallback. v0.41.1 accidentally composed that measured offset ON
TOP of the base, so every lifted toast floated a whole base too high —
mid-panel, over the very Updates row it was reporting to. The pins: the
stylesheet takes the offset via max(), never a sum; the JS keeps
speaking in bottom offsets.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text()
APP = (WEB / "app.js").read_text()


def test_the_offset_wins_over_the_base_instead_of_stacking():
    assert "bottom: max(24px, var(--toast-lift, 0px));" in CSS
    assert ("bottom: max(calc(var(--tabbar-h) + 12px + env(safe-area-inset-bottom)), "
            "var(--toast-lift, 0px));" in CSS)
    # the additive shapes are gone for good — the whole regression in one line
    assert "+ var(--toast-lift" not in CSS


def test_the_measurement_still_speaks_in_bottom_offsets():
    """The fix lives in the stylesheet's composition; the JS contract stays
    'bottom edge, 8px above the furniture' (the formula years of behavior
    was built on)."""
    fn = APP.split("function syncToastLane() {")[1].split("\n}")[0]
    assert 'host.style.setProperty("--toast-lift", ' in fn
    assert 'Math.round(vh - (top - 8)) + "px")' in fn
    assert 'host.style.removeProperty("--toast-lift")' in fn


def test_the_fallback_stays_when_nothing_is_docked():
    # var unset -> max(base, 0px) = base: just above the tab bar (phone)
    # and the 24px corner (desktop) — the v0.38.2 behavior, untouched
    assert "var(--toast-lift, 0px)" in CSS
