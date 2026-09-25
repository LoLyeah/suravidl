"""Metadata probe via yt-dlp as a module."""
from __future__ import annotations

import yt_dlp

MAX_ENTRIES = 100


def probe(url: str, extra_headers: dict | None = None,
          cookie_opts: dict | None = None) -> dict:
    """Extract metadata (incl. formats) without downloading.

    Playlist URLs return a compact summary with flat entries (fast, no
    per-video extraction); single videos keep the full info dict.
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
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False)) or {}

    if info.get("_type") == "playlist" or info.get("entries"):
        entries = [e for e in (info.get("entries") or []) if e]
        return {
            "playlist": True,
            "title": info.get("title"),
            "extractor": info.get("extractor"),
            "count": info.get("playlist_count") or len(entries),
            "entries": [
                {
                    "id": e.get("id"),
                    "title": e.get("title"),
                    "url": e.get("url") or e.get("webpage_url"),
                    "duration": e.get("duration"),
                }
                for e in entries[:MAX_ENTRIES]
            ],
        }

    out = dict(info)
    out["playlist"] = False
    return out
