"""v0.49.4 "the day" — the light theme's weakest controls.

Walked the Download page in light mode with Cobalt. Contrast measured fine
(5.2-6.2:1 on every label), so the problems were hierarchy, not legibility:

- the disabled START was the accent at 55% opacity — on the day ground that is
  a dusty blue, a DIFFERENT colour rather than an unavailable control. It is a
  tint of the accent now, ink label, no glow: still primary, clearly inert.
- "Download now" disabled was a full-width empty pill the same fill as the card
  under it, reading as an input that had lost its label. It is a quiet
  borderless action now.
- the unlit scope LEDs were filled dark dots; on white that reads as a lit LED
  with the light off. Hollow rings say "instrument off" in every theme.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def _block(marker: str) -> str:
    i = CSS.index(marker)
    return CSS[i:CSS.index("}", i)]


def test_the_notes_name_this_release():
    assert __version__ == "0.49.4"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the day"
    assert len(ENTRIES) == 10


def test_a_disabled_primary_keeps_the_accent_family():
    block = _block(".btn.prime:disabled {")
    assert "background: var(--accent-soft)" in block
    assert "color: var(--accent-ink)" in block
    assert "opacity: 1" in block


def test_the_quick_action_is_quiet_when_off():
    block = _block("#quickBtn:disabled {")
    assert "background: transparent" in block
    assert "border-color: transparent" in block


def test_unlit_leds_are_hollow():
    block = _block("\n.led {")
    assert "background: transparent" in block
    assert "inset 0 0 0 1.5px var(--dim)" in block
