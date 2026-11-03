"""v0.48.3 "the follow" — the theme previews follow the chosen scheme.

They were painted with amber literal colours, so choosing Cobalt turned the
Save button blue while Light/Dark/AMOLED still showed amber diagonals — the
scheme looked half-applied. Each accent now declares a deep/bright pair, and
the three theme chips read it: the light plate takes the deep shade, the dark
and AMOLED plates the bright one.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.48.4"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the rim"
    assert len(ENTRIES) == 10


def test_the_theme_chips_read_the_pair():
    assert ".sw-light  { background: linear-gradient(135deg, #f0ede8 45%, var(--pv-deep) 46%" in CSS
    assert ".sw-dark   { background: linear-gradient(135deg, #14181d 45%, var(--pv-bright) 46%" in CSS
    assert ".sw-amoled { background: linear-gradient(135deg, #000 60%, var(--pv-bright) 61%" in CSS


def test_no_theme_chip_is_painted_amber():
    for cls in ("sw-light", "sw-dark", "sw-amoled"):
        block = re.search(rf"\.{cls}\s*\{{([^}}]*)\}}", CSS).group(1)
        assert "#e8a33e" not in block, cls
        assert "var(--pv-" in block, cls


def test_no_chip_wears_a_rim():
    """v0.48.4: the hairline tinted against the art and read as a warm edge."""
    import re as _re
    block = _re.search(r"\.sw-preview\s*\{([^}]*)\}", CSS).group(1)
    assert "border: 0" in block and "1px solid rgba(127,127,127" not in block


def test_every_scheme_declares_both_shades():
    # amber is the default voice: its pair lives in :root and the amoled block
    assert CSS.count("--pv-deep:") >= 7 and CSS.count("--pv-bright:") >= 7
    for accent in ("pine", "cobalt", "oxide", "silver", "dynamic"):
        block = CSS[CSS.index(f'html[data-accent="{accent}"]'):]
        assert "--pv-deep" in block[:600], accent
        assert "--pv-bright" in block[:600], accent
