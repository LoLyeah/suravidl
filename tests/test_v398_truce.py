"""v0.39.8: the truce - a switch for the ad deny list.

Why (2026-10-02, the user): "What if the site has an anti-adblock measure and
refuses to let us in? Maybe add a button to disable the denylist?" Exactly
the failure a serve-empty deny list can cause: a page that notices its ad
scripts never load can refuse to play. The phone app's browser gets a truce
switch in its action row - "ads blocked" / "ads allowed" - remembered across
sessions, applied from the next request on, and the bounce guard (off-site
hops, scripted pop-ups) stays on either way.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
ANDROID = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
           "suravidl" / "app")
NAVGUARD = (ANDROID / "NavGuard.kt").read_text()
CLIENT = (ANDROID / "SnifferWebViewClient.kt").read_text()
ACTIVITY = (ANDROID / "BrowserActivity.kt").read_text()
TESTK = (ROOT / "android" / "app" / "src" / "test" / "java" / "com" /
         "suravidl" / "app" / "NavGuardTest.kt").read_text()
JS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
WHATSNEW = (ROOT / "src" / "suravidl_engine" / "whatsnew.py").read_text()


def test_the_deny_list_can_be_pardoned():
    assert "fun blocked(url: String, enabled: Boolean = true)" in NAVGUARD
    assert "if (!enabled) return false" in NAVGUARD


def test_the_client_asks_live_so_the_switch_needs_no_reopen():
    """The lambda is read per request: flipping the switch changes the next
    request, no new WebView, no restart."""
    assert "adsBlocked: () -> Boolean" in CLIENT
    assert "AdHosts.blocked(u, adsBlocked())" in CLIENT


def test_the_switch_sits_in_the_browser_row_and_is_remembered():
    assert '"ads_blocked"' in ACTIVITY
    assert 'getSharedPreferences("browser", MODE_PRIVATE)' in ACTIVITY
    assert 'getBoolean("ads_blocked", true)' in ACTIVITY
    assert "putBoolean(" in ACTIVITY and "ads_blocked" in ACTIVITY
    assert '"ads blocked"' in ACTIVITY and '"ads allowed"' in ACTIVITY
    assert "adsBlocked = { adBlock }" in ACTIVITY
    # the note tells the user the reload is theirs to make - no surprise reload
    assert "reload (\u27f3)" in ACTIVITY


def test_the_unit_test_covers_the_pardon():
    assert "fun adsBlockingCanBePardoned()" in TESTK


def test_the_faq_knows_the_truce():
    assert "turn off my ad blocker" in JS
    assert "ads allowed" in JS


def test_the_truce_entry_retired_cleanly():
    # The truce shipped with 0.39.8 and was announced in its card. The
    # rolling card keeps ten entries and retires the oldest — v0.40.4
    # retired this one, so the announcement lives in git and the release
    # notes now, and this pin retires WITH the entry (policy: a feature
    # stays pinned by its living tests — the FAQ and ACTIVITY pins above;
    # verbatim-entry pins age out with the list). All this test still
    # guards is that the retirement left no half behind; the shape test
    # (v32) covers the rest.
    assert '"version": "0.39.8"' not in WHATSNEW
    assert "The truce" not in WHATSNEW
