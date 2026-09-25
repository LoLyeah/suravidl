"""Per-site memory: the quality you pick for a site, offered again next time.

Stored in the app's settings as `site_quality` — a mapping of site → quality
key, bounded, cleaned on the way in (`Settings._validate`) and never a
per-job override. It is only ever an *offer*: a remembered pick shows up on
the probe response so the UI can mark that chip, and it never changes what a
download uses unless the user clicks it again.
"""
import re
from urllib.parse import urlsplit

from .download_opts import QUALITY_KEYS

# How many sites we keep. A phone user has a handful of favourites; a list
# that grows without end is a settings file nobody wants to read.
MAX_SITES = 50

# A hostname (or an IP): labels of letters/digits/hyphens, dots between them.
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,78}[a-z0-9])?$")


def _norm_host(raw: str) -> str | None:
    """A hostname as we store it: lowercase, no `www.`, no scheme/path/port."""
    value = str(raw or "").strip().lower()
    if "://" in value:
        try:
            value = (urlsplit(value).hostname or "")
        except ValueError:
            return None
    value = value.split("/")[0].split("?")[0].split("#")[0]
    if "@" in value:                      # user:pass@host
        value = value.rsplit("@", 1)[1]
    value = value.split(":")[0]           # a port is not part of the site
    if value.startswith("www."):
        value = value[4:]
    if not value or not _HOST_RE.match(value) or "." not in value:
        # a bare "localhost" is not a site we can recognise either way
        return None
    return value


def host_of(url: str | None) -> str | None:
    """The site a URL belongs to, or None.

    `www.` is a prefix, not a site of its own, so it is dropped; other
    subdomains are kept (`m.youtube.com` is remembered separately). No
    public-suffix list is pulled in: honest, predictable, documented.
    """
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    host = (parts.hostname or "").strip().lower()
    if not host:
        return None
    return _norm_host(host)


def clean(mapping) -> dict:
    """Drop what cannot be a remembered pick; keep insertion order.

    Raises for a non-object (that is a caller bug, not room data). When two
    hosts normalize to the same name the last one wins.
    """
    if not isinstance(mapping, dict):
        raise ValueError("site_quality must be an object of site → quality")
    out: dict[str, str] = {}
    for host, quality in mapping.items():
        name = _norm_host(host)
        key = str(quality or "").strip().lower()
        if name and key in QUALITY_KEYS:
            out.pop(name, None)
            out[name] = key
    while len(out) > MAX_SITES:
        out.pop(next(iter(out)))    # the oldest site goes first
    return out


def record(memory, url: str, fmt: str | None) -> dict | None:
    """The updated memory if this job taught us a preference, else None.

    Only an exact quality-preset expression counts: a format the user typed
    by hand is a one-off, and guessing that it was a preference would be
    inventing intent.
    """
    from .download_opts import QUALITY_BY_FMT

    key = QUALITY_BY_FMT.get((fmt or "").strip())
    host = host_of(url)
    if not key or not host:
        return None
    updated = clean(memory or {})
    updated.pop(host, None)
    updated[host] = key
    while len(updated) > MAX_SITES:
        updated.pop(next(iter(updated)))
    return updated
