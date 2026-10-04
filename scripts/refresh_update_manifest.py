#!/usr/bin/env python3
"""Fold a late-arriving asset (the Android APK) into an existing manifest.

The publish job writes version.json + SHA256SUMS.txt over the dist/ set it
can see; the APK is built by the android workflow and attached afterwards.
This script merges that asset in with exactly the generator's rules — pinned
tag URL, size, sha256 — so the manifest on the release always describes the
complete release, Android included. Run by the attach-apk job.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def merge(meta_dir: Path, asset: Path, tag: str, repo: str) -> dict:
    """Add one asset to version.json + SHA256SUMS.txt; deterministic."""
    vj_path = meta_dir / "version.json"
    if not vj_path.is_file():
        raise FileNotFoundError(
            f"no version.json in {meta_dir} — this release predates the manifest")
    vj = json.loads(vj_path.read_text())
    vj.setdefault("assets", {})[asset.name] = {
        "url": f"https://github.com/{repo}/releases/download/{tag}/{asset.name}",
        "size": asset.stat().st_size,
        "sha256": sha256_of(asset),
    }
    vj["assets"] = {k: vj["assets"][k] for k in sorted(vj["assets"])}
    roles = dict(vj.get("roles") or {})
    roles["android_apk"] = asset.name
    vj["roles"] = {k: roles[k] for k in sorted(roles)}
    vj_path.write_text(json.dumps(vj, indent=2, sort_keys=True,
                                  ensure_ascii=True) + "\n")
    sums = "".join(f"{e['sha256']}  {name}\n"
                   for name, e in sorted(vj["assets"].items()))
    (meta_dir / "SHA256SUMS.txt").write_text(sums)
    return vj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("meta", type=Path, help="folder with version.json from the release")
    ap.add_argument("asset", type=Path, help="the late-arriving file to merge in")
    ap.add_argument("--tag", required=True, help="the git tag, e.g. v0.41.0")
    ap.add_argument("--repo", required=True, help="owner/name on GitHub")
    args = ap.parse_args()
    try:
        vj = merge(args.meta, args.asset, args.tag, args.repo)
    except (FileNotFoundError, ValueError) as e:
        print(f"manifest merge refused: {e}", file=sys.stderr)
        return 2
    print(f"manifest: {len(vj['assets'])} assets, {len(vj['roles'])} roles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
