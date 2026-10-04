#!/usr/bin/env python3
"""Generate the update manifest (version.json) + SHA256SUMS.txt for a release.

Run by the publish job over the downloaded dist/ folder just before the
release is created, so every release carries two little files:

- version.json — what the app's update check reads through the rate-limit-free
  `releases/latest/download/version.json` path: the version, per-file
  sha256/size, tag-PINNED download URLs (the hash in this manifest must always
  describe the bytes at that URL — latest/download would drift), and the role
  map the engine uses to pick its own platform's asset.
- SHA256SUMS.txt — the plain traditional list next to it.

Offline and deterministic: same inputs, same bytes; no network, no clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROLES = {
    "windows_installer": "suravidl-windows-x64-setup.exe",
    "windows_portable": "suravidl-windows-x64.exe",
    "macos_dmg": "suravidl-macos-arm64.dmg",
    "macos_app_zip": "suravidl-macos-arm64.zip",
    "linux_appimage": "suravidl-linux-x64.AppImage",
    "android_apk": "app-release.apk",
    "firefox_xpi": "suravidl-extension-firefox.xpi",
}

SKIP = {"version.json", "SHA256SUMS.txt"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dist", type=Path, help="the folder holding the release assets")
    ap.add_argument("--tag", required=True, help="the git tag, e.g. v0.41.0")
    ap.add_argument("--repo", required=True, help="owner/name on GitHub")
    ap.add_argument("--out", type=Path,
                    help="where the metadata lands (default: the dist folder)")
    args = ap.parse_args()

    if not args.tag.startswith("v") or len(args.tag) < 3:
        print(f"the tag must look like vX.Y.Z — got {args.tag!r} "
              f"(releases tag with a leading v)", file=sys.stderr)
        return 2
    version = args.tag[1:]

    files = sorted(p for p in args.dist.iterdir()
                   if p.is_file() and p.name not in SKIP)
    if not files:
        print(f"nothing to hash in {args.dist}", file=sys.stderr)
        return 2

    assets = {}
    for p in files:
        assets[p.name] = {
            "url": (f"https://github.com/{args.repo}/releases/"
                    f"download/{args.tag}/{p.name}"),
            "size": p.stat().st_size,
            "sha256": sha256_of(p),
        }
    roles = {role: name for role, name in ROLES.items() if name in assets}
    manifest = {"version": version, "tag": args.tag, "repo": args.repo,
                "assets": assets, "roles": roles}

    out = args.out or args.dist
    out.mkdir(parents=True, exist_ok=True)
    (out / "version.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    sums = "".join(f"{e['sha256']}  {name}\n"
                   for name, e in sorted(assets.items()))
    (out / "SHA256SUMS.txt").write_text(sums)
    print(f"manifest: {len(assets)} assets, version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
