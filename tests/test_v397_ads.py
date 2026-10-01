"""v0.39.7: the bounce guard — the in-app browser refuses off-site hops and
ad pop-ups, so the page (and the find list) cannot be taken mid-hunt.

Report (2026-10-02, a private video on an ad-fed host): the page kept
redirecting the WebView to ad sites; finds appeared and were gone a fraction
of a second later when the redirect landed. Two hijack paths existed: a
top-level navigation straight off-site, and a (gestured or scripted) pop-up
window that loaded into the main view. Both now go through NavGuard.

Nothing private lives in this file on purpose: the guard works on any host,
and the tests below use example.com only.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "suravidl" / "app"
NAVGUARD = (APP / "NavGuard.kt").read_text()
CLIENT = (APP / "SnifferWebViewClient.kt").read_text()
ACTIVITY = (APP / "BrowserActivity.kt").read_text()
UNIT = (ROOT / "android" / "app" / "src" / "test" / "java" / "com" / "suravidl" /
        "app" / "NavGuardTest.kt").read_text()
GRADLE = (ROOT / "android" / "app" / "build.gradle").read_text()
YML = (ROOT / ".github" / "workflows" / "android.yml").read_text()
JS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_guard_is_pure_so_the_jvm_can_test_it():
    assert "object NavGuard" in NAVGUARD
    assert "fun blockReason(" in NAVGUARD and "fun siteKey(" in NAVGUARD
    assert "import android" not in NAVGUARD, "android.* would break JVM unit tests"


def test_only_the_main_frame_can_lose_the_page():
    assert "request?.isForMainFrame == false" in CLIENT
    assert "NavGuard.blockReason(pageUrl(), u)" in CLIENT
    assert "onHopBlocked(u)" in CLIENT


def test_popups_need_a_gesture_and_a_same_site_target():
    assert "if (!isUserGesture)" in ACTIVITY
    assert "reportPopupRefused()" in ACTIVITY
    assert "NavGuard.blockReason(currentPage, target)" in ACTIVITY
    assert "tap to follow anyway" in ACTIVITY


def test_classic_ad_hosts_load_as_empty_bodies():
    assert "object AdHosts" in NAVGUARD
    assert '"popads.net"' in NAVGUARD and '"doubleclick.net"' in NAVGUARD
    assert "AdHosts.blocked(u)" in CLIENT
    assert "ByteArrayInputStream(ByteArray(0))" in CLIENT


def test_the_jvm_tests_run_in_ci():
    assert "class NavGuardTest" in UNIT
    assert "testImplementation 'junit:junit:4.13.2'" in GRADLE
    assert "testDebugUnitTest" in YML


def test_the_faq_knows_about_the_bounce():
    assert "bouncing me at ads" in JS
    assert "tap the note on screen to follow it anyway" in JS
