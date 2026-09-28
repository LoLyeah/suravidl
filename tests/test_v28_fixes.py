"""The phone's two routes to a signed-in video, made explicit (v0.28.0).

The v0.27.0 plan, second half (P3 + P4). The engine side already carries the
session (cookies file / extension handoff / the in-app browser's own jar
rides every handoff). What this pins is that the *phone* shows its two
routes where the user actually is:

- sign in inside "Find a video on a page" — that browser's session goes with
  the download, and the browser says so (a hint line, the empty state, the
  start page);
- or import a cookies.txt exported from a desktop browser (the encrypted
  vault), and the Settings hint on Android names both;

plus docs/AUTH.md: the routes, the per-site notes (Facebook → cookies +
impersonation; Instagram → freshness, rate limits; DRM never), where cookies
live on each platform, and a verify-it-yourself checklist.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
BROWSER = (ROOT / "android/app/src/main/java/com/suravidl/app/BrowserActivity.kt").read_text()
SNIFFER_TEST = (ROOT / "android/app/src/androidTest/java/com/suravidl/app/SnifferTest.kt").read_text()
WEB = ROOT / "src/suravidl_engine/web"
HTML = (WEB / "index.html").read_text()
APP = (WEB / "app.js").read_text()
README = (ROOT / "README.md").read_text()


# -- 1. the in-app browser speaks its route --------------------------------

def test_the_browser_offers_the_sign_in_route_where_a_login_would_happen():
    assert 'tag = "signin-hint"' in BROWSER, \
        "the hint must carry a tag — an untagged view is untestable on device"
    assert "session goes with the download" in BROWSER, \
        "the one fact that matters: this browser's session is what the download uses"
    assert "tap to hide" in BROWSER, "a persistent ad is noise — it must dismiss"
    assert "You can sign in here" in BROWSER, \
        "the hint line itself must say the user may sign in on the page"


def test_the_empty_state_and_the_start_page_teach_the_same_route():
    assert "If the video needs a login" in BROWSER, \
        "a login-walled page finds nothing — the empty state is where that user is"
    assert "Need to sign in?" in BROWSER, \
        "the start page should say it before the first scan, not after"


def test_the_sniffer_suite_checks_the_hint_on_the_device():
    assert '"signin-hint"' in SNIFFER_TEST, \
        "a static substring check is decoration; the hint needs an on-device assertion"


# -- 2. the Android settings hint names both routes ------------------------

def test_the_android_settings_hint_names_both_routes():
    assert 'id="authHint"' in HTML, "the hint span needs an id to swap per host"
    assert '$("authHint")' in APP, "Android gives it its own words"
    seg = APP.split('$("authHint")')[1][:400]
    assert "Find a video on a page" in seg, "route one: sign in inside the app browser"
    assert "cookies.txt exported from a desktop browser" in seg, \
        "route two: the import — and where the file comes from"


# -- 3. the doc -----------------------------------------------------------------

def test_the_auth_doc_covers_the_routes_and_the_limits():
    doc = (ROOT / "docs/AUTH.md").read_text()
    for needle in ("Settings → Authentication", "cookies.txt", "Impersonate",
                   "Find a video on a page", "Facebook", "Instagram", "DRM"):
        assert needle in doc, f"AUTH.md must cover {needle!r}"
    assert "PRIVACY.md" in doc and "THREAT-MODEL.md" in doc, \
        "the doc must point at where the guarantees live"
    low = doc.lower()
    assert "rate" in low and ("expire" in low or "hours" in low), \
        "Instagram's reality (expiry, rate limits) is the most-asked failure"
    assert "verify" in low, "end with a checklist a user can run"


def test_the_readme_points_at_the_auth_doc():
    assert "docs/AUTH.md" in README, \
        "the README's signed-in bullet is where people land first"
