"""v0.47.11 "the sheet" (extension 0.5.19) — the engine page wears the house.

The options page shipped as unstyled system-ui on white: the one screen a
new user is told to visit looked like a debug page. It now links the popup's
tokens and both faces, lays out a tab-sized column, hides the token behind
Show/Hide, and reads its version from the manifest.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
OPTS = (EXT / "options.html").read_text()
CSS = (EXT / "options.css").read_text()
JS = (EXT / "options.js").read_text()


def test_the_page_wears_the_popups_tokens_and_faces():
    assert '<link rel="stylesheet" href="popup.css" />' in OPTS
    assert '<link rel="stylesheet" href="options.css" />' in OPTS
    assert 'href="popup.css"' in OPTS and OPTS.index("popup.css") < OPTS.index("options.css")
    # the popup's 340px plate is widened for a tab, never stretched in place
    assert "width: auto" in CSS and "min(560px" in CSS


def test_the_token_is_a_secret_until_asked():
    assert 'id="reveal"' in OPTS and 'data-i18n="Show"' in OPTS
    assert 'field.type = hidden ? "text" : "password"' in JS
    assert 'type="password"' in OPTS


def test_enter_saves_instead_of_reloading_the_page():
    assert 'id="engineForm"' in OPTS
    assert "preventDefault" in JS and 'form.onsubmit' in JS


def test_the_version_chip_reads_the_manifest():
    assert 'id="ver"' in OPTS and 'id="ver"' in (EXT / "popup.html").read_text()
    assert 'MANIFEST.version' in JS


def test_the_shipped_version_moved_together():
    chrome = json.loads((EXT / "manifest.json").read_text())
    firefox = json.loads((EXT / "firefox" / "manifest.json").read_text())
    assert chrome["version"] == firefox["version"] == "0.5.19"
    assert "v0.5.19" in OPTS
