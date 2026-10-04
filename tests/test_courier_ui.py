"""v0.41.0 "the courier" — the UI side of the update flow, plus the Kotlin
bridge contract it phones into.

Desktop: the Settings row walks stage -> verify -> restart into the
installer. Android: the same row, but the ready door is the system installer
(one confirmation tap, which Android requires); the JS calls the AndroidHost
bridge by name, so the names are pinned against the Kotlin — a rename on one
side without the other is a dead button.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
KOT = (ROOT / "android/app/src/main/java/com/suravidl/app/MainActivity.kt").read_text()
SVC = (ROOT / "android/app/src/main/java/com/suravidl/app/EngineService.kt").read_text()
PATHS = (ROOT / "android/app/src/main/res/xml/file_paths.xml").read_text()
MANIFEST = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text()


def _fn(name, end_marker):
    assert name in APP, f"{name} is missing"
    return APP.split(name, 1)[1].split(end_marker, 1)[0]


def test_the_settings_row_walks_the_whole_flow():
    row = APP[APP.index("function renderCourierRow"):
              APP.index("/** Resume the row's truth after a reload")]
    for token in ("Update to ${u.latest}", "startUpdateDownload",
                  "Downloading\u2026", "Verifying\u2026", "Restart & Install",
                  "Install update", "installStagedUpdate", "Try again"):
        assert token in row, token
    for ep in ("/update/download", "/update/status", "/update/apply"):
        assert ep in APP, ep
    assert "humanBytes(st.bytes" in row and "humanBytes(st.total)" in row, \
        "progress must read in real numbers"


def test_the_ready_door_picks_the_shell():
    door = _fn("async function installStagedUpdate", "function renderCourierRow")
    assert 'apply_kind === "windows_installer"' in door
    assert "AndroidHost.installApk(st.name)" in door
    assert "AndroidHost.canInstallPackages" in door
    assert "AndroidHost.openInstallPermissionSettings" in door
    assert "let suravidl install updates" in door, "the permission ask must explain"
    assert "openExternal" in door, "the release page is the last door"


def test_a_staged_download_resumes_after_a_reload():
    wire = _fn("function wireUpdateRow", "function openExternal")
    assert "syncStagedUpdate()" in wire, "the row must re-read a staged download"
    sync = _fn("async function syncStagedUpdate", "/** force")
    assert 'api("/update/status")' in sync
    assert "pollUpdateStatus();" in sync


def test_the_banner_offers_the_one_tap_when_it_can():
    banner = _fn("function showUpdateBanner", "/** force")
    assert '"Update now"' in banner and "startUpdateDownload()" in banner
    assert "Get ${u.latest}" in banner, "the release-page fallback stays"


def test_the_js_and_the_kotlin_agree_on_bridge_names():
    for name in ("canInstallPackages", "openInstallPermissionSettings",
                 "installApk"):
        assert name in APP, f"JS lost {name}"
        assert name in KOT, f"Kotlin lost {name}"


def test_the_apk_lands_where_the_fileprovider_serves_it():
    assert 'name="cache_updates" path="updates"' in PATHS
    assert "REQUEST_INSTALL_PACKAGES" in MANIFEST
    assert "SURAVIDL_ANDROID" in SVC
    assert '"updates/$fileName"' in KOT, "the bridge resolves the engine's bucket"
    assert '"$packageName.fileprovider"' in KOT


def test_the_installer_policy_is_jvm_tested():
    policy = (ROOT / "android/app/src/main/java/com/suravidl/app/"
              "UpdateInstallPolicy.kt").read_text()
    test = (ROOT / "android/app/src/test/java/com/suravidl/app/"
            "UpdateInstallTest.kt").read_text()
    assert "safeName" in policy and "needsUnknownSourcesPrompt" in policy
    assert '".."' in policy, "the traversal ban must be explicit"
    assert "UpdateInstallPolicy" in test
