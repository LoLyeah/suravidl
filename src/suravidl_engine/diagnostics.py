"""The bug-report bundle (v0.46.0 "the toolbox").

Two weeks of field debugging went through screenshots and guessing. This
module builds the one-paste alternative: versions, the ffmpeg probe
summary, redacted settings, the log tail, and a jobs summary — JSON a
person can drop into a bug report.

Redaction is the whole game, and it happens HERE, engine-side: the UI
never holds the secrets to leak them. Keys whose name is secret-shaped
are replaced wholesale, every string value and every log line passes
through `scrub_secrets` (the same scrubber the error paths use), and a
test plants sentinel secrets in settings, logs and job errors and
asserts none of them appear anywhere in the payload.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys

_SECRET_KEY = re.compile(
    r"(?i)(token|secret|password|passwd|api[_-]?key|cookie|authorization"
    r"|credential|auth)")


def redact_settings(settings: dict) -> dict:
    """Settings with anything secret-shaped replaced. Nested values too."""
    from .auth import scrub_secrets

    def walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if _SECRET_KEY.search(str(k)):
                    out[k] = "***"
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, str):
            return scrub_secrets(node)
        return node

    return walk(dict(settings or {}))


def _probe_flag(exe: str, flag: str, name: str) -> bool | None:
    """One ffmpeg list probe — encoders/decoders. None = could not tell."""
    try:
        proc = subprocess.run([exe, "-hide_banner", flag],
                              capture_output=True, text=True, timeout=15)
        return re.search(rf"^\s*[A-Z.]{{5,6}}\s+{re.escape(name)}\b",
                         proc.stdout or "", re.M) is not None
    except Exception:  # noqa: BLE001 - unknown is said as unknown
        return None


def ffmpeg_summary() -> dict:
    """What the ffmpeg this engine would RUN can actually do.

    The phone build taught the lesson twice: its encoders differ from its
    configure line (mov_text), and its decoders lack webp while reddit
    serves it. A bug report without this block guesses; with it, knows.
    """
    exe = os.environ.get("SURAVIDL_FFMPEG", "").strip() or shutil.which("ffmpeg") or ""
    out: dict = {"path": exe or "(not found)", "version": ""}
    if not exe:
        return out
    try:
        proc = subprocess.run([exe, "-hide_banner", "-version"],
                              capture_output=True, text=True, timeout=15)
        first = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
        out["version"] = first[:160]
    except Exception as e:  # noqa: BLE001
        out["version"] = f"(probe failed: {type(e).__name__})"
    out["can_encode"] = {n: _probe_flag(exe, "-encoders", n)
                         for n in ("mov_text", "aac", "libmp3lame")}
    out["can_decode"] = {n: _probe_flag(exe, "-decoders", n)
                         for n in ("webp", "mjpeg", "png")}
    return out


# scrub_secrets is URL-shaped (`?token=…`); a token can also sit in prose
# ("boom token=abc") — the sentinel test caught exactly that hole, so the
# bundle scrubs a second time with a key=value pattern
_INLINE_SECRET = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key|sig|signature)"
    r"\s*[=:]\s*([^\s&\"'<>|]+)")


def scrub_inline(text: str) -> str:
    from .auth import scrub_secrets
    return _INLINE_SECRET.sub(r"\1=[redacted]", scrub_secrets(str(text)))


def build_payload(*, settings: dict, logs: list, jobs: list) -> dict:
    """The bundle. Everything user-visible in it is scrubbed first."""
    from . import __version__
    from .auth import scrub_secrets

    try:
        import yt_dlp
        yt = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    except Exception:  # noqa: BLE001
        yt = "absent"

    safe_logs = [scrub_inline(line) for line in (logs or [])][-200:]

    counts: dict = {}
    for j in jobs or []:
        st = str(j.get("status") or "?")
        counts[st] = counts.get(st, 0) + 1

    recent = []
    for j in list(jobs or [])[:10]:
        recent.append({
            "status": j.get("status"),
            "title": scrub_inline(str(j.get("title") or j.get("url") or ""))[:120],
            "error": scrub_inline(str(j.get("error") or ""))[:200],
        })

    return {
        "engine": __version__,
        "yt-dlp": yt,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} ({sys.platform})",
        "ffmpeg": ffmpeg_summary(),
        "jobs": {"counts": counts, "recent": recent},
        "settings": redact_settings(settings),
        "logs": safe_logs,
        "note": ("paste this whole block into the bug report — every secret "
                 "was redacted by the engine itself, not by trust"),
    }
