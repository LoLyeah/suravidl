#!/usr/bin/env python3
"""Build all suravidl raster assets from the master SVGs in assets/brand/.

Regenerates: assets/logo.png, assets/icon.ico, the web icon, the extension
icon set, and the Android launcher mipmaps (legacy square + round, adaptive
foreground/background for all densities). Masters are the source of truth;
never hand-edit a PNG.

Requires: google-chrome (SVG render), Pillow. Run from the repo root:
    .venv/bin/python scripts/build_brand.py
"""
from pathlib import Path
import io
import struct
import subprocess
import tempfile

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
PINE = (20, 73, 60, 255)

CHROME = "google-chrome"


def render(svg: Path, size: int) -> Image.Image:
    """Render an SVG to RGBA at size x size via headless Chrome.

    The SVG is wrapped in an HTML page stretched to the viewport — Chrome
    lays an SVG document out at its intrinsic size otherwise.
    """
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "wrap.html"
        page.write_text(
            '<body style="margin:0;overflow:hidden">'
            f'<img src="file://{svg}" style="width:100vw;height:100vh;display:block">'
            "</body>"
        )
        out = Path(td) / "shot.png"
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={out}", f"--window-size={size},{size}",
             "--default-background-color=00000000", f"file://{page}"],
            check=True, capture_output=True, timeout=120,
        )
        return Image.open(out).convert("RGBA")


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"  {path.relative_to(ROOT)}  {img.width}x{img.height}")


def circle_mask(img: Image.Image) -> Image.Image:
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, img.width - 1, img.height - 1), fill=255)
    out = img.copy()
    out.putalpha(m)
    return out


def build_icns(bleed: Image.Image, out: Path) -> None:
    """The macOS dock icon: a hand-packed .icns container.

    Pillow only writes ICNS on macOS itself, so the container is packed
    here (magic + total length, then one PNG chunk per type). bleed is the
    1024 edge-to-edge master; every size is a Lanczos resize of it.
    """
    kinds = {  # icon type -> pixel size (ic10 is the 512@2x master)
        "icp4": 16, "icp5": 32, "ic07": 128, "ic08": 256, "ic09": 512,
        "ic10": 1024,
    }
    chunks = b""
    for kind, px in kinds.items():
        buf = io.BytesIO()
        bleed.resize((px, px), Image.Resampling.LANCZOS).save(buf, "PNG")
        raw = buf.getvalue()
        chunks += kind.encode() + struct.pack(">I", len(raw) + 8) + raw
    out.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)
    print(f"  {out.relative_to(ROOT)}  {sorted(kinds.values())}")


def main() -> None:
    master = render(BRAND / "mark.svg", 1024)          # margin version
    bleed = render(BRAND / "mark-bleed.svg", 1024)     # edge-to-edge
    arrow = render(BRAND / "arrow-cream.svg", 1024)

    # desktop / readme logo
    save(master, ROOT / "assets" / "logo.png")

    # macOS dock icon (the .app bundle's icon)
    build_icns(bleed, ROOT / "assets" / "icon.icns")

    # multi-size .ico (Windows + taskbar)
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    ico = bleed.resize((256, 256), Image.Resampling.LANCZOS)
    save_ico = ROOT / "assets" / "icon.ico"
    ico.save(save_ico, sizes=[(s, s) for s in ico_sizes])
    print(f"  assets/icon.ico  {ico_sizes}")

    # web favicon (the /static/icon.png the pages link)
    save(bleed.resize((128, 128), Image.Resampling.LANCZOS), ROOT / "src" / "suravidl_engine" / "web" / "icon.png")

    # extension icons
    for s in (16, 32, 48, 96, 128):
        save(bleed.resize((s, s), Image.Resampling.LANCZOS), ROOT / "extension" / "icons" / f"icon{s}.png")

    # Android launcher mipmaps
    density = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    dp108 = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
    res = ROOT / "android" / "app" / "src" / "main" / "res"
    for d, px in density.items():
        tgt = res / f"mipmap-{d}"
        sq = bleed.resize((px, px), Image.Resampling.LANCZOS)
        save(sq, tgt / "ic_launcher.png")
        flat = Image.new("RGBA", sq.size, PINE)
        flat.alpha_composite(sq)
        save(circle_mask(flat), tgt / "ic_launcher_round.png")
    for d, px in dp108.items():
        tgt = res / f"mipmap-{d}"
        # foreground: arrow at ~42% of the 108dp canvas, transparent
        content_px = 704  # the arrow's rendered width inside the 1024 master
        scale = (px * 0.42) / content_px
        fg = arrow.resize((round(1024 * scale),) * 2, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        canvas.alpha_composite(fg, ((px - fg.width) // 2, (px - fg.height) // 2))
        save(canvas, tgt / "ic_launcher_foreground.png")
        bg = Image.new("RGBA", (px, px), PINE)
        save(bg, tgt / "ic_launcher_background.png")

    print("done.")


if __name__ == "__main__":
    main()
