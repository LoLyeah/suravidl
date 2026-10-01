"""v0.39.0: the popup's contract — readable, and the quality choice is the app's.

The popup was a wall of raw stream URLs with a download button per row: a
debug view, not a front door (the screenshot that started this version). The
redesign keeps the extension a *doorman*: it names what the page is playing
in plain words, offers a quiet chooser when the page really offered several
streams, and hands the find to the engine — where the format list and the
quality choice live, because that is where they are real.

The Node harness (extension/test_harness.mjs) drives the behavior against a
stubbed DOM; these pins hold the markup and stylesheet still wired for it —
the ids it drives, the promise-namespace guard Firefox needs, the house
tokens (one lamp, smoked glass, signal amber), and the one button's words.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
EXT = ROOT / "extension"

HTML = (EXT / "popup.html").read_text()
CSS = (EXT / "popup.css").read_text()
POPUP_JS = (EXT / "popup.js").read_text()
BG_JS = (EXT / "background.js").read_text()

# the ids extension/test_harness.mjs drives — the popup may add none it lacks
HARNESS_IDS = [
    "engine", "engineText", "found", "site", "favicon", "hostline",
    "headline", "subline", "pickgroup", "streams", "send",
    "empty", "down", "retry", "rescan", "status", "optsLink", "ver",
]


def test_the_popup_has_every_id_the_harness_drives():
    for i in HARNESS_IDS:
        assert f'id="{i}"' in HTML, f"popup.html lost #{i}"


def test_the_sections_still_start_hidden():
    """The script unhides exactly one card; a section rendered visible by
    default would flash on every open (and the down state would sit under
    the found card)."""
    import re
    # the status region is NOT hidden — it stays present so screen readers
    # announce it reliably; the stylesheet hides it while it is empty
    for section in ("found", "empty", "down", "pickgroup", "site"):
        assert re.search(f'id="{section}"[^>]*\\bhidden\\b', HTML), \
            f"#{section} must start hidden"


def test_the_popup_loads_its_own_stylesheet_and_script():
    assert '<link rel="stylesheet" href="popup.css" />' in HTML
    assert '<script src="popup.js"></script>' in HTML


def test_the_one_button_says_where_the_choice_happens():
    assert "Choose quality in suravidl" in HTML
    # the old debug view is gone: no per-row download button, no raw URLs
    assert "Download with suravidl" not in HTML


def test_the_version_line_tracks_the_manifest():
    """The footer prints the extension version; a bump that misses the line
    is how a store page and its popup end up disagreeing."""
    import json
    version = json.loads((EXT / "manifest.json").read_text())["version"]
    assert f'id="ver">v{version}<' in HTML


def test_the_popup_speaks_the_promise_namespace_guard():
    """Firefox's `chrome` namespace is callback-only (measured on Firefox
    157): every `await api.*` in the popup needs `browser`, which Chrome
    lacks — the guard picks whichever exists. Direct `chrome.` calls would
    break Firefox the day one is added."""
    assert "globalThis.browser || chrome" in POPUP_JS
    # every call goes through that guard: a bare `await chrome.…` or
    # `await browser.…` would pick one browser's semantics for both
    assert "await chrome." not in POPUP_JS
    assert "await browser." not in POPUP_JS
    assert "api.tabs.query(" in POPUP_JS and "api.runtime.sendMessage(" in POPUP_JS


def test_the_popup_keeps_the_engine_behind_the_background():
    """The popup must not know the engine's address or the token — that is
    the background's job; the popup only sends messages."""
    assert "http://" not in POPUP_JS and "https://" not in POPUP_JS
    assert "engineToken" not in POPUP_JS


def test_the_background_grew_the_handoff_and_the_health_check():
    assert '"/handoff"' in BG_JS and "sendHandoff" in BG_JS
    assert '"/health"' in BG_JS and "engineState" in BG_JS
    # an engine that predates /handoff still gets the old one-shot job
    assert "sendToEngine(url)" in BG_JS
    assert "res.status === 404 || res.status === 405" in BG_JS


def test_the_chooser_is_a_named_radio_group():
    assert 'role="radiogroup"' in HTML and 'aria-labelledby="pickLabel"' in HTML
    assert ".status:empty { display: none; }" in CSS


def test_the_stylesheet_carries_the_house_tokens():
    """One lamp (`--lamp` washes the top), smoked glass, signal amber — and
    the chip at night is the brand's dark-room twin (cream tile, pine)."""
    assert "--bg: #0f1216" in CSS
    assert "--accent: #e8a33e" in CSS
    assert "radial-gradient" in CSS and "var(--lamp)" in CSS
    assert "--mark-tile: #F2E9D8" in CSS and "--mark-arrow: #14493C" in CSS


def test_the_glass_is_honest():
    """Liquid Glass discipline: the vendor-prefixed pair travels together,
    and a `@supports` fallback means nobody ever sees a half-glass."""
    assert "-webkit-backdrop-filter: var(--glass-blur)" in CSS
    assert "backdrop-filter: var(--glass-blur)" in CSS
    assert "@supports not" in CSS


def test_the_parts_nobody_draws_are_drawn():
    assert "::selection" in CSS
    assert ":focus-visible" in CSS
    assert "::-webkit-scrollbar" in CSS
    assert "scrollbar-width: thin" in CSS        # Firefox's half of the pair
    assert "color-scheme: dark" in CSS
    assert "prefers-reduced-motion" in CSS


def test_the_fonts_travel_with_the_popup():
    for name in ("archivo-var.woff2", "martian-mono-var.woff2"):
        path = EXT / "fonts" / name
        assert path.exists(), f"{name} must ship inside the extension"
        assert path.stat().st_size > 10_000, f"{name} looks truncated"
        assert f'url("fonts/{name}")' in CSS
