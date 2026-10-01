"""v0.39.7: dress-up may not take the engine down.

Why (2026-10-02): the v0.39.6 build failed AppStartupTest on BOTH emulators
with android.app.RemoteServiceException$ForegroundServiceDidNotStartInTime-
Exception -- the process was crashed by the fg-start watchdog half a second
into the first test, four runs in a row, while v0.39.5 was green. A service
cannot reach startForeground when its notification build throws before the
call: the catch - stopSelf - destroys the service while the start is still
pending, and the system generates that exception at once.

The lesson, born as rules: a notification is dress-up. The drawn mark is
attempted; the platform glyph takes over when it rounds badly; and a last
plainfall posts even when both fail. startForeground is always reached.
And the big tile goes through the Drawable API -- on modern Android the
launcher icon is an adaptive-icon XML, which BitmapFactory cannot decode
(decodeResource returns null for it, silently).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
KOTLIN = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
          "suravidl" / "app" / "EngineService.kt").read_text()


def test_the_logo_is_rasterized_through_the_drawable_api():
    """decodeResource cannot read an adaptive icon: it returns null for the
    anydpi-v26 XML on every modern Android. The tile is drawn instead."""
    assert "private val notifLogo: android.graphics.Bitmap? by lazy" in KOTLIN
    assert "ContextCompat.getDrawable(this, R.mipmap.ic_launcher)" in KOTLIN
    assert "BitmapFactory.decodeResource" not in KOTLIN


def test_a_bad_notification_never_skips_start_foreground():
    """Both sites build through one helper; the helper falls back to the
    platform glyph; startInForeground has the plainest possible fallback;
    and only then does the call to go foreground happen."""
    assert "private fun buildNotification(" in KOTLIN
    assert 'buildNotification("starting engine\u2026", openApp = false)' in KOTLIN
    assert "buildNotification(text, openApp = true)" in KOTLIN
    assert KOTLIN.count("setSmallIcon(android.R.drawable.stat_sys_download)") == 2
    assert 'writeLog("notif-fallback", t)' in KOTLIN
    assert "ServiceCompat.startForeground(" in KOTLIN


def test_the_startup_guard_does_not_trip_on_a_recovered_badge():
    """The startup test fails on crash-* and engine-error* files; a
    recovered cosmetic hiccup logs under its own name instead."""
    assert 'writeLog("notif-fallback", t)' in KOTLIN
    assert 'writeLog("engine-error", t)' in KOTLIN   # the real failures still do
