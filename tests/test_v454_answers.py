"""v0.45.4 "the answers" — the FAQ wears glass, and learns the current app.

Two asks on the released desktop (2026-10-05): "do it with the FAQ cards
too" — every entry is now a glass plate of the popup-standard material —
and "update the FAQ itself": the stale locations were fixed (the updater
lives at Settings → General; cookies at Settings → Authentication), the
extension answer gained the pairing token, and a new entry covers the
log for failed downloads. Every FAQ string ships translated.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src" / "suravidl_engine" / "web"
APP = (WEB / "app.js").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def _block(marker, text=CSS):
    i = text.index(marker)
    start = text.index("{", i)
    depth, j = 0, start
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces after " + marker)


def test_the_faq_entries_are_glass_cards():
    blk = _block("\n.faq-item {")
    for part in ("border-radius: 12px", "var(--glass-bg)",
                 "backdrop-filter: var(--glass-blur);",
                 "-webkit-backdrop-filter: var(--glass-blur);",
                 "var(--glass-gloss)", "var(--glass-border)"):
        assert part in blk, part
    assert "gap: 8px" in _block("\n.faqlist {")
    assert ".faq-item:first-child" not in CSS, "the divider-era rule is gone"


def test_the_faq_learned_the_current_app():
    assert "Settings → General checks" in APP
    assert "Settings → Tools" not in APP, "the stale location is gone"
    assert ("the token from Settings → Authentication goes into the "
            "extension's Options") in APP
    assert "A download failed — how do I see why?" in APP
    assert "press View log" in APP


def test_every_faq_string_ships_translated():
    m = re.search(r"const STRINGS = \{ en: \{\}, id: \{(.*?)\n\} \};", APP, re.S)
    d = json.loads("{" + m.group(1) + "}")
    block = re.search(r"const FAQ = \[(.*?)\n\];", APP, re.S).group(1)
    strings = re.findall(r'"([^"]+)"', block)
    assert len(strings) == 22, "11 entries, question + answer"
    for s in strings:
        assert s in d, f"untranslated FAQ string: {s[:70]}"
