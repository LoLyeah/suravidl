"""The API token is required, and the extension says so before you try.

Field report (2026-11-22): "the extension still doesn't explicitly tell the
user if they don't add an authentication token, even though the extension
won't work without it." It used to surface only as a 401 after a download
attempt — the one moment nobody wants to discover a setup problem.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
POPUP_HTML = (EXT / "popup.html").read_text()
POPUP = (EXT / "popup.js").read_text()
BACKGROUND = (EXT / "background.js").read_text()
OPTIONS_HTML = (EXT / "options.html").read_text()
OPTIONS_JS = (EXT / "options.js").read_text()


def test_the_state_carries_whether_a_token_is_saved():
    assert "hasToken" in BACKGROUND
    assert 'engineToken: ""' in BACKGROUND
    assert "hasToken," in BACKGROUND


def test_the_popup_has_a_plate_for_it():
    assert 'id="token"' in POPUP_HTML
    assert 'id="tokenOpts"' in POPUP_HTML
    assert "suravidl needs its API token" in POPUP_HTML


def test_the_plate_wins_over_a_list_it_cannot_send():
    i = POPUP.index("state.hasToken === false")
    block = POPUP[i:i + 700]
    assert '$("token").hidden = false;' in block
    assert '$("found").hidden = true;' in block
    assert '$("pagedoor").hidden = true;' in block
    assert "openOptionsPage" in block


def test_the_options_page_marks_the_field_required():
    assert 'id="engineToken"' in OPTIONS_HTML
    assert "required" in OPTIONS_HTML.split('id="engineToken"')[1][:200]
    assert 'id="tokenWarn"' in OPTIONS_HTML
    assert "No token saved" in OPTIONS_HTML


def test_an_empty_save_says_what_will_happen():
    assert "tokenWarning" in OPTIONS_JS
    assert "saved — but no token: downloads will be refused" in OPTIONS_JS
