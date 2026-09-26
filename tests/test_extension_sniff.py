"""M4: desktop parity — the extension asks the engine what it is looking at.

The extension and the phone's in-app browser are the same feature in two
places, so the promises are pinned in one place: the pattern list comes from the
engine, a response Content-Type can upgrade a find whose *name* said nothing,
the popup hides fragments only because the engine said so — and nothing here
loosens the v0.21.2 audit (media-ish requests only, ever).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
BG = (ROOT / "extension/background.js").read_text()
POPUP = (ROOT / "extension/popup.js").read_text()


def test_a_lying_name_is_still_a_find():
    """A stream served as video/* from a URL nothing recognises is exactly the
    one yt-dlp would never hear about."""
    assert "chrome.webRequest.onHeadersReceived.addListener" in BG
    assert '"responseHeaders"' in BG, "the response headers are the whole point"
    assert "MEDIA_TYPES" in BG
    assert r"video\/" in BG and r"application\/dash\+xml" in BG
    assert 'details.type === "main_frame"' in BG, "documents are not media"


def test_the_header_capture_still_only_looks_at_media():
    """The v0.21.2 audit must survive the wider net: ordinary browsing's cookies
    never land in extension storage."""
    block = BG.split("onBeforeSendHeaders")[1].split("onHeadersReceived")[0]
    assert 'details.type === "media"' in block
    assert "MEDIA_RE.test(details.url)" in block


def test_the_popup_hides_fragments_only_on_the_engines_word():
    assert 'msg.type === "rank"' in BG and '"/sniff/rank"' in BG
    # no answer (engine down, no token) means show everything, so the popup's
    # render() only hides what the engine actually flagged
    assert "return null" in BG and "show everything" in BG
    assert "shape[m.url] && shape[m.url].hidden" in POPUP
    # and the user is told what was hidden, and why
    assert "hidden — part of the playlist above" in POPUP
    assert 'kind === "manifest" ? "playlist"' in POPUP


def test_the_handoff_still_carries_the_captured_headers():
    assert "reqHeaders[url]" in BG
    assert "JSON.stringify({ url, headers: captured })" in BG
    assert "Authorization" in BG
