"""The header stops duplicating the tabs, and Settings reads as a page.

Reported from a phone, with screenshots: the header carried a "⚙ Settings"
button directly above a Settings *tab* and an "Update yt-dlp" button that
belongs with the yt-dlp options; the settings panel rendered as an opaque,
square-cornered sheet with a ✕ in the corner — a dialog that was not a dialog.
The ✕ and the two opaque slabs (a sticky header plate and the Save bar) were
also exactly what covered the card's 20px rounded corners.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()

HEADER = HTML.split("<header>", 1)[1].split("</header>", 1)[0]
YTDLP = HTML.split('id="panel-ytdlp"', 1)[1]


def test_the_header_no_longer_duplicates_the_tabs():
    """One Settings entry point (the tab), one update button (with its options)."""
    assert 'id="settingsBtn"' not in HEADER
    assert 'id="updateBtn"' not in HEADER
    assert "settingsBtn" not in APP, "dangling wiring for a button that is gone"
    assert "settingsBtn" not in HTML
    # the host controls stay: they are not in the tab bar
    assert 'id="quitBtn"' in HEADER and 'id="minBtn"' in HEADER


def test_update_ytdlp_lives_with_the_ytdlp_options():
    card = YTDLP.split("</section>", 1)[0]
    assert 'id="updateBtn"' in card, "the button moved, it must not vanish"
    assert 'id="ytdlpVer"' in card, "say which version is installed"
    # and the version label is filled from /version, then refreshed after an update
    assert '$("ytdlpVer")' in APP
    handler = APP.split('$("updateBtn").onclick', 1)[1][:900]
    assert "loadVersions()" in handler


def test_settings_is_a_page_not_a_dialog():
    """No ✕ and no dialog header: the tab bar (or the rail) is the way out."""
    card = HTML.split('id="panel-settings"', 1)[1][:400]
    assert 'class="page-head"' in card
    assert "modal-head" not in card
    assert 'id="setClose"' not in HTML and "setClose" not in APP
    assert ".page-head {" in CSS and ".page-head h2 {" in CSS
    # the old dialog rules for settings are gone for good
    assert "#panel-settings .modal-head" not in CSS
    assert "#setClose" not in CSS


def test_the_sticky_save_bar_keeps_the_cards_shape():
    """It used to be a full-width opaque slab, which squared off the card's
    bottom corners and made the whole panel look like a modal sheet."""
    foot = CSS.split("#panel-settings .modal-foot {", 1)[1].split("}", 1)[0]
    assert "position: sticky" in foot, "Save must stay in reach"
    assert "var(--glass-bg-strong)" in foot, "the bar keeps the card's glass"
    assert "var(--panel-solid)" not in foot, "no opaque slab over the glass"
    assert "border-bottom-left-radius: 20px" in foot
    assert "border-bottom-right-radius: 20px" in foot
    # a sticky element that blurs smears its backdrop in Android's WebView
    assert "backdrop-filter" not in foot
