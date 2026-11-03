"""v0.49.2 "the ring" — three polish defects found by using the app.

Walked the paste → probe → start → filed path at 900px and 412px with touch
emulation, plus keyboard-only focus. Three real defects, all fixed here:

- the paste field stacked the 2px focus ring on top of its 4px soft halo for
  a keyboard focus: two cues on the same control;
- a 412px field cut the placeholder mid-word with no ellipsis, which reads as
  a broken string;
- the new palette note had no Indonesian translation.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.49.2"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the cue"
    assert len(ENTRIES) == 10


def test_the_field_wears_one_focus_cue():
    assert ".paste input:focus-visible { box-shadow: none; }" in CSS
    assert ".paste input:focus { border-color: var(--accent-line); box-shadow: 0 0 0 4px var(--accent-soft); }" in CSS


def test_the_placeholder_ellipsises():
    assert "#url { text-overflow: ellipsis; }" in CSS


def test_the_palette_note_speaks_indonesian():
    assert '"this phone did not return a wallpaper palette": "ponsel ini tidak memberi palet wallpaper"' in APP
