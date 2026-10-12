"""v0.46.16 "the pickup": the companion extension, taught at the moment of
need.

Observed gap (2026-10-12): when a probe met a page no extractor knows, the
desktop read "\u2026then Scan for the stream" — a button only the phone
carries — and nothing offered the desktop's actual catcher, the extension.
The fix is platform-true: the phone keeps its browser door, the desktop gets
an offer row that opens a short guide sheet, the FAQ's extension answers link
to it, and every new string ships translated.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src" / "suravidl_engine" / "web"
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()
JS = (WEB / "app.js").read_text()
POPUP = (ROOT / "extension" / "popup.html").read_text()


def _id_map():
    m = re.search(r"const STRINGS = \{ en: \{\}, id: \{(.*?)\n\} \};", JS, re.S)
    return json.loads("{" + m.group(1) + "}")


def test_the_offer_row_is_platform_true():
    """The phone keeps its browser door; the desktop gets the extension one —
    the old function could only ever show the phone's."""
    assert 'id="extOffer"' in HTML and 'id="extOfferBtn"' in HTML
    assert "const phone = !!(window.AndroidHost && window.AndroidHost.openBrowser);" in JS
    assert 'row.classList.toggle("hidden", !phone);' in JS
    assert 'if (ext) ext.classList.toggle("hidden", phone);' in JS


def test_the_unsupported_copy_names_the_right_catcher_per_platform():
    assert ('t("no extractor knows this page — play it in your browser, then '
            'hand the stream over with the extension")') in JS
    assert ('t("no extractor knows this page — open it in the browser, press '
            'play, then Scan for the stream")') in JS   # the phone keeps its own
    assert "the extension may catch its audio" in JS    # the TikTok-photo arm too
    # the desktop sentence is no longer a bare untranslated return
    assert 'return "no extractor knows this page' not in JS


def test_the_guide_sheet_exists_and_speaks_the_popup_words():
    assert 'id="extModal"' in HTML and 'id="extDesktopSteps"' in HTML
    assert 'id="extPhoneLine"' in HTML
    # the guide quotes the extension's real button — both files must agree
    assert "Choose quality in suravidl" in HTML
    assert "Choose quality in suravidl" in POPUP


def test_the_sheet_is_honest_and_optional_first():
    assert "Most links need none of this" in HTML
    assert "What travels: the stream you picked, plus the session details" in HTML
    assert "Settings → Authentication" in HTML


def test_get_it_doors_open_the_real_pages():
    assert "addons.mozilla.org/en-US/firefox/addon/suravidl/" in JS
    assert "releases/latest/download/suravidl-extension-chrome.zip" in JS
    assert "openExternal(EXT_AMO)" in JS and "openExternal(EXT_ZIP)" in JS


def test_the_faq_answers_link_to_the_guide():
    assert "const [q, a, link] of FAQ" in JS
    assert JS.count('{ label: "the extension, step by step", open: openExtGuide }') == 2
    assert "lb.onclick = link.open;" in JS


def test_the_guide_answers_on_escape_like_every_dialog():
    assert "the extension guide answers on Escape like every dialog (v0.46.16)" in JS
    assert 'if (!$("extModal").classList.contains("hidden")) { closeModal($("extModal")); return; }' in JS


def test_one_frost_at_a_time_when_the_faq_hands_over():
    assert "a likely caller — one frost at a time" in JS
    assert 'if (faq && !faq.classList.contains("hidden")) closeModal(faq);' in JS


def test_the_phone_footnote_swaps_with_the_steps():
    assert 'steps.classList.toggle("hidden", phone);' in JS
    assert 'line.classList.toggle("hidden", !phone);' in JS


def test_every_new_string_ships_translated():
    d = _id_map()
    block = re.search(r'<div id="extModal".*?\n</div>', HTML, re.S).group(0)
    keys = re.findall(r'data-i18n="([^"]+)"', block)
    assert keys, "the sheet carries data-i18n keys"
    for k in keys:
        assert k in d, f"untranslated guide string: {k[:60]}"
    for k in ["How it works",
              "this page hides its player from the engine — the companion "
              "extension can hand the stream over",
              "no extractor knows this page — play it in your browser, then "
              "hand the stream over with the extension",
              "the extension, step by step"]:
        assert k in d, f"untranslated: {k[:60]}"


def test_the_sheet_reads_as_steps():
    assert ".extguide ol {" in CSS and ".extguide .linksrow {" in CSS
