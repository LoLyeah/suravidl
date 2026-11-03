"""v0.48.0 "the palette" — three more schemes, Material You, and the ring.

The owner's screenshot: selected swatches wore a bright double outline under
AMOLED + Pine. Cause: `.swatch.on` drew a 1px `--accent` border plus a 3px
outer `--accent-soft` halo, `--ring` was only defined in one theme (so every
focus outline fell back to the cream accent), and the settings card — the one
slab with no blur — carried the *glass* border on true black.

This file pins the fix, the three new schemes (with their contrast pairs) and
the Material You mapping, including the fallback ladder.
"""
import pathlib
import re

from suravidl_engine import __version__, settings
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()
KOTLIN = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
          "suravidl" / "app" / "MainActivity.kt").read_text()

BG = {"light": "#e7e4de", "dark": "#0f1216", "amoled": "#000000"}


def _hex(c: str) -> tuple:
    c = c.strip().lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb: tuple) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(_hex(a)), _lum(_hex(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _block(marker: str) -> str:
    i = CSS.index(marker)
    return CSS[i:CSS.index("}", i)]


def _token(block: str, name: str) -> str:
    m = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", block)
    assert m, f"--{name} missing"
    return m.group(1)


def test_the_notes_name_this_release():
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.48.0" and e["title"].lower() == "the palette"
               for e in ENTRIES)


def test_the_selected_swatch_is_not_an_outline():
    """v0.48.0 shipped an inset ring here; the owner still saw a bright edge,
    so v0.48.1 replaced the whole treatment. The lesson outlives the rule: no
    outer halo and no stacked near-white strokes on a selected swatch."""
    block = _block(".swatch.on {")
    assert "inset 0 0 0 1px var(--accent2" not in block


def test_every_scheme_defines_its_own_ring():
    """:focus-visible falls back to var(--accent) when --ring is missing —
    which on AMOLED + Pine meant a cream outline."""
    # amber is the default voice: its ring lives in the base theme blocks
    root = CSS[CSS.index(":root, html[data-theme=\"dark\"]"):][:1800]
    amoled = CSS[CSS.index('html[data-theme="amoled"]'):][:900]
    assert "--ring:" in root and "--ring:" in amoled
    for accent in ("pine", "cobalt", "oxide", "silver"):
        blocks = re.findall(rf'html\[data-accent="{accent}"\]\[[^\]]+\][^{{]*{{([^}}]+)}}', CSS)
        assert blocks, accent
        assert any("--ring:" in b for b in blocks), f"{accent} has no --ring"
    assert 'html[data-accent="dynamic"][data-theme="light"]' in CSS
    assert "--ring: var(--dyn-accent-ink" in CSS


def test_the_new_schemes_hold_their_contrast():
    for accent in ("cobalt", "oxide", "silver"):
        for theme in ("light", "dark", "amoled"):
            block = _block(f'html[data-accent="{accent}"][data-theme="{theme}"]')
            ink = _token(block, "accent-ink")
            fg = _token(block, "accent-fg")
            acc = _token(block, "accent")
            assert contrast(ink, BG[theme]) >= 4.5, (accent, theme, "ink", contrast(ink, BG[theme]))
            assert contrast(fg, acc) >= 4.5, (accent, theme, "fg", contrast(fg, acc))


def test_the_new_schemes_never_touch_the_state_lights():
    for accent in ("cobalt", "oxide", "silver", "dynamic"):
        for b in re.findall(rf'html\[data-accent="{accent}"\]\[[^\]]+\][^{{]*{{([^}}]+)}}', CSS):
            for light in ("--ok:", "--err:", "--warn:"):
                assert light not in b, f"{accent} repaints a state light"


def test_settings_accepts_the_new_schemes():
    for accent in ("cobalt", "oxide", "silver", "dynamic"):
        assert accent in settings.ACCENTS


def test_the_swatches_exist_and_wallpaper_is_hidden_by_default():
    for accent in ("cobalt", "oxide", "silver"):
        assert f'data-accent="{accent}"' in HTML
    assert 'id="swDynamic"' in HTML
    dyn = HTML[HTML.index('id="swDynamic"'):]
    dyn = dyn[:dyn.index("</button>")]
    assert 'class="swatch hidden"' in HTML[HTML.index('id="swDynamic"') - 40:HTML.index('id="swDynamic"')]


def test_material_you_comes_from_the_bridge_or_not_at_all():
    assert "fun dynamicPalette(): String" in KOTLIN
    assert "Build.VERSION.SDK_INT < 31" in KOTLIN
    assert "system_accent1_600" in KOTLIN and "system_neutral1_50" in KOTLIN
    assert 'return ""' in KOTLIN                    # the pre-31 ladder
    assert "readDynamicPalette" in APP
    assert "onDynamicPaletteChanged" in APP
    assert 'classList.toggle("hidden", !DYN)' in APP  # swatch only when a palette exists


def test_the_dynamic_accent_maps_onto_tokens():
    for theme in ("light", "dark", "amoled"):
        block = _block(f'html[data-accent="dynamic"][data-theme="{theme}"]')
        assert "--dyn-accent" in block
    assert 'r.setProperty(name, v)' in APP or 'put("--dyn-" + k, v)' in APP
