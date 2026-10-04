"""v0.41.0 "the courier" — the Windows installer line and the release manifest.

Two layers pinned here: the Inno Setup packaging (per-user install, a stable
installer name the app's updater depends on) and the release manifest
generator (version.json + SHA256SUMS.txt, read by every build through the
rate-limit-free releases/latest/download path).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _gen(dist: Path, tag="v0.41.0", repo="LoLyeah/suravidl"):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_release_manifest.py"),
         str(dist), "--tag", tag, "--repo", repo],
        capture_output=True, text=True)


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "suravidl-windows-x64.exe").write_bytes(b"PORTABLE")
    (dist / "suravidl-windows-x64-setup.exe").write_bytes(b"SETUP")
    (dist / "app-release.apk").write_bytes(b"APK!")
    (dist / "suravidl-macos-arm64.dmg").write_bytes(b"DMG")
    (dist / "suravidl-linux-x64.AppImage").write_bytes(b"APPIMAGE")
    (dist / "suravidl-extension-firefox.xpi").write_bytes(b"XPI")
    return dist


def test_the_manifest_is_deterministic_and_complete(tmp_path):
    dist = _make_dist(tmp_path)
    r = _gen(dist)
    assert r.returncode == 0, r.stderr
    m = json.loads((dist / "version.json").read_text())

    assert m["version"] == "0.41.0"
    assert m["tag"] == "v0.41.0"
    assert m["repo"] == "LoLyeah/suravidl"
    # every asset in the folder gets an entry with a real hash and size
    assert set(m["assets"]) == {p.name for p in dist.iterdir()
                                if p.name not in ("version.json", "SHA256SUMS.txt")}
    entry = m["assets"]["suravidl-windows-x64-setup.exe"]
    assert entry["sha256"] == hashlib.sha256(b"SETUP").hexdigest()
    assert entry["size"] == 5
    # download URLs are PINNED to this tag: the hash in this manifest must
    # always describe the bytes that URL serves, even after the next release
    assert entry["url"] == ("https://github.com/LoLyeah/suravidl/releases/"
                            "download/v0.41.0/suravidl-windows-x64-setup.exe")


def test_the_manifest_roles_are_what_the_updater_looks_up(tmp_path):
    dist = _make_dist(tmp_path)
    assert _gen(dist).returncode == 0
    m = json.loads((dist / "version.json").read_text())
    roles = m["roles"]
    assert roles["windows_installer"] == "suravidl-windows-x64-setup.exe"
    assert roles["windows_portable"] == "suravidl-windows-x64.exe"
    assert roles["android_apk"] == "app-release.apk"
    assert roles["macos_dmg"] == "suravidl-macos-arm64.dmg"
    assert roles["linux_appimage"] == "suravidl-linux-x64.AppImage"


def test_sha256sums_matches_the_manifest(tmp_path):
    dist = _make_dist(tmp_path)
    assert _gen(dist).returncode == 0
    m = json.loads((dist / "version.json").read_text())
    sums = (dist / "SHA256SUMS.txt").read_text()
    for name, entry in m["assets"].items():
        assert f"{entry['sha256']}  {name}" in sums, name


def test_the_manifest_rejects_a_bad_tag(tmp_path):
    dist = _make_dist(tmp_path)
    r = _gen(dist, tag="0.41.0")          # no leading v
    assert r.returncode != 0
    assert "v" in (r.stderr + r.stdout).lower()


def test_windows_installer_script_is_per_user(tmp_path):
    iss = (ROOT / "packaging/windows/suravidl.iss").read_text()
    assert "PrivilegesRequired=lowest" in iss
    assert "{localappdata}\\Programs\\suravidl" in iss
    # a stable installer file name — the updater downloads and runs exactly it
    assert "suravidl-setup" in iss
    assert "AppId" in iss
    # an interactive install may offer to launch; silent upgrades must not
    assert "skipifsilent" in iss


def test_the_release_workflow_builds_and_attaches_the_installer():
    yml = (ROOT / ".github/workflows/release.yml").read_text()
    assert "ISCC" in yml or "Inno Setup" in yml
    assert "suravidl-windows-x64-setup.exe" in yml
    assert "suravidl-windows-x64.exe" in yml
    # the manifest rides along in dist/ (the publish job uploads dist/*)
    assert "generate_release_manifest" in yml
    # full releases: the update feed reads releases/latest, and a prerelease
    # would hold the feed back by design — the courier went stable with
    # v0.41.1, so re-adding "prerelease" here is a deliberate, reviewable act
    assert "prerelease" not in yml


def _gen_no_apk(tmp_path: Path) -> Path:
    dist = _make_dist(tmp_path)
    (dist / "app-release.apk").unlink()      # the apk is attached later
    assert _gen(dist).returncode == 0
    return dist


def _refresh(meta: Path, apk: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/refresh_update_manifest.py"),
         str(meta), str(apk), "--tag", "v0.41.0", "--repo", "LoLyeah/suravidl"],
        capture_output=True, text=True)


def test_the_apk_folds_into_the_manifest(tmp_path):
    dist = _gen_no_apk(tmp_path)
    apk = tmp_path / "app-release.apk"
    apk.write_bytes(b"APK!")
    r = _refresh(dist, apk)
    assert r.returncode == 0, r.stderr
    m = json.loads((dist / "version.json").read_text())
    # the APK joins the assets with the same pinned-URL + hash discipline ...
    entry = m["assets"]["app-release.apk"]
    assert entry["sha256"] == hashlib.sha256(b"APK!").hexdigest()
    assert entry["size"] == 4
    assert entry["url"].endswith("/download/v0.41.0/app-release.apk")
    # ... and the updater's role lookup now finds it
    assert m["roles"]["android_apk"] == "app-release.apk"
    assert f"{entry['sha256']}  app-release.apk" in (dist / "SHA256SUMS.txt").read_text()
    # idempotent: the same inputs rewrite the same bytes
    before = (dist / "version.json").read_bytes()
    assert _refresh(dist, apk).returncode == 0
    assert (dist / "version.json").read_bytes() == before


def test_the_merge_refuses_a_manifestless_release(tmp_path):
    meta = tmp_path / "meta"
    meta.mkdir()
    apk = tmp_path / "app-release.apk"
    apk.write_bytes(b"APK!")
    r = _refresh(meta, apk)
    assert r.returncode != 0
    assert "version.json" in (r.stderr + r.stdout)


def test_the_attach_job_folds_the_apk_into_the_manifest():
    yml = (ROOT / ".github/workflows/android.yml").read_text()
    attach = yml.split("attach-apk:", 1)[1].split("\n  instrumentation:")[0]
    # uploads through gh, guarded: a missing release fails loudly instead of
    # letting the uploader create a stray release (v0.41.0 footgun)
    assert "gh release view" in attach
    assert "gh release upload" in attach
    # and folds the APK into the manifest right after uploading it
    assert "refresh_update_manifest" in attach
    assert "softprops" not in attach
