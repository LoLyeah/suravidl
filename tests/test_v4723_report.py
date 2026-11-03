"""v0.47.23 "the report" — the browser says why a video never loaded.

The previous release guessed that WebView's gesture requirement was stopping
script-started playback. It was not: the spinner stayed, so that change is
reverted. A <video> that fails is silent by design, which is why nothing was
explained — the WebView client now reports the failure (network, HTTP status
or certificate) and the app shows it.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
JAVA = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "suravidl" / "app")
CLIENT = (JAVA / "SnifferWebViewClient.kt").read_text()
BROWSER = (JAVA / "BrowserActivity.kt").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    # retired by v0.48.1 "the tint"; the feature stays covered by its own tests
    assert not any(e["title"].lower() == "the report" for e in ENTRIES)


def test_the_wrong_hypothesis_is_gone():
    assert "mediaPlaybackRequiresUserGesture" not in BROWSER


def test_the_client_reports_every_kind_of_load_failure():
    assert "override fun onReceivedError(" in CLIENT
    assert "override fun onReceivedHttpError(" in CLIENT
    assert "override fun onReceivedSslError(" in CLIENT
    # an incomplete chain is the one case that may proceed — for media only
    assert "primary == android.net.http.SslError.SSL_UNTRUSTED" in CLIENT
    assert "incompleteChain && looksLikeMedia(url)" in CLIENT
    assert "handler?.cancel()" in CLIENT


def test_only_failures_that_a_player_would_hide_are_reported():
    assert "fun looksLikeMedia(" in CLIENT
    for ext in ('".mp4"', '".m3u8"', '".ts"', '".webm"', '"/media/"'):
        assert ext in CLIENT, ext


def test_the_browser_shows_the_reason():
    assert "onLoadError = { url, detail -> reportLoadError(url, detail) }" in BROWSER
    assert "private fun reportLoadError(" in BROWSER
    assert "LogStore.write(this, \"browser.log\"" in BROWSER
