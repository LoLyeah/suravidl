"""What is this URL? One judgement, in the engine, for every shell.

Each shell's sniffer (the Android browser, the extension, the web UI) collects
candidate URLs while the user watches. None of those candidates can say what
they are — an ad creative is an .mp4 too, a page is not a video, and only a
real round trip, with the caller's own cookies, can tell them apart. So the
judgement lives here, once, and every shell shows the answer instead of a
naked URL.

The media pattern list is canonical here too (`GET /sniff/patterns`): shells
prefilter with it, the engine classifies what survives. A prefilter decides
what gets *looked at*; it never decides what gets *shown*.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlsplit

TIMEOUT = 10
PEEK_BYTES = 4096

# A sniffed URL usually arrives with the *browser's* own User-Agent attached by
# the caller; when nobody attached one, urllib's default ("Python-urllib/…") is
# bot-blocked on sight, so ask like a browser instead.
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")
HEADER_DEFAULTS = {"User-Agent": DEFAULT_UA, "Accept": "*/*"}

# A local tool may reach the LAN — a NAS is a fine place to keep films — and
# loopback, which is where the engine lives. Link-local is different: that is
# where cloud metadata services sit, and a page that smuggles a URL into the
# pipeline must not be able to make the engine poke one. Host *literals* only:
# guessing at DNS would break the LAN case for no real gain.
BLOCKED_HOSTS = ("metadata.google.internal", "metadata.goog")
BLOCKED_PREFIXES = ("169.254.", "fd00:ec2")


def blocked_reason(url: str) -> str:
    """Why this URL must not be fetched, or '' when it is fine to fetch."""
    host = (urlsplit(url).hostname or "").lower().strip("[]")
    if not host:
        return ""
    if host in BLOCKED_HOSTS:
        return "cloud metadata address"
    if host.startswith(BLOCKED_PREFIXES):
        return "link-local address"
    return ""

# The canonical prefilter list. The extension fetches it (with a baked-in
# fallback for when the engine is not answering yet); a test keeps that fallback
# a subset of this one, so a shell can only ever look at *fewer* URLs than the
# engine can name.
MEDIA_EXT = ("mp4", "m4v", "webm", "mov", "mkv", "avi", "flv", "wmv", "ogv",
             "m3u8", "mpd", "ts", "m4s",
             "mp3", "m4a", "aac", "ogg", "opus", "wav", "flac")
VIDEO_EXT = ("mp4", "m4v", "webm", "mov", "mkv", "avi", "flv", "wmv", "ogv")
AUDIO_EXT = ("mp3", "m4a", "aac", "ogg", "opus", "wav", "flac")
SEGMENT_EXT = ("ts", "m4s")
# Streams with no extension at all still tend to look like this.
URL_HINTS = ("manifest", "playlist", "master.m3u8", "/hls/", "/dash/",
             "videoplayback", "format=m3u8", "type=m3u8")

DRM_SCHEMES = {
    "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed": "widevine",
    "9a04f079-9840-4286-ab92-e65be0885f95": "playready",
    "e2719d58-a985-b3c9-781a-b030af78d30e": "clearkey",
}
MIME_KINDS = {
    "application/vnd.apple.mpegurl": "hls",
    "application/x-mpegurl": "hls",
    "audio/mpegurl": "hls",
    "application/dash+xml": "dash",
    "text/html": "page",
    "application/xhtml+xml": "page",
}


def media_regex() -> re.Pattern:
    return re.compile(r"\.(" + "|".join(MEDIA_EXT) + r")(\?|$)", re.I)


def patterns() -> dict:
    """The one media-pattern list, ready for a shell to bake in or fetch."""
    return {"ext": list(MEDIA_EXT), "hints": list(URL_HINTS),
            "regex": media_regex().pattern}


@dataclass
class Response:
    """What one fetch learned — enough to classify, never the whole file."""

    status: int = 0
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    final_url: str = ""
    error: str = ""

    def ok(self) -> bool:
        return 200 <= self.status < 400


def _headers_with_defaults(headers: dict | None) -> dict:
    """Defaults first, the caller's headers on top — case-insensitively.

    urllib happily sends `User-Agent` and `user-agent` as two headers if the
    caller gives the second spelling, so the default is dropped by name.
    """
    out = dict(HEADER_DEFAULTS)
    for key in (headers or {}):
        for existing in list(out):
            if existing.lower() == key.lower():
                out.pop(existing)
    out.update(headers or {})
    return out


def _why(error: str, status: int) -> str:
    """A refusal is worth explaining: it usually means 'bring the cookies'."""
    base = error or (f"http {status}" if status else "fetch failed")
    if status in (401, 403, 429):
        return f"{base} — the site refused the request (it may need the browser's cookies)"
    return base


def _http_fetch(url, headers=None, method="GET", range_bytes=None) -> Response:
    """The real fetch: stdlib only, bounded, never reads a whole file."""
    req = urlrequest.Request(url, method=method)
    for key, value in _headers_with_defaults(headers).items():
        req.add_header(key, value)
    if range_bytes:
        req.add_header("Range", f"bytes=0-{range_bytes - 1}")
    try:
        with urlrequest.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(range_bytes) if method == "GET" else b""
            return Response(status=getattr(r, "status", 200) or 200,
                            headers=dict(r.headers), body=body,
                            final_url=r.geturl() or url)
    except urlerror.HTTPError as e:
        return Response(status=e.code, headers=dict(e.headers or {}),
                        final_url=url, error=f"http {e.code}")
    except (urlerror.URLError, OSError, ValueError) as e:
        return Response(status=0, final_url=url, error=str(e) or "fetch failed")


def _mime(headers: dict) -> str:
    for key, value in (headers or {}).items():
        if key.lower() == "content-type":
            return str(value).split(";")[0].strip().lower()
    return ""


def _size(headers: dict) -> int | None:
    for key, value in (headers or {}).items():
        if key.lower() == "content-length":
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _range_total(headers: dict) -> int | None:
    """A 206 knows the whole file's size even though we only peeked."""
    for key, value in (headers or {}).items():
        if key.lower() == "content-range" and "/" in str(value):
            tail = str(value).rsplit("/", 1)[1].strip()
            if tail.isdigit():
                return int(tail)
    return None


def kind_from_mime(mime: str) -> str:
    mime = (mime or "").strip().lower()
    if mime in MIME_KINDS:
        return MIME_KINDS[mime]
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("image/"):
        return "image"
    return ""


def kind_from_body(body: bytes) -> str:
    """Mimes lie. The first bytes do not."""
    head = body[:1024].lstrip()
    if body[:7] == b"#EXTM3U" or b"#EXTM3U" in body[:64]:
        return "hls"
    if head.startswith(b"<") and b"<MPD" in body[:4096]:
        return "dash"
    low = body[:512].lower()
    if head.lower().startswith((b"<!doctype html", b"<html")) or b"<html" in low:
        return "page"
    if len(body) >= 12 and body[4:8] == b"ftyp":
        return "video"
    if body[:4] == b"\x1a\x45\xdf\xa3":
        return "video"                     # matroska / webm
    if body[:3] == b"ID3" or body[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "audio"
    if body[:3] == b"\xff\xd8\xff" or body[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"
    return ""


def kind_from_url(url: str) -> str:
    last = urlsplit(url).path.rsplit("/", 1)[-1].lower()
    if "." not in last:
        return ""
    ext = last.rsplit(".", 1)[-1]
    if ext == "m3u8":
        return "hls"
    if ext == "mpd":
        return "dash"
    if ext in VIDEO_EXT or ext in SEGMENT_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    return ""


def _drm_in(body: bytes, kind: str) -> tuple[bool, str]:
    """Encrypted is not the same as locked.

    HLS with an ordinary `METHOD=AES-128` key is downloadable — yt-dlp fetches
    the key with our cookies. `METHOD=SAMPLE-AES`, `skd://` and DASH
    `<ContentProtection>` are the real lock, and the honest answer there is no.
    """
    text = body[:16384].decode("utf-8", "ignore")
    low = text.lower()
    if kind == "hls":
        for line in text.splitlines():
            upper = line.upper()
            if not (upper.startswith("#EXT-X-KEY") or upper.startswith("#EXT-X-SESSION-KEY")):
                continue
            if "METHOD=SAMPLE-AES" in upper:
                return True, "sample-aes"
            if "SKD://" in upper or "WIDEVINE" in upper or "URN:UUID:" in upper:
                return True, "key-delivery"
            # FairPlay usually arrives as SAMPLE-AES (caught above), but a playlist
            # can name the key system with an ordinary METHOD — and the docs
            # promise FairPlay is detected, so the KEYFORMAT decides, not luck.
            if "STREAMINGKEYDELIVERY" in upper or "FAIRPLAY" in upper:
                return True, "key-delivery"
        return False, ""
    if kind == "dash":
        for scheme, name in DRM_SCHEMES.items():
            if scheme in low:
                return True, name
        if "<contentprotection" in low:
            return True, "content-protection"
        return False, ""
    return False, ""


def _unknown(url: str, final: str, note: str) -> dict:
    return {"kind": "unknown", "mime": None, "size": None,
            "final_url": final or url, "drm": False, "note": note}


def classify(url: str, headers: dict | None = None, fetch=None) -> dict:
    """Name what a URL is: kind, mime, size, DRM — never the whole file.

    `fetch(url, headers, method, range_bytes) -> Response` is injectable so the
    tests can drive every branch offline, and so a shell could bring its own
    session one day.
    """
    scheme = (urlsplit(url).scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"classify needs an http(s) url, got {scheme or 'none'!r}")
    why = blocked_reason(url)
    if why:
        return _unknown(url, url, f"{why} — not fetched")
    fetch = fetch or _http_fetch

    head = fetch(url, headers, "HEAD", None)
    final = head.final_url or url
    mime = _mime(head.headers)
    size = _size(head.headers)
    body, kind = b"", ""
    if head.ok():
        kind = kind_from_mime(mime)
    if not head.ok() or not kind or kind in ("hls", "dash"):
        # HLS/DASH carry their DRM decision in the first bytes, so peek either
        # way; for everything else the peek is the fallback when HEAD refused
        got = fetch(url, headers, "GET", PEEK_BYTES)
        if got.ok():
            body = got.body or b""
            mime = _mime(got.headers) or mime
            size = (_size(got.headers) if got.status == 200
                    else _range_total(got.headers)) or size
            final = got.final_url or final
            kind = kind or kind_from_mime(mime) or kind_from_body(body)
        elif not kind:
            return _unknown(url, final,
                            _why(got.error or head.error, got.status or head.status))

    kind = kind or kind_from_url(url)
    if not kind:
        return _unknown(url, final, "no media signals")

    note = ""
    if kind in ("hls", "dash"):
        drm, system = _drm_in(body, kind)
        if drm:
            note = f"{system} protection"
            kind = "drm"
    if kind == "video" and kind_from_url(url) == "video":
        last = urlsplit(url).path.rsplit("/", 1)[-1].lower()
        if "." in last and last.rsplit(".", 1)[-1] in SEGMENT_EXT:
            note = "stream segment — the manifest is the better pick"
    return {"kind": kind, "mime": mime or None, "size": size,
            "final_url": final, "drm": kind == "drm", "note": note}


# -- which of these should a shell *show*? (M4) -----------------------------

def _ext_of(url: str) -> str:
    last = urlsplit(url).path.rsplit("/", 1)[-1].lower()
    return last.rsplit(".", 1)[-1] if "." in last else ""


def _is_manifest(url: str) -> bool:
    """A playlist or a DASH manifest.

    By extension, or by a hint in the *path* — a `.ts`/`.m4s` URL is never a
    manifest, even under `/hls/`, and a query string is not a name: an honest
    `.mp4?origin=playlist` is a video, not a playlist. (The shells' *prefilter*
    still reads the whole URL — a hit there only costs one /classify call. Here
    it decides what is hidden and how a row is labelled, so it has to be exact.)
    """
    ext = _ext_of(url)
    if ext in SEGMENT_EXT:
        return False
    if ext in ("m3u8", "mpd"):
        return True
    path = urlsplit(url).path.lower()
    return any(h in path for h in ("manifest", "master.m3u8", "playlist"))


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def rank(urls: list) -> dict:
    """Hide what is not a stream: fragments whose playlist was also seen.

    A manifest and the fragments it names are *one* stream, and a lone fragment
    is not a download anyone wants. So a `.ts`/`.m4s` URL is hidden whenever a
    manifest from the same origin is in the same list — and told *why*, so a
    shell can say "3 fragments hidden" instead of making rows vanish.

    Same origin, not same folder: an ad's segment list is usually served from
    the same host as the real stream's, and hiding one fragment costs nothing
    while showing forty of them costs the user everything.

    When two manifests share an origin, a fragment is attributed to the one it
    actually sits next to (longest common path prefix) — the reason should name
    a playlist the user can find, not whichever was seen last.
    """
    manifests = [u for u in urls if _is_manifest(u)]
    items = []
    for u in urls:
        if _is_manifest(u):
            items.append({"url": u, "kind": "manifest", "hidden": False, "reason": ""})
        elif _ext_of(u) in SEGMENT_EXT:
            path = urlsplit(u).path
            here = [m for m in manifests if _origin_of(m) == _origin_of(u)]
            best = max(here, key=lambda m: _common_prefix_len(urlsplit(m).path, path),
                       default="")
            if best:
                items.append({"url": u, "kind": "segment", "hidden": True,
                              "reason": "part of " + best.rsplit("/", 1)[-1].split("?")[0]})
            else:
                items.append({"url": u, "kind": "segment", "hidden": False,
                              "reason": "no playlist seen for this fragment"})
        else:
            items.append({"url": u, "kind": "media", "hidden": False, "reason": ""})
    return {"items": items, "hidden": sum(1 for i in items if i["hidden"])}
