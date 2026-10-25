"""v0.47.14 "the seal" — the Play Protect audit, confirmed and fixed.

Play Protect called the app "may be harmful" when an update was installed.
The cause is the app's *shape* (sideloaded + self-signed + installs APKs +
downloads code), but the audit it prompted found four real holes worth
closing: an update APK with no identity check, a same-site guard that
collapsed two-part suffixes, an ffmpeg fetch that would run on Android
(where a glibc binary can never work), and a hand-off that accepted any
path FileProvider happened to cover.
"""
import pathlib

from suravidl_engine import __version__, api, tools
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
JAVA = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "suravidl" / "app"
ANDROID_TEST = ROOT / "android" / "app" / "src" / "androidTest" / "java" / "com" / "suravidl" / "app"
JVM_TEST = ROOT / "android" / "app" / "src" / "test" / "java" / "com" / "suravidl" / "app"
APP_JS = ROOT / "src" / "suravidl_engine" / "web" / "app.js"
AUTH = {"Authorization": "Bearer testtoken"}


def test_the_notes_name_this_release():
    assert __version__ == "0.47.14"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the seal"
    assert len(ENTRIES) == 10, "the card shows ten releases; retire the oldest"


def test_android_is_not_a_linux_desktop(monkeypatch):
    # the audit's V-04: Android reports sys.platform == "linux", so the old
    # key matched the desktop linux build and would have fetched a glibc
    # binary that can never run under bionic
    monkeypatch.setenv("SURAVIDL_ANDROID", "1")
    assert tools.on_android() is True
    assert tools.platform_key().startswith("android-")
    assert tools.entry() is None
    st = tools.status()
    assert st["supported"] is False
    assert "Android" in st["note"]


def test_the_fetch_refuses_on_android(monkeypatch):
    monkeypatch.setenv("SURAVIDL_ANDROID", "1")
    out = tools.start_download()
    assert out["state"] == "error"
    assert "Android" in out["error"]


def test_the_endpoint_answers_501_on_android(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_ANDROID", "1")
    d = pathlib.Path(tmp_path)
    app = api.create_app(download_dir=d / "dl", auth_token="testtoken",
                         db_path=d / "jobs.db")
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.post("/tools/ffmpeg", headers=AUTH)
        assert r.status_code == 501
        assert "Android" in r.json()["detail"]
        # status stays answerable, so a UI that asks anyway is told why
        assert c.get("/tools/ffmpeg", headers=AUTH).json()["supported"] is False


def test_an_update_must_carry_our_own_certificate():
    trust = (JAVA / "ApkTrust.kt").read_text()
    main = (JAVA / "MainActivity.kt").read_text()
    # both API levels, because minSdk is 24
    assert "GET_SIGNING_CERTIFICATES" in trust
    assert "GET_SIGNATURES" in trust
    assert "signingCertificateHistory" in trust, "key rotation must still verify"
    assert "ApkTrust.signedLikeSelf" in main
    assert "ApkTrust.packageOf" in main
    assert "not signed by the same key" in main


def test_the_seal_is_proven_on_a_device_image():
    t = (ANDROID_TEST / "ApkTrustTest.kt").read_text()
    assert "theInstalledAppPassesItsOwnSeal" in t
    assert "aStrangerFileIsRefused" in t


def test_the_browser_guard_learned_two_part_suffixes():
    nav = (JAVA / "NavGuard.kt").read_text()
    assert "MULTI_PART" in nav
    for suffix in ('"co.uk"', '"com.au"', '"github.io"', '"pages.dev"'):
        assert suffix in nav
    assert "takeLast(take)" in nav
    assert "twoPartSuffixesDoNotBecomeOneSite" in (JVM_TEST / "NavGuardTest.kt").read_text()


def test_a_hand_off_only_leaves_from_the_downloads_folder():
    main = (JAVA / "MainActivity.kt").read_text()
    guard = (JAVA / "PathGuard.kt").read_text()
    assert "PathGuard.insideAny" in main
    assert "downloadRoots()" in main
    assert "canonicalPath" in guard, "a sibling or .. must not pass"
    t = (JVM_TEST / "PathGuardTest.kt").read_text()
    assert "aClimbOutIsNotInside" in t
    assert "aLookAlikeSiblingIsNotInside" in t


def test_the_phone_settings_hide_a_dead_download():
    app = APP_JS.read_text()
    assert 'if (ANDROID()) { const f = $("ffmpegField")' in app
    assert "ffmpeg ships inside the Android app" not in app  # it is the engine's line


def test_the_security_page_tells_the_truth():
    doc = (ROOT / "docs" / "SECURITY.md").read_text()
    for pin in ("REQUEST_INSTALL_PACKAGES", "SHA256SUMS.txt", "4A:03:C1:E5",
                "Install anyway", "dynamic code loading"):
        assert pin in doc, pin


def test_the_audit_itself_is_kept():
    report = (ROOT / "docs" / "audits" / "play-protect-2026-10.md").read_text()
    assert "Play Protect" in report and "V-01" in report and "D-01" in report
