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
