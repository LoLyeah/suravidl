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
    # pre-release until the courier feature is verified — flipping this line
    # back is a deliberate, reviewable act
    assert "prerelease" in yml
