"""v0.48.1 "the tint" — selection that isn't a headlight, and Material You
that can actually be reached.

The owner reported the same bright edge twice. v0.48.0 had replaced an outer
halo with a 1px `--accent` border plus a 1px `--accent2` inset — in AMOLED +
Pine those are cream and pure white, so the two strokes fused into a 2px
near-white outline on every selected swatch.

And the Wallpaper swatch never appeared: `applyDynamicPalette()` — the only
code that unhides it — ran only when the accent was ALREADY "dynamic", a
state nobody could reach. Behind that sat a second defect: the Kotlin bridge
emitted `"lamp":"rgba(...)}` with no closing quote, so JSON.parse threw and
the palette was null even on a phone that had one.

Selection is now a tint, a hairline and an LED — no outline.
"""
import json
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
KOTLIN = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
          "suravidl" / "app" / "MainActivity.kt").read_text()


def _block(marker: str) -> str:
    i = CSS.index(marker)
    return CSS[i:CSS.index("}", i)]


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.48.1" and e["title"].lower() == "the tint"
               for e in ENTRIES)


def test_selection_is_a_tint_not_an_outline():
    block = _block(".swatch.on {")
    assert "background: var(--accent-soft)" in block
    assert "border-color: var(--accent-line)" in block
    # the two near-white strokes that fused into a headlight
    assert "inset 0 0 0 1px var(--accent2" not in block
    assert "border-color: var(--accent)" not in block.replace("--accent-line", "")


def test_the_selected_swatch_carries_an_led():
    assert ".swatch.on .sw-label::before" in CSS
    assert "width: 6px; height: 6px" in CSS
    # the LED is not a second filled control: no accent-filled badge circle
    assert ".swatch.on::after" not in CSS


def test_the_palette_is_read_before_the_first_paint():
    boot = APP.index("applyDynamicPalette();\napplyTheme(CURRENT.theme")
    assert boot > 0
    assert APP.index("applyDynamicPalette();\napplyTheme(CURRENT.theme") < \
        APP.index("applyTheme(CURRENT.theme, CURRENT.glass, CURRENT.accent);",
                  boot)


def test_a_wallpaper_change_is_reread_on_resume():
    # inside the EXISTING resume listener: a second one would be shadowed by
    # whichever the tests (and the browser) see first
    fn = APP[APP.index('document.addEventListener("visibilitychange", () => {'):]
    body = fn[:fn.index("});")]
    assert "window.onDynamicPaletteChanged();" in body
    assert "refreshJobs();" in body


def test_the_bridge_emits_valid_json():
    """The missing quote before } made every palette unparseable (v0.48.0)."""
    assert '"\\"lamp\\":\\"" + lamp + "\\"}"' in KOTLIN
    payload = ('{"bg":"#000000","panel":"#000000","text":"#000000",'
               '"muted":"#000000","accent":"#000000","accent2":"#000000",'
               '"accent-fg":"#000000","accent-ink":"#000000",'
               '"accent-soft":"rgba(0,0,0,0.14)",'
               '"accent-line":"rgba(0,0,0,0.45)","glow":"rgba(0,0,0,0.40)",'
               '"sel":"rgba(0,0,0,0.28)","lamp":"rgba(0,0,0,0.07)"}')
    assert len(json.loads(payload)) == 13


def test_the_palette_is_formatted_locale_free():
    """%.2f under id-ID emits 0,14 — an rgba() the CSS parser drops. The
    owner's phone is Indonesian even when the app's UI is English."""
    assert "String.format(Locale.US" in KOTLIN
    assert "import java.util.Locale" in KOTLIN
    assert 'String.format("rgba(' not in KOTLIN


def test_the_reader_survives_a_broken_bridge():
    body = APP[APP.index("function readDynamicPalette()"):]
    body = body[:body.index("\nfunction paintDynamicPalette")]
    assert "try {" in body and "catch" in body     # a bad payload is not a crash


def test_the_old_ring_test_now_pins_the_lesson():
    """v0.48.0's test pinned the inset ring that caused this report; it now
    pins what must never return."""
    old = (ROOT / "tests" / "test_v480_themes.py").read_text()
    assert '"inset 0 0 0 1px" in block' not in old
