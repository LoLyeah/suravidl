"""v0.42.0 "the crossing" — the courier reaches macOS.

The update flow finally covers all three platforms: on macOS the app
downloads a zip of the .app, verifies it, and a detached swap script
waits for the app to die, swaps the bundle by rename, rolls back on any
failure, and reopens it.

The script ships as package data (src/suravidl_engine/macos_swap.sh) so
the macOS CI job can dry-run the VERY file the app executes — these pins
hold the shape; the live dry-run holds the mechanics.
"""
import subprocess
from pathlib import Path

from suravidl_engine import updater

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "suravidl_engine"
SWAP = SRC / "macos_swap.sh"
APP = (SRC / "web" / "app.js").read_text()


def _client(tmp_path, **kw):
    from suravidl_engine.api import create_app

    app = create_app(download_dir=str(tmp_path), auth_token="t",
                     db_path=":memory:", **kw)
    from fastapi.testclient import TestClient

    return TestClient(app), {"Authorization": "Bearer t"}


# --- the feed: roles and platform wiring ------------------------------------


def test_the_manifest_carries_the_mac_zip_role():
    gen = (ROOT / "scripts/generate_release_manifest.py").read_text()
    assert '"macos_app_zip": "suravidl-macos-arm64.zip"' in gen


def test_macos_is_now_an_apply_platform():
    assert updater._APPLY_KINDS["macos"] == "macos_app_zip"
    assert updater._ROLE_FOR["macos"] == "macos_app_zip"


def test_check_update_resolves_the_zip_on_macos(monkeypatch):
    monkeypatch.setattr(updater, "running_platform", lambda: "macos")
    m = {"version": "9.9.9", "tag": "v9.9.9",
         "assets": {"suravidl-macos-arm64.zip": {
             "url": "https://github.com/LoLyeah/suravidl/releases/download/"
                    "v9.9.9/suravidl-macos-arm64.zip",
             "size": 10, "sha256": "x" * 64}},
         "roles": {"macos_app_zip": "suravidl-macos-arm64.zip"}}
    r = updater.check_update("0.1.0", manifest_fn=lambda repo: m)
    assert r["update_available"] is True
    assert r["can_apply"] is True
    assert r["apply_kind"] == "macos_app_zip"
    assert r["asset"]["name"] == "suravidl-macos-arm64.zip"


def test_the_ci_builds_and_ships_the_mac_zip():
    yml = (ROOT / ".github/workflows/release.yml").read_text()
    assert "ditto -c -k --keepParent dist/suravidl.app" in yml
    assert "suravidl-macos-arm64.zip" in yml


def test_the_ci_dry_runs_the_very_script_the_app_runs():
    yml = (ROOT / ".github/workflows/release.yml").read_text()
    assert "bash src/suravidl_engine/macos_swap.sh" in yml
    assert "SURAVIDL_APPLY_DRYRUN=1" in yml


# --- the swap script itself --------------------------------------------------


def test_the_swap_script_waits_swaps_and_rolls_back():
    s = SWAP.read_text()
    assert "kill -0" in s, "it must wait for the old app to exit"
    assert 'mv "$APP" "$OLD"' in s, "the swap is a rename, never a copy"
    assert 'mv "$NEW" "$APP"' in s
    assert 'mv "$OLD" "$APP"' in s, "a failed swap must roll back"
    assert "ditto -x -k" in s, "extract beside the old bundle (same fs)"
    assert "xattr -dr com.apple.quarantine" in s
    assert "SURAVIDL_APPLY_DRYRUN" in s, "the CI hook stops the relaunch"
    assert 'relaunch "$APP"' in s


def test_the_relaunch_is_hardened_and_leaves_a_trace():
    """v0.46.3 "the comeback". The reopen is the leg no CI dry-run rides,
    and in the field it failed silently: "update and restart just shuts
    down". A plain open can activate a stale window-less registration;
    a lingering old process makes it worse; and nothing wrote anywhere."""
    s = SWAP.read_text()
    assert "open -n" in s, "the reopen must force a FRESH instance"
    assert "suravidl-update.log" in s, "a failed relaunch must leave a trace"
    assert 'INNER="$1/Contents/MacOS/$EXEC"' in s, "the direct-exec fallback"
    assert 'kill -TERM "$PID"' in s and 'kill -KILL "$PID"' in s, \
        "a lingering old process must be ended, or the reopen lands on it"
    assert 'ps -p "$PID" -o comm=' in s, "never kill a recycled pid"
    assert 'SURAVIDL_APPLY_WAIT_TICKS' in s, "CI must be able to shrink the wait"


def test_the_app_leaves_deliberately_when_the_window_is_gone():
    src = (SRC / "__main__.py").read_text()
    assert "os._exit(0)" in src, \
        "after the update destroys the window, a lingering process must \n" \
        "leave on its own — the swap waits on exactly that pid"


def test_the_script_is_valid_bash():
    r = subprocess.run(["bash", "-n", str(SWAP)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_the_staging_names_are_mktemp_not_predictable():
    """v0.43.3 (audit follow-up): a PID-named staging directory in the
    install folder is a symlink-planting target for a local program —
    mktemp creates a fresh 0700 path and never reuses an existing name."""
    s = SWAP.read_text()
    assert "mktemp -d" in s
    assert ".suravidl-update.$$" not in s
    assert ".suravidl-old.$$" not in s


def test_the_app_bundle_ships_the_swap_script():
    spec = (ROOT / "suravidl.spec").read_text()
    assert "macos_swap.sh" in spec


# --- engine-side helpers -----------------------------------------------------


def test_the_bundle_is_found_from_the_executable():
    b = updater.app_bundle_from("/Applications/suravidl.app/Contents/MacOS/suravidl")
    assert str(b) == "/Applications/suravidl.app"
    assert updater.app_bundle_from("/home/u/proj/.venv/bin/python") is None


def test_the_apply_command_rides_the_bundled_script():
    cmd = updater.macos_apply_command("/Applications/suravidl.app",
                                      "/tmp/suravidl-macos-arm64.zip", 4242)
    assert cmd[0] == "/bin/bash"
    assert cmd[1].endswith("macos_swap.sh")
    assert cmd[2] == "suravidl-apply"
    assert cmd[3:] == ["/Applications/suravidl.app",
                       "/tmp/suravidl-macos-arm64.zip", "4242"]


def test_translocated_and_read_only_copies_get_words(tmp_path):
    t = tmp_path / "AppTranslocation" / "abc" / "d" / "suravidl.app"
    why = updater.macos_apply_refusal(t)
    assert why and "drag" in why
    assert "drag" in updater.macos_apply_refusal(
        Path("/Volumes/suravidl/suravidl.app"))
    ro = tmp_path / "ro" / "suravidl.app"
    ro.mkdir(parents=True)
    ro.parent.chmod(0o500)                 # a folder the user cannot write
    try:
        why = updater.macos_apply_refusal(ro)
        assert why and "cannot replace itself" in why
    finally:
        ro.parent.chmod(0o700)
    assert updater.macos_apply_refusal(ro) is None


# --- wiring: the action, the endpoint, the UI --------------------------------


def test_the_action_takes_the_macos_path():
    src = (SRC / "__main__.py").read_text()
    acts = src.split("def _make_apply_update_action", 1)[1] \
              .split("\n    return _apply_update", 1)[0]
    assert 'sys.platform == "darwin"' in acts
    assert "macos_apply_command(" in acts
    assert "macos_apply_refusal(" in acts
    assert "start_new_session=True" in acts, "the swap must outlive us"


def test_apply_carries_the_appliers_specific_words(tmp_path):
    updater.reset_update_state(status="ready",
                               path=str(tmp_path / "x.zip"), name="x.zip")
    c, h = _client(tmp_path, desktop_actions={
        "apply_update": lambda path=None: "drag suravidl into Applications"})
    r = c.post("/update/apply", headers=h)
    body = r.json()
    assert body["ok"] is False
    assert body["reason"] == "drag suravidl into Applications"


def test_the_ui_hands_macos_to_the_desktop_applier():
    assert ('const DESKTOP_APPLY_KINDS = ["windows_installer", '
            '"macos_app_zip"];') in APP
    assert "DESKTOP_APPLY_KINDS.indexOf(UPD_STATE.apply_kind) !== -1" in APP


def _shim_bin(tmp_path):
    """ditto/xattr stand-ins so the swap mechanics run on any POSIX box."""
    d = tmp_path / "shimbin"
    d.mkdir()
    ditto = d / "ditto"
    ditto.write_text(
        '#!/bin/bash\n'
        # only the extraction direction matters: -x -k ZIP DEST
        'if [ "$1" = "-x" ]; then exec python3 -c '
        '"import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" '
        '"$3" "$4"; fi\n'
        'exit 0\n')
    ditto.chmod(0o755)
    xattr = d / "xattr"
    xattr.write_text("#!/bin/bash\nexit 0\n")
    xattr.chmod(0o755)
    return d


def test_the_swap_mechanics_on_a_fixture(tmp_path):
    import os
    import zipfile

    shimbin = _shim_bin(tmp_path)
    installed = tmp_path / "installed" / "suravidl.app"
    (installed / "Contents").mkdir(parents=True)
    (installed / "Contents" / "OLD").write_text("old")
    z = tmp_path / "update.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("suravidl.app/Contents/NEW", "new")
    env = dict(os.environ, PATH=f"{shimbin}:{os.environ['PATH']}",
               SURAVIDL_APPLY_DRYRUN="1")
    r = subprocess.run(["bash", str(SWAP), "suravidl-apply",
                        str(installed), str(z), "999999"],
                       capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0, r.stderr
    assert (installed / "Contents" / "NEW").exists(), "the swap did not land"
    assert not (installed / "Contents" / "OLD").exists(), "old bundle lingered"
    # v0.42.1: the carrier is consumed once the swap lands
    assert not z.exists(), "the spent update zip must be gone"

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("notanapp.txt", "nope")
    r = subprocess.run(["bash", str(SWAP), "suravidl-apply",
                        str(installed), str(bad), "999999"],
                       capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode != 0, "a zip without a bundle must not report success"
    assert (installed / "Contents" / "NEW").exists(), "rollback left nothing?"
    # v0.42.1: a failed swap keeps the carrier — the boot sweep, not the
    # script, decides its fate once the app is back up
    assert bad.exists(), "a failed swap keeps the carrier for a retry"
