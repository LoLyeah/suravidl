"""v0.49.0 "the landing" — the one authored beat after the probe.

A finishing job rebuilds its row (the signature includes the status), so the
progress groove cannot settle: it is simply gone between two polls. The beat
therefore lives on what survives the rebuild — the COMPLETED pill stamps flat
and a scanner pass runs along the row's top edge, once per job.

Motion rules this file protects: one beat, never replayed by a poll, linear
sweep (an eased fade killed the line by a quarter of the pass — measured),
and the global reduced-motion rule still zeroes every duration.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.49.0"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the landing"
    assert len(ENTRIES) == 10


def test_the_beat_only_fires_on_a_real_transition():
    assert 'if (j.status === "completed" && was && ACTIVE.has(was) && !LANDED.has(j.id))' in APP
    assert 'const was = row.dataset.status;' in APP
    assert 'LANDED.add(j.id);' in APP
    # and it must not stick around to replay on the next poll
    assert 'fresh.classList.remove("landed"), 720' in APP


def test_the_beat_is_a_stamp_and_a_sweep():
    assert ".job.landed .pill { animation: stampLand" in CSS
    assert ".job.landed::before" in CSS
    assert "@keyframes stampLand" in CSS and "@keyframes scanPass" in CSS


def test_the_sweep_is_linear_and_stays_lit():
    """An eased opacity fade measured 0.116 at the midpoint — invisible."""
    assert "animation: scanPass .5s linear both;" in CSS
    scan = CSS[CSS.index("@keyframes scanPass"):]
    scan = scan[:scan.index("}") + 1]
    assert "opacity" not in scan


def test_reduced_motion_still_stops_it():
    block = CSS[CSS.index("@media (prefers-reduced-motion: reduce)"):]
    block = block[:1200]
    assert "animation-duration: .001s !important;" in block
