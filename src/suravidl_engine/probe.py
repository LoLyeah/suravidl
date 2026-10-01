"""Metadata probe via yt-dlp as a module."""
from __future__ import annotations

import yt_dlp  # tests monkeypatch probe.yt_dlp.YoutubeDL — keep the name

from .extract import extract_info

MAX_ENTRIES = 500


# yt-dlp preserves the request shape it used inside the payload it returns:
# `http_headers` at the top and `cookies` on every format entry. Probe
# answers are read by shells (the web UI, browser handoffs), so the captures
# must not ride back out — they stay engine-side, for the job that reuses
# them.
SENSITIVE_INFO_KEYS = ("http_headers", "cookies")


def scrub_secrets(value):
    """Strip the capture keys from a probe payload, at any depth. Idempotent."""
    if isinstance(value, dict):
        return {k: scrub_secrets(v) for k, v in value.items()
                if k not in SENSITIVE_INFO_KEYS}
    if isinstance(value, list):
        return [scrub_secrets(v) for v in value]
    return value


PROTECTED_PROBE_KEYS = (
    "skip_download", "paths", "outtmpl", "noplaylist", "extract_flat",
    "playlistend", "quiet", "no_warnings", "download", "download_archive",
    "postprocessors", "writethumbnail", "writesubtitles", "writeautomaticsub",
    "progress_hooks", "postprocessor_hooks", "format", "playlist_items",
)


def probe(url: str, extra_headers: dict | None = None,
          cookie_opts: dict | None = None,
          extra_opts: dict | None = None) -> dict:
    """Extract metadata (incl. formats) without downloading.

    Playlist URLs return a compact summary with flat entries (fast, no
    per-video extraction); single videos keep the full info dict.

    extra_opts may carry network/geo preferences (proxy, geo_bypass, …) but
    can never redefine what a probe is: engine-owned keys are dropped.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": False,
        "extract_flat": "in_playlist",  # playlist entries stay flat
        "playlistend": MAX_ENTRIES,
    }
    if extra_headers:
        opts["http_headers"] = extra_headers
    if cookie_opts:
        opts.update(cookie_opts)
    for key, value in (extra_opts or {}).items():
        if key in PROTECTED_PROBE_KEYS:
            continue
        opts[key] = value
    info = extract_info(opts, url, download=False) or {}

    if info.get("_type") == "playlist" or info.get("entries"):
        entries = [e for e in (info.get("entries") or []) if e]
        return scrub_secrets({
            "playlist": True,
            "title": info.get("title"),
            "extractor": info.get("extractor"),
            "count": info.get("playlist_count") or len(entries),
            "entries": [
                {
                    # 1-based, in playlist order: the number the pick list
                    # writes into playlist_items
                    "index": i + 1,
                    "id": e.get("id"),
                    "title": e.get("title"),
                    "url": e.get("url") or e.get("webpage_url"),
                    "duration": e.get("duration"),
                }
                for i, e in enumerate(entries[:MAX_ENTRIES])
            ],
        })

    out = dict(info)
    out["playlist"] = False
    return scrub_secrets(out)
