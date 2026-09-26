"""M3: the handoff — a found stream becomes a download, with its own headers.

Three promises are pinned here, all of them things the desktop extension already
keeps and the phone must now keep too:

  * the headers the browser hands over are ones the engine will actually forward
    to yt-dlp (`jobs.py` drops everything else silently, so a typo here would
    look like "the site needs a login" rather than a bug),
  * a "no extractor for this page" answer offers the browser — but only where a
    host actually has one, and never left armed for a URL the user replaced,
  * and the destructive "clear browsing data" takes the word, the engine-side
    rule from v0.21.1 applied to the browser.
"""
from pathlib import Path

from suravidl_engine.jobs import ALLOWED_HEADER_KEYS

ROOT = Path(__file__).parent.parent
APP = ROOT / "android/app/src/main/java/com/suravidl/app"
HANDOFF = APP / "Handoff.kt"
BROWSER = APP / "BrowserActivity.kt"
MAIN = APP / "MainActivity.kt"
HTML = ROOT / "src/suravidl_engine/web/index.html"
JS = ROOT / "src/suravidl_engine/web/app.js"
FIXTURE = ROOT / "android/app/src/androidTest/java/com/suravidl/app/FixtureServer.kt"


def test_the_handoff_headers_are_ones_the_engine_forwards():
    src = HANDOFF.read_text()
    for key in ("User-Agent", "Referer", "Cookie"):
        assert f'"{key}"' in src, f"{key} left the handoff"
        assert key.lower() in ALLOWED_HEADER_KEYS, \
            f"the engine would silently drop {key}"
    # markers are proof, never downloads
    assert "isHandoffable" in src and "blob:" in src


def test_a_found_stream_can_be_classified_and_downloaded_from_the_browser():
    src = BROWSER.read_text()
    assert "Handoff.classify(" in src and "Handoff.download(" in src
    assert '"Download"' in src, "the row lost its download button"
    # the cookie comes from this WebView's own jar, the referer from the frame
    assert "CookieManager.getInstance().getCookie(c.url)" in src
    assert "c.frame.ifEmpty { currentPage }" in src
    # DRM never gets a download button
    assert "isDrm(c.url)" in src


def test_clearing_browser_data_takes_the_word():
    src = BROWSER.read_text()
    assert 'setTitle("Clear browsing data?")' in src
    assert "setNegativeButton" in src, "a destructive confirm needs a way out"
    assert "removeAllCookies" in src and "deleteAllData" in src
    # and it must say what it does *not* touch
    assert "cookie file" in src


def test_an_unsupported_probe_offers_the_browser_only_where_there_is_one():
    html = HTML.read_text()
    js = JS.read_text()
    assert 'id="browserOffer"' in html and 'id="browserOfferBtn"' in html
    assert "function offerBrowser" in js
    assert "detail.unsupported" in js, "the engine's own flag is the trigger"
    assert "AndroidHost.openBrowser" in js, "the offer must ask the host"
    # hidden again the moment a probe works
    assert 'browserOffer").classList.add("hidden")' in js
    # and the host implements what the offer calls
    assert "fun openBrowser" in MAIN.read_text()


def test_the_token_can_be_read_where_it_is_needed():
    """M4: the extension needs the token and a phone cannot read
    ~/.suravidl/token — so Settings shows a masked copy, with a way to take it.
    Masked because it is a secret and screenshots happen."""
    html = HTML.read_text()
    js = JS.read_text()
    assert 'id="apiToken"' in html and 'id="copyToken"' in html
    assert "function wireToken" in js and "wireToken();" in js
    assert "slice(0, 6)" in js, "the row shows a mask, not the secret"
    assert "navigator.clipboard" in js, "and the copy button is the way out"


def test_the_guarded_fixture_keeps_the_handoff_test_honest():
    """The end-to-end handoff test is only worth something if the fixture would
    have said no without the browser's own headers."""
    src = FIXTURE.read_text()
    assert "guardAllows" in src and "403" in src
    assert 'cookie.contains("sv=ok")' in src
    assert 'referer.contains("/guarded.html")' in src
