"""Metadata probe via yt-dlp as a module."""
import yt_dlp


def probe(url: str, extra_headers: dict | None = None) -> dict:
    """Extract metadata (incl. formats) without downloading."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if extra_headers:
        opts["http_headers"] = extra_headers
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.sanitize_info(ydl.extract_info(url, download=False))
