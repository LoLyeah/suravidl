"""yt-dlp self-update via pip (venv/pip installs; frozen builds use their own)."""
import subprocess
import sys

import yt_dlp


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
