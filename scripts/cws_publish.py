#!/usr/bin/env python3
"""Upload and publish the Chrome extension (Chrome Web Store API v2).

One-time setup (creds live outside the repo):

    mkdir -p ~/.config/suravidl
    cat > ~/.config/suravidl/cws.json <<'JSON'
    {"client_id": "...", "client_secret": "...", "refresh_token": "...",
     "publisher_id": "...", "item_id": "..."}
    JSON
    chmod 600 ~/.config/suravidl/cws.json

The same five values can come from the environment (CWS_CLIENT_ID,
CWS_CLIENT_SECRET, CWS_REFRESH_TOKEN, CWS_PUBLISHER_ID, CWS_ITEM_ID), which is
how CI uses this. See docs/CWS-PUBLISH.md for how to obtain them.

    python3 scripts/cws_publish.py --check          # where the store stands
    python3 scripts/cws_publish.py                  # build, upload, publish
    python3 scripts/cws_publish.py --zip x.zip      # upload a built zip
    python3 scripts/cws_publish.py --no-publish     # upload only (draft)
    python3 scripts/cws_publish.py --bump patch     # manifest +1, then ship

Exit codes: 0 done, 2 refused (nothing to ship / version not bumped),
1 anything else.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
CONFIG = pathlib.Path.home() / ".config" / "suravidl" / "cws.json"

API = "https://chromewebstore.googleapis.com"
UPLOAD = API + "/upload/v2"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/chromewebstore"

ENV_KEYS = {
    "client_id": "CWS_CLIENT_ID",
    "client_secret": "CWS_CLIENT_SECRET",
    "refresh_token": "CWS_REFRESH_TOKEN",
    "publisher_id": "CWS_PUBLISHER_ID",
    "item_id": "CWS_ITEM_ID",
}


def credentials() -> dict:
    cfg: dict = {}
    if CONFIG.exists():
        cfg = json.loads(CONFIG.read_text())
    for key, env in ENV_KEYS.items():
        cfg[key] = os.environ.get(env) or cfg.get(key)
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        sys.exit(
            "missing " + ", ".join(missing) + " — see docs/CWS-PUBLISH.md "
            f"(config file: {CONFIG})"
        )
    return cfg


def access_token(cfg: dict) -> str:
    body = urllib.parse.urlencode({
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"token refresh failed ({e.code}): {detail}")


def name_of(cfg: dict) -> str:
    return f"publishers/{cfg['publisher_id']}/items/{cfg['item_id']}"


def call(cfg: dict, token: str, method: str, url: str, body: bytes | None = None,
         ctype: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:600]}


def status(cfg: dict, token: str) -> dict:
    code, body = call(cfg, token, "GET", f"{API}/v2/{name_of(cfg)}:fetchStatus")
    if code != 200:
        sys.exit(f"fetchStatus failed ({code}): {json.dumps(body)[:400]}")
    return body


def version_in_zip(path: pathlib.Path) -> str:
    with zipfile.ZipFile(path) as z:
        data = json.loads(z.read("manifest.json"))
    return str(data["version"])


def build_zip(out: pathlib.Path) -> pathlib.Path:
    """The release's own recipe: everything in extension/ except the Firefox
    tree and the dev harness."""
    skip = {"firefox/", "test_harness.mjs"}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(EXT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(EXT).as_posix()
            if rel in skip or rel.startswith("firefox/"):
                continue
            z.write(p, rel)
    return out


def bump_manifest(kind: str) -> str:
    path = EXT / "manifest.json"
    data = json.loads(path.read_text())
    parts = [int(x) for x in str(data["version"]).split(".")]
    while len(parts) < 3:
        parts.append(0)
    if kind == "major":
        parts = [parts[0] + 1, 0, 0]
    elif kind == "minor":
        parts = [parts[0], parts[1] + 1, 0]
    else:
        parts = [parts[0], parts[1], parts[2] + 1]
    data["version"] = ".".join(str(x) for x in parts)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data["version"]


def published_versions(info: dict) -> set[str]:
    out = set()
    for key in ("publishedItemRevisionStatus", "submittedItemRevisionStatus"):
        rev = info.get(key) or {}
        for ch in rev.get("distributionChannels") or []:
            if ch.get("crxVersion"):
                out.add(str(ch["crxVersion"]))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Upload and publish the Chrome extension (CWS API v2).")
    ap.add_argument("--zip", type=pathlib.Path, help="a built zip (default: built from extension/)")
    ap.add_argument("--check", action="store_true", help="print the store's status and stop")
    ap.add_argument("--no-publish", action="store_true", help="upload but do not submit for review")
    ap.add_argument("--bump", choices=("patch", "minor", "major"), help="raise manifest version first")
    ap.add_argument("--force", action="store_true", help="upload even if this version is already on the store")
    args = ap.parse_args(argv)

    cfg = credentials()
    token = access_token(cfg)

    if args.check:
        info = status(cfg, token)
        pub = (info.get("publishedItemRevisionStatus") or {}).get("state")
        sub = (info.get("submittedItemRevisionStatus") or {}).get("state")
        print(json.dumps({
            "item": cfg["item_id"],
            "published": pub,
            "submitted": sub,
            "versions": sorted(published_versions(info)),
            "lastUpload": info.get("lastAsyncUploadState"),
            "warned": info.get("warned"),
            "takenDown": info.get("takenDown"),
        }, indent=2))
        return 0

    if args.bump:
        print(f"manifest -> {bump_manifest(args.bump)}")

    zip_path = args.zip
    if zip_path is None:
        zip_path = pathlib.Path("/tmp/suravidl-extension-chrome.zip")
        build_zip(zip_path)
    version = version_in_zip(zip_path)

    info = status(cfg, token)
    if version in published_versions(info) and not args.force:
        print(f"refusing: {version} is already on the store — bump extension/manifest.json "
              f"(--bump patch) or --force", file=sys.stderr)
        return 2

    print(f"uploading {version} ({zip_path.stat().st_size} bytes)…")
    code, body = call(cfg, token, "POST", f"{UPLOAD}/{name_of(cfg)}:upload",
                      body=zip_path.read_bytes(), ctype="application/zip")
    if code not in (200, 202):
        print(f"upload failed ({code}): {json.dumps(body)[:600]}", file=sys.stderr)
        return 1
    state = body.get("uploadState")
    print(f"upload state: {state} crx {body.get('crxVersion')}")

    for _ in range(30):
        if state != "UPLOAD_IN_PROGRESS":
            break
        time.sleep(4)
        state = (status(cfg, token).get("lastAsyncUploadState") or {}).get("state")
        print(f"  …{state}")
    if state and state not in ("SUCCESS",):
        print(f"upload did not succeed: {state}", file=sys.stderr)
        return 1

    if args.no_publish:
        print("uploaded; not submitted (--no-publish)")
        return 0

    code, body = call(cfg, token, "POST", f"{API}/v2/{name_of(cfg)}:publish", body=b"{}",
                      ctype="application/json")
    if code not in (200, 202):
        print(f"publish failed ({code}): {json.dumps(body)[:600]}", file=sys.stderr)
        return 1
    print(f"submitted: state={body.get('state')} item={body.get('itemId')}")
    if body.get("warningInfo"):
        print(json.dumps(body["warningInfo"], indent=2)[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
