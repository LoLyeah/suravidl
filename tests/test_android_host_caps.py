"""The UI must not promise what the host cannot do.

Found while reviewing the Android install floor: below API 29 `MediaImporter`
skips the Gallery/Music import (no scoped storage → the app's own folder is
already reachable, so the copy would be pointless). The completion message
pointed at "Gallery → suravidl" on *every* Android version, sending users on
Android 7/8 to look for a copy that was never written.

The fix is host-answers-the-question, not user-agent guessing: the Kotlin
bridge exposes `galleryExport()` and the UI asks. These tests pin both halves
and — the part that matters — that they agree on the same boundary.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
JS = ROOT / "src/suravidl_engine/web/app.js"
KOTLIN = ROOT / "android/app/src/main/java/com/suravidl/app/MainActivity.kt"
IMPORTER = ROOT / "android/app/src/main/java/com/suravidl/app/MediaImporter.kt"


def test_the_ui_asks_the_host_about_gallery_export():
    js = JS.read_text()
    assert "AndroidHost.galleryExport()" in js, \
        "the UI must ask the host instead of assuming a gallery copy"
    # the promise and its opposite both exist, chosen at runtime
    assert '"saved where you can open it' in js
    assert "use Open or Share on a finished download" in js
    # the destructive confirms stop claiming a copy that may not exist
    assert js.count("GALLERY()") >= 3, \
        "the location line and both delete confirms must be gated"


def test_the_host_answers_with_the_same_rule_the_importer_uses():
    kotlin = KOTLIN.read_text()
    importer = IMPORTER.read_text()
    assert "fun galleryExport(): Boolean = Build.VERSION.SDK_INT >= 29" in kotlin
    # MediaImporter skips the import on exactly the same boundary — if one
    # moves without the other, the UI lies in one direction or the other
    assert "Build.VERSION.SDK_INT < 29" in importer


# -- the rest of the UI/Android review, same rule: pin the fix ---------------

ENGINE = ROOT / "android/app/src/main/java/com/suravidl/app/EngineService.kt"
APP = ROOT / "android/app/src/main/java/com/suravidl/app/SuravidlApp.kt"


def test_android_7_0_can_start_the_service():
    """NotificationChannel is API 26+, and its class is resolved when the line
    runs. Unguarded, an Android 7.0/7.1 phone — the floor the manifest
    declares — died with NoClassDefFoundError before Python ever started."""
    block = ENGINE.read_text().split("private fun startInForeground()")[1]
    block = block.split("val n = ")[0]
    assert "createNotificationChannel" in block
    assert "SDK_INT >= 26" in block, "the channel call must be guarded"


def test_a_failed_gallery_copy_gives_up_instead_of_looping_forever():
    """`existing` counts files, not copies, so on API<29 the old condition was
    never met: every finished job was re-checked every 2 seconds forever,
    writing a log line each time."""
    kt = ENGINE.read_text()
    assert "canCopy" in kt and "IMPORT_TRIES" in kt and "importTries" in kt
    assert "tries == 1" in kt, "only the first failure should reach the log"


def test_a_pending_share_survives_a_config_change():
    """It lived only in a field: a rotation or a low-memory kill between the
    share and the engine being ready dropped the user's link."""
    kt = KOTLIN.read_text()
    assert "onSaveInstanceState" in kt and "STATE_SHARED_URL" in kt
    assert "savedInstanceState?.getString(STATE_SHARED_URL)" in kt


def test_the_share_intent_states_its_read_grant():
    assert "ClipData.newRawUri" in KOTLIN.read_text()


def test_the_crash_log_is_read_from_both_places_it_can_be_written():
    """`write` falls back to the app-private dir; `readAll` only ever looked at
    the media dir, so a crash that was safely saved showed up as "No log
    recorded"."""
    kt = APP.read_text()
    assert 'getExternalFilesDir(null)?.let { File(it, "logs") }' in kt


def test_an_ancient_webview_gets_told_instead_of_a_blank_page():
    kt = KOTLIN.read_text()
    assert "webViewCanRunTheUi" in kt and r"Chrome/(\\d+)" in kt
    assert "update Android System WebView" in kt
