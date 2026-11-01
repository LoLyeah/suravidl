"""v0.47.26 "the once" — the arrival is a one-shot, not a standing rule.

v0.47.25 moved the tab fade onto the panel's contents, but `.tab-in` stayed on
the panel for ever. The queue rebuilds its chips and action buttons on a
1.2 s poll, so every rebuilt button started `contentIn` again from opacity 0
and the controls blinked for as long as the tab was open.

Measured in the running app (5 s of MutationObserver on #panel-queue):
  DIV.qstate 80 · BUTTON.btn sm 50 · BUTTON.btn sm pick 10
— the buttons are re-created, not merely updated. Hence: the class must live
only for the arrival.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["title"].lower() == "the once" for e in ENTRIES)


def test_the_arrival_marks_and_clears_itself():
    assert "function markArrival(panel, cls)" in APP
    body = APP[APP.index("function markArrival"):]
    body = body[:body.index("\n}\n") + 3]
    assert "classList.add(cls)" in body
    assert "classList.remove(cls)" in body
    assert 'addEventListener("animationend", done, { once: true })' in body
    assert "setTimeout(done" in body, "a timer covers reduced-motion and a lost event"
    assert "_arrivalSeq" in body, "a stale timer must not strip a newer arrival"


def test_both_switches_use_it():
    for call in ('markArrival(incoming, "tab-in")',
                 'markArrival(incoming, "spanel-in")'):
        assert call in APP
    assert 'incoming.classList.add("tab-in")' not in APP
    assert 'incoming.classList.add("spanel-in")' not in APP


def test_the_fade_rule_itself_is_unchanged():
    """Only the class lifetime changed — the contents still dissolve in."""
    assert "@keyframes contentIn { from { opacity: 0; } }" in CSS
    assert ".tab-in .card > *" in CSS


def test_a_wrapper_full_of_glass_is_never_animated():
    """#subLink (index.html:116) holds the paste card AND the transport. It
    matched `.tab-in > :not(...)` and faded a glass ancestor — measured at
    opacity .847 mid-arrival, i.e. the backdrop root was back one level down."""
    assert ":not(.subpanel)" in CSS
    assert ".tab-in > .subpanel > :not(.card):not(.transport)" in CSS


def test_the_timer_respects_reduced_motion():
    body = APP[APP.index("function markArrival"):]
    body = body[:body.index("\n}\n") + 3]
    assert "motionMs(180)" in body, "under reduced motion the class must not linger"


def test_the_filed_rail_stops_rebuilding_every_poll():
    """renderBins() ran on every 1.2 s poll and re-created each .bin button
    whether or not the list had changed — glass re-composited once a second."""
    body = APP[APP.index("function renderBins"):]
    body = body[:body.index("\n}\n") + 3]
    assert "box.dataset.sig" in body
