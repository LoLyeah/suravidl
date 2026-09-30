"""v0.38.0 — the pine & cream brand mark replaces the amber "s" tile.

The mark is drawn vector (no letter, no gradient): a pine tile with the cream
down-arrow, its play triangle knocked out so it inherits the tile. Themes swap
the two tones: light keeps the pine tile; dark and AMOLED use the cream-chip
twin (the pine tile would sink on those rooms at 1.8:1).
"""
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()
BRAND = ROOT / "assets" / "brand"

PINE = "#14493C"
CREAM = "#F2E9D8"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


def test_the_header_mark_is_drawn_svg_not_a_letter():
    assert 'class="mark"' in HTML
    assert '<div class="mark">s</div>' not in HTML
    assert "var(--mark-tile)" in HTML and "var(--mark-arrow)" in HTML


def test_the_mark_is_two_tones_from_theme_variables():
    # dark (default) and amoled: the cream chip at night
    assert CSS.count(f"--mark-tile: {CREAM}") == 2
    # light: the pine tile
    assert f"--mark-tile: {PINE}" in CSS
    # and the arrow always reads against its tile
    assert f"--mark-arrow: {PINE}" in CSS and f"--mark-arrow: {CREAM}" in CSS


def test_the_old_amber_tile_is_gone():
    assert "--accent2), var(--accent));" not in CSS  # the old gradient
    assert "font-weight: 700; font-size: 15px" not in CSS


def test_master_svgs_are_mortal_vector():
    for name in ("mark.svg", "mark-dark.svg", "mark-bleed.svg",
                 "arrow-pine.svg", "arrow-cream.svg",
                 "lockup-horizontal.svg", "lockup-horizontal-dark.svg",
                 "lockup-stacked.svg"):
        svg = (BRAND / name).read_text()
        for banned in ("<text", "<mask", "<filter", "<image", "base64"):
            assert banned not in svg, f"{name} contains {banned}"
        assert PINE in svg or CREAM in svg


def test_every_surface_has_its_icon_at_the_right_size():
    assert png_size(WEB / "icon.png") == (128, 128)
    for s in (16, 32, 48, 96, 128):
        assert png_size(ROOT / "extension" / "icons" / f"icon{s}.png") == (s, s)
    assert png_size(ROOT / "assets" / "logo.png") == (1024, 1024)
    ico = (ROOT / "assets" / "icon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00"  # a real multi-size .ico


def test_android_launcher_mipmaps_are_complete():
    res = ROOT / "android" / "app" / "src" / "main" / "res"
    legacy = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    adaptive = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
    for d, px in legacy.items():
        assert png_size(res / f"mipmap-{d}" / "ic_launcher.png") == (px, px)
        assert png_size(res / f"mipmap-{d}" / "ic_launcher_round.png") == (px, px)
    for d, px in adaptive.items():
        assert png_size(res / f"mipmap-{d}" / "ic_launcher_foreground.png") == (px, px)
        assert png_size(res / f"mipmap-{d}" / "ic_launcher_background.png") == (px, px)


def test_the_icon_png_centre_is_the_cream_arrow_on_a_pine_tile():
    import pytest
    PIL = pytest.importorskip("PIL.Image")
    im = PIL.open(WEB / "icon.png").convert("RGB")
    corner = im.getpixel((6, 64))       # inside the tile, off the arrow
    shaft = im.getpixel((64, 27))       # the arrow shaft, above the play
    assert corner[0] < 80 and corner[1] < 100 and corner[2] < 90      # pine
    assert shaft[0] > 200 and shaft[1] > 190 and shaft[2] > 180       # cream
