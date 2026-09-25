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
IP_VERSIONS = ("auto", "ipv4", "ipv6")
_SOURCE_ADDRESS = {"ipv4": "0.0.0.0", "ipv6": "::"}   # yt-dlp's own mapping
SLEEP_REQUESTS_MAX = 30.0

# One-click quality picks, expressed the way yt-dlp recommends: a capped
# video stream paired with the best audio when the site serves them apart
# (`bv*` + `ba`), falling back to the best single file (`b`). The engine owns
# these strings so every shell gets the same presets — and so a test can prove
# yt-dlp itself accepts each one.
QUALITY_PRESETS = (
    {"key": "best", "label": "Best", "fmt": "bv*+ba/b"},
    {"key": "2160", "label": "2160p", "fmt": "bv*[height<=2160]+ba/b[height<=2160]/b"},
    {"key": "1440", "label": "1440p", "fmt": "bv*[height<=1440]+ba/b[height<=1440]/b"},
    {"key": "1080", "label": "1080p", "fmt": "bv*[height<=1080]+ba/b[height<=1080]/b"},
    {"key": "720", "label": "720p", "fmt": "bv*[height<=720]+ba/b[height<=720]/b"},
    {"key": "480", "label": "480p", "fmt": "bv*[height<=480]+ba/b[height<=480]/b"},
)

QUALITY_KEYS = tuple(p["key"] for p in QUALITY_PRESETS)

# Reverse lookup, so a finished pick can be recognised again ("this job used
# the 720p expression" → "720", the per-site memory and the UI both use it).
QUALITY_BY_FMT = {p["fmt"]: p["key"] for p in QUALITY_PRESETS}

# The curated groups the yt-dlp tab exposes as named controls (as opposed to
# raw arguments). Kept here so the UI, the engine and the tests share one list.
CURATED_KEYS = (
    "verbose",             # verbosity
    "ip_version", "no_check_certificates", "sleep_requests",   # workarounds
    "geo_bypass", "geo_bypass_country",                        # geo
    "extractor_args",                                          # extractor
)

# extractor:key=value[,value][;extractor:key=value…] — yt-dlp's --extractor-args
# syntax, parsed here so nothing ever reaches a shell.
_EXTRACTOR_ARG_RE = re.compile(
    r"^([A-Za-z0-9_.-]+):([A-Za-z0-9_-]+)=([^=;:]+(?:,[^=;:]+)*)$")


def parse_extractor_args(value: str | None) -> dict:
    """'youtube:player_client=web_safari,ios' ->
    {'youtube': {'player_client': ['web_safari', 'ios']}}

    Same shape yt-dlp's own --extractor-args produces (asserted against its
    CLI in tests/test_curated.py). Values must be literal: anything that
    doesn't match `extractor:key=value,values` is refused instead of guessed at.
    """
    text = str(value or "").strip()
    if not text:
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _EXTRACTOR_ARG_RE.match(chunk)
        if not m:
            raise ValueError(
                "extractor_args must look like 'extractor:key=value' "
                f"(got {chunk!r})")
        extractor, key, values = m.group(1), m.group(2), m.group(3)
        parsed = [v.strip() for v in values.split(",") if v.strip()]
        if not parsed:
            raise ValueError(f"extractor_args value is empty in {chunk!r}")
        out.setdefault(extractor, {})[key] = parsed
    return out


def curated_settings_opts(settings: dict) -> dict:
    """The curated groups as yt-dlp options (no defaults: inert when unused)."""
    opts: dict = {}
    if settings.get("verbose"):
        opts["verbose"] = True
        opts["quiet"] = False
        opts["no_warnings"] = False
    ip_version = settings.get("ip_version", "auto")
    if ip_version in _SOURCE_ADDRESS:
        opts["source_address"] = _SOURCE_ADDRESS[ip_version]
    if settings.get("no_check_certificates"):
        opts["nocheckcertificate"] = True
    try:
        sleep_requests = float(settings.get("sleep_requests") or 0)
    except (TypeError, ValueError):
        sleep_requests = 0.0
    if sleep_requests > 0:
        opts["sleep_interval_requests"] = sleep_requests
    if settings.get("geo_bypass"):
        opts["geo_bypass"] = True
    country = str(settings.get("geo_bypass_country") or "").strip().upper()
    if len(country) == 2 and country.isalpha():
        opts["geo_bypass_country"] = country
    # retries / how much of a playlist to take: inert at the yt-dlp defaults
    try:
        retries = int(settings.get("retries", 10))
    except (TypeError, ValueError):
        retries = 10
    if retries != 10:
        opts["retries"] = retries
    try:
        max_downloads = int(settings.get("max_downloads", 0) or 0)
    except (TypeError, ValueError):
        max_downloads = 0
    if max_downloads > 0:
        opts["max_downloads"] = max_downloads
    extractor_args = parse_extractor_args(settings.get("extractor_args"))
    if extractor_args:
        opts["extractor_args"] = extractor_args
    return opts


def probe_extra_opts(settings: dict) -> dict:
    """Which curated options a *probe* may honour.

    Network/geo only: a region-locked or IPv6-broken video can then at least
    be listed, while nothing download-shaped leaks into an extraction.
    """
    curated = curated_settings_opts(settings)
    allowed = ("geo_bypass", "geo_bypass_country", "source_address",
               "nocheckcertificate", "extractor_args")
    out = {k: curated[k] for k in allowed if k in curated}
    proxy = str(settings.get("proxy") or "").strip()
    if proxy:
        out["proxy"] = proxy
    return out

# Raw arguments (Advanced tier) may not touch flags the engine owns, nor
# anything that runs programs or abandons the job model. Checked twice:
# a pre-scan (some flags break the parse itself — --batch-file reads files,
# --exec is translated into a postprocessor and never shows up as a key)
# and a post-parse diff (indirect effects, e.g. --dump-json implies
# simulate). Maps flag/key -> why it is refused.
DENIED_RAW_FLAGS: dict[str, str] = {
    "--exec": "runs programs",
    "--exec-before-download": "runs programs",
    "--external-downloader": "runs external programs",
    "--downloader": "runs external programs",
    "--ffmpeg-location": "the app manages ffmpeg",
    "--batch-file": "the engine owns the job list",
    # the output path is the app's decision: `-o/-P` would write anywhere
    # the user can write (v0.21.2 audit)
    "-o": "the app decides where downloads go",
    "--output": "the app decides where downloads go",
    "-P": "the app decides where downloads go",
    "--paths": "the app decides where downloads go",
    "--config-locations": "config files are app-managed",
    "--plugin-dirs": "plugins run code",
    "--load-info-json": "the engine owns the job model",
    "--simulate": "nothing would be downloaded",
    "--skip-download": "nothing would be downloaded",
    "--dump-json": "implies --simulate",
    "--dump-single-json": "implies --simulate",
    "--download-archive": "the archive is a settings feature",
    "--cookies": "auth lives in Settings → Authentication",
    "--cookies-from-browser": "auth lives in Settings → Authentication",
    "--flat-playlist": "playlists are a first-class feature",
    "--playlist-items": "playlists are a first-class feature",
    "--no-playlist": "playlists are a first-class feature",
    "--yes-playlist": "playlists are a first-class feature",
}

DENIED_RAW_KEYS: dict[str, str] = {
    "exec_cmd": "--exec",
    "outtmpl": "-o",
    "paths": "-P",
    "exec_before_dl_cmd": "--exec-before-download",
    "external_downloader": "--external-downloader",
    "ffmpeg_location": "--ffmpeg-location",
    "batchfile": "--batch-file",
    "batchurls": "--batch-file",
    "config_locations": "--config-locations",
    "plugin_dirs": "--plugin-dirs",
    "load_info_json": "--load-info-json",
    "simulate": "--simulate",
    "skip_download": "--skip-download",
    "download_archive": "--download-archive",
    "cookiefile": "--cookies",
    "cookiesfrombrowser": "--cookies-from-browser",
    "extract_flat": "--flat-playlist",
    "playlist_items": "--playlist-items",
    "noplaylist": "--no-playlist",
    "progress_hooks": "internal hooks",
    "postprocessor_hooks": "internal hooks",
}

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


_BASELINE_OPTS: dict | None = None


def _same(a, b) -> bool:
    """Structural equality; opaque objects (DateRange etc.) compare by str()."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, (str, int, float, bool, type(None))):
        return a == b
    return str(a) == str(b)


def _baseline_opts() -> dict:
    """The full option dump yt-dlp produces for an EMPTY argument list."""
    global _BASELINE_OPTS
    if _BASELINE_OPTS is None:
        import yt_dlp

        _BASELINE_OPTS = yt_dlp.parse_options([]).ydl_opts
    return _BASELINE_OPTS


def parse_raw_args(raw: str | None) -> dict:
    """Parse a raw yt-dlp argument string into YoutubeDL options.

    Uses yt-dlp's own parser (shlex-split, never a shell). The parser returns
    a FULL option dump with every default filled in; merging that wholesale
    would silently clobber the engine's choices, so only options the
    arguments actually changed (versus an empty argv) are kept. Flags the
    engine owns are refused with ValueError naming them.
    """
    import shlex
    from optparse import OptParseError

    import yt_dlp

    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        argv = shlex.split(raw)
    except ValueError as e:
        raise ValueError(f"could not parse raw arguments: {e}") from e

    banned = sorted({f.split("=", 1)[0] for f in argv
                     if f.split("=", 1)[0] in DENIED_RAW_FLAGS})
    if banned:
        reasons = "; ".join(f"{f} ({DENIED_RAW_FLAGS[f]})" for f in banned)
        raise ValueError(f"these arguments are not allowed: {reasons}")

    try:
        parsed = yt_dlp.parse_options(argv).ydl_opts
    except (OptParseError, SystemExit) as e:
        text = str(e).strip()
        msg = text.splitlines()[-1].strip() if text else "invalid arguments"
        raise ValueError(f"yt-dlp rejected those arguments: {msg}") from e

    baseline = _baseline_opts()
    opts: dict = {}
    for key, value in parsed.items():
        if _same(value, baseline.get(key)):
            continue  # untouched default
        if key in DENIED_RAW_KEYS:
            flag = DENIED_RAW_KEYS[key]
            raise ValueError(f"these arguments are not allowed: {flag}")
        opts[key] = value
    return opts


def build_download_opts(settings: dict, download_dir, archive_path=None,
                        raw_args: str | None = None) -> dict:
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

    # -- curated groups (verbosity · workarounds · geo · extractor args) ---
    opts.update(curated_settings_opts(settings))

    opts["outtmpl"] = outtmpl
    if pps:
        opts["postprocessors"] = pps

    # -- raw arguments (Advanced tier, default-OFF) ------------------------
    # Applied last: a power user's explicit flags win over the settings they
    # overlap with (job-level format/preset still override afterwards).
    if raw_args is None and settings.get("raw_args_enabled"):
        raw_args = settings.get("raw_args") or ""
    if raw_args:
        extra = parse_raw_args(raw_args)
        extra_pps = extra.pop("postprocessors", None)
        opts.update(extra)
        if extra_pps:
            opts["postprocessors"] = list(opts.get("postprocessors") or []) + \
                list(extra_pps)
    return opts
