"""yt-dlp self-update via pip (venv/pip installs; frozen builds use their own)."""
import json
import os
import subprocess
import sys
import urllib.request

import yt_dlp

DEFAULT_REPO = "LoLyeah/suravidl"


def _fetch_latest_release(repo: str) -> dict:
    """Latest release JSON from the GitHub API (token optional for private repos)."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "suravidl-update-check"})
    token = os.environ.get("SURAVIDL_GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def _parse(v: str):
    parts = []
    for chunk in (v or "").lstrip("v").split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_update(current: str, repo: str = DEFAULT_REPO, fetch_fn=None) -> dict:
    """Compare the running version with the latest GitHub release."""
    fetch_fn = fetch_fn or _fetch_latest_release
    try:
        data = fetch_fn(repo)
    except Exception as e:  # noqa: BLE001 - reported, never raised
        return {"current": current, "latest": None,
                "update_available": False, "error": str(e)}
    tag = (data.get("tag_name") or "").strip()
    latest = tag.lstrip("v") or None
    return {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and _parse(latest) > _parse(current)),
        "url": data.get("html_url"),
    }


def self_update() -> dict:
    """Upgrade yt-dlp in this environment; safe to call again anytime."""
    before = yt_dlp.version.__version__
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True, text=True, timeout=600,
        )
        ok = r.returncode == 0
        detail = (r.stdout + r.stderr)[-2000:]
    except Exception as e:  # noqa: BLE001 - surfaced to the client
        ok, detail = False, str(e)
    try:
        import importlib.metadata as md

        after = md.version("yt-dlp")
    except Exception:  # noqa: BLE001
        after = before
    return {"ok": ok, "updated": ok and after != before,
            "before": before, "after": after, "detail": detail}
