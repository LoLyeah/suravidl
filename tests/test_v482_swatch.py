"""v0.48.2 "the swatch" — the preview chips lose their diagonal.

The owner circled the preview chips, not the card: the two-tone
`linear-gradient(135deg, A 45%, B 46%, ...)` left a hard seam, and on the dark
plates the black half vanished into the card, so the remaining triangle read as
a torn or folded corner. Each chip is now a plate with one accent bar — the
scheme's own colour on the scheme chips, and the current scheme's deep/bright
pair on the three theme chips (so switching scheme still updates them).

The glass chips keep their gradient and must not grow a bar.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.48.2"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the swatch"
    assert len(ENTRIES) == 10


def test_no_chip_is_a_diagonal_any_more():
    for cls in ("sw-light", "sw-dark", "sw-amoled", "sw-amber", "sw-pine",
                "sw-cobalt", "sw-oxide", "sw-silver", "sw-dynamic"):
        m = re.search(rf"\.{cls}\s*\{{([^}}]*)\}}", CSS)
        assert m, cls
        assert "linear-gradient" not in m.group(1), cls


def test_every_chip_is_a_plate_with_one_bar():
    assert ".sw-preview::after" in CSS
    bar = CSS[CSS.index(".sw-preview::after"):]
    bar = bar[:bar.index("}")]
    assert "background: var(--pv-accent" in bar
    assert "border-radius: 3px" in bar


def test_the_theme_chips_follow_the_scheme_pair():
    assert ".sw-light  { --pv: #f0ede8; --pv-accent: var(--pv-deep); }" in CSS
    assert "--pv-accent: var(--pv-bright)" in CSS
    # amber is the default voice: its pair lives in the :root block
    root = CSS[CSS.index(":root, html[data-theme=\"dark\"]"):]
    assert "--pv-deep" in root[:2000]
    for accent in ("pine", "cobalt", "oxide", "silver", "dynamic"):
        block = CSS[CSS.index(f'html[data-accent="{accent}"]'):]
        assert "--pv-deep" in block[:600], accent


def test_the_glass_chips_keep_their_own_art():
    assert ".g-frosted::after, .g-liquid::after { display: none; }" in CSS
