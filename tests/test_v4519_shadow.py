"""v0.45.19 "the shadow" — the popup dim restored, the Save strip floats.

Field report (2026-10-07, Android, AMOLED): "why there's no slight
blur/dimmed screen behind the pop up?" — and "make the save button in
settings have blur like ... in yt-dlp save button".

Root cause of the missing dim, caught in the live rig (the phone's own
state reproduced on desktop Chrome): the AMOLED theme set
`--shadow: none`. `none` is illegal inside a shadow LIST, and the veil
rides as a list member (`box-shadow: var(--shadow), inset …, 0 0 0
100vmax rgba(…)`) — so under AMOLED the whole declaration was invalid
and every composite shadow died (computed `none`), the popup veils
included. The phone runs AMOLED; the desktop tests ran dark. A
transparent zero shadow (`0 0 #0000`) is the list-legal "no shadow".

The Settings Save strip was a full-bleed bar (top border only) while
the yt-dlp tab's Save floats as a rounded glass card — the owner asked
for the match. The strip now twins that shape, frost included, on every
host (base + phone blocks; the Android host keeps its denser pour).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(encoding="utf-8")


def test_no_theme_nulls_the_shadow_token():
    # a `none` anywhere in a shadow LIST invalidates the entire
    # declaration — the AMOLED vehicle for a month of missing dims
    assert "--shadow: none;" not in CSS
    assert CSS.count("--shadow: 0 0 #0000;") == 1


def test_the_veil_survives_every_theme():
    assert "0 0 0 100vmax rgba(5, 7, 10, .55)" in CSS          # base
    assert "0 0 0 100vmax rgba(30, 29, 24, .30)" in CSS         # light override
    assert "0 0 0 100vmax rgba(3, 5, 12, .72)" in CSS           # android host


def test_the_settings_strip_twins_the_ytdlp_save():
    ytdlp = CSS.split("#panel-ytdlp .foot-row {")[1].split("}")[0]
    foot = CSS.split("#panel-settings .modal-foot {")[1].split("}")[0]
    for blk, name in ((ytdlp, "yt-dlp"), (foot, "settings")):
        assert "backdrop-filter: var(--glass-blur);" in blk, name
        assert "border-radius: 14px" in blk, name
    assert "border: 1px solid var(--line); border-radius: 14px;" in foot
    assert "margin: 14px 0 0" in foot, "floats, no longer full-bleed"
