"""Settings -> yt-dlp download options.

yt-dlp's CLI translates flags like --embed-metadata / --embed-thumbnail /
--embed-subs / --sponsorblock-remove into postprocessors; the Python API does
NOT — postprocessors must be listed explicitly. This module mirrors the CLI's
translation (yt_dlp/__init__.py::get_postprocessors) for the options suravidl
exposes, including its ordering rules:

    FFmpegEmbedSubtitle must run before ModifyChapters (subtitles already in
    the container when chapters get cut), ModifyChapters before FFmpegMetadata
    (so chapter metadata reflects the cut), metadata before thumbnail embed.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

SUBTITLE_MODES = ("off", "sidecar", "embed")
SPONSORBLOCK_MODES = ("off", "mark", "remove")
SPONSORBLOCK_CATEGORIES = (
    "sponsor", "intro", "outro", "selfpromo", "preview", "filler",
    "interaction", "music_offtopic",
)
PROXY_SCHEMES = ("http", "https", "socks4", "socks4a", "socks5", "socks5h")

DEFAULT_TEMPLATE = "%(title).100B.%(ext)s"

_RATE_RE = re.compile(r"^\d+(?:\.\d+)?[kKmMgG]?$")
_SUFFIX = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}


def parse_rate_limit(value: str | None) -> int | None:
    """'2M' -> 2097152 bytes per second. None for empty, ValueError for junk."""
    v = (value or "").strip()
    if not v:
        return None
    if not _RATE_RE.match(v):
        raise ValueError("rate_limit must look like 500K, 2M, 1.5M or a plain number")
    mult = _SUFFIX.get(v[-1].lower(), 1)
    num = float(v[:-1]) if v[-1].isalpha() else float(v)
    return int(num * mult)


def parse_langs(value: str | None) -> list[str]:
    return [s.strip() for s in (value or "").replace(";", ",").split(",")
            if s.strip()]


def validate_template(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("filename_template cannot be empty")
    if len(v) > 200:
        raise ValueError("filename_template is too long")
    if any(sep in v for sep in ("/", "\\")) or ".." in v:
        raise ValueError("filename_template must be a plain filename "
                         "(no path separators or '..')")
    if "%(ext)s" not in v:
        raise ValueError("filename_template must contain %(ext)s")
    return v


def validate_proxy(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if any(c.isspace() for c in v):
        raise ValueError("proxy must not contain spaces")
    parsed = urlparse(v)
    if parsed.scheme not in PROXY_SCHEMES or not parsed.hostname:
        raise ValueError(f"proxy must be one of {PROXY_SCHEMES}, "
                         f"e.g. socks5://127.0.0.1:1080")
    return v


def validate_sponsorblock_categories(value: str) -> str:
    cats = parse_langs(value)
    unknown = [c for c in cats if c not in SPONSORBLOCK_CATEGORIES]
    if unknown:
        raise ValueError(f"unknown sponsorblock categories: {unknown} "
                         f"(known: {list(SPONSORBLOCK_CATEGORIES)})")
    return ", ".join(cats)


def build_download_opts(settings: dict, download_dir, archive_path=None) -> dict:
    """yt-dlp options derived from user settings (no per-job overrides here)."""
    opts: dict = {}
    pps: list[dict] = []

    template = settings.get("filename_template") or DEFAULT_TEMPLATE
    outtmpl = str(Path(download_dir) / template)

    # -- subtitles ---------------------------------------------------------
    sub_mode = settings.get("subtitles_mode", "off")
    if sub_mode != "off":
        opts["writesubtitles"] = True
        if settings.get("subtitles_auto"):
            opts["writeautomaticsub"] = True
        langs = parse_langs(settings.get("subtitles_langs")) or ["en"]
        opts["subtitleslangs"] = langs
        if sub_mode == "embed":
            pps.append({"key": "FFmpegEmbedSubtitle",
                        "already_have_subtitle": True})

    # -- sponsorblock (mirrors CLI: SponsorBlock then ModifyChapters) ------
    sb_mode = settings.get("sponsorblock_mode", "off")
    if sb_mode != "off":
        cats = set(parse_langs(settings.get("sponsorblock_categories"))) & \
            set(SPONSORBLOCK_CATEGORIES)
        if cats:
            pps.append({"key": "SponsorBlock", "categories": cats,
                        "when": "after_filter"})
            pps.append({"key": "ModifyChapters",
                        "remove_sponsor_segments":
                            cats if sb_mode == "remove" else set()})

    # -- metadata ----------------------------------------------------------
    if settings.get("embed_metadata"):
        pps.append({"key": "FFmpegMetadata", "add_metadata": True})

    # -- thumbnail ---------------------------------------------------------
    if settings.get("embed_thumbnail"):
        opts["writethumbnail"] = True
        # don't write playlist-level thumbnails (the CLI does the same)
        outtmpl = {"default": outtmpl, "pl_thumbnail": ""}
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": True})

    # -- network -----------------------------------------------------------
    ratelimit = parse_rate_limit(settings.get("rate_limit"))
    if ratelimit:
        opts["ratelimit"] = ratelimit
    fragments = int(settings.get("fragments") or 1)
    if fragments > 1:
        opts["concurrent_fragment_downloads"] = fragments
    proxy = (settings.get("proxy") or "").strip()
    if proxy:
        opts["proxy"] = proxy

    # -- archive -----------------------------------------------------------
    if settings.get("archive") and archive_path:
        opts["download_archive"] = str(archive_path)

    opts["outtmpl"] = outtmpl
    if pps:
        opts["postprocessors"] = pps
    return opts
