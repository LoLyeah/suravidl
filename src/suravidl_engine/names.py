"""File names a person can live with (v0.49.12 "the handle").

Two different problems, one place:

  * a title that is simply long — the preset truncates it, by grapheme cluster
    and in UTF-8 bytes, so no CJK character and no emoji is cut in half;
  * a title that is not a title at all — some sites hand back an opaque token
    (`AQNenhI7M4vPbmsy…`), which lands in the file manager as a wall of
    letters. It is detected and replaced with who + when, while `[id]` still
    keeps the file unique.

Gemini 4 Carbon's constraints, 2026-11-12, implemented as stated: NFC rather
than NFKC (NFKC rewrites CJK compatibility characters and superscripts),
collapse whitespace, drop format/bidi characters (a right-to-left override in
a name can spoof an extension), keep `[id]`, and only call a title opaque when
it is ASCII-only, space-free, at least 24 characters, holds letters AND digits,
and carries high entropy — so space-free Thai, CJK or emoji titles are never
mistaken for a token.
"""
from __future__ import annotations

import math
import re
import unicodedata

# A title's share of the file name, in UTF-8 bytes. Carbon's budget: ~100 for
# the title and ~24 for the id, leaving headroom under the 255-byte component
# limit and Windows' 260-character path.
TITLE_LIMITS = {"short": 60, "standard": 100, "long": 180, "none": 0}
DEFAULT_LIMIT_KEY = "standard"

_ASCII_TOKEN = re.compile(r"[A-Za-z0-9_-]+")
_ZWJ = "\u200d"
_VARIATION = range(0xFE00, 0xFE10)
_SKIN = range(0x1F3FB, 0x1F400)


def limit_for(settings: dict) -> int:
    key = str((settings or {}).get("filename_length") or DEFAULT_LIMIT_KEY)
    return TITLE_LIMITS.get(key, TITLE_LIMITS[DEFAULT_LIMIT_KEY])


def template_for(settings: dict) -> str:
    """The default template, with the chosen title budget baked in."""
    limit = limit_for(settings)
    title = f"%(title).{limit}B" if limit else "%(title)s"
    return f"{title} [%(id)s].%(ext)s"


def clusters(text: str) -> list[str]:
    """Split into extended grapheme clusters, near enough for a file name.

    A combining mark, a variation selector, a skin-tone modifier, or a
    character right after a ZWJ belongs to the cluster before it — cutting
    between them is what leaves a broken emoji or a detached accent.
    """
    out: list[str] = []
    join_next = False
    for ch in text:
        joined = (join_next or unicodedata.combining(ch)
                  or ch == _ZWJ or ord(ch) in _VARIATION or ord(ch) in _SKIN)
        if out and joined:
            out[-1] += ch
        else:
            out.append(ch)
        join_next = ch == _ZWJ
    return out


def _keep(ch: str) -> bool:
    """Drop controls and format characters, but keep the ones emoji need.

    A ZWJ is a format character and `str.isprintable()` says no to it, yet
    dropping it turns one family emoji into four unrelated people — the
    joiner and the variation selectors are part of the picture (v0.49.12).
    Bidi overrides are format characters with no such excuse: a right-to-left
    override can make a .mp4 read as a .jpg.
    """
    if ch == _ZWJ or 0xFE00 <= ord(ch) <= 0xFE0F:
        return True
    return unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn")


def clean_title(raw: object, limit: int) -> str:
    """NFC, one line, no control or bidi marks, then cut at a cluster edge."""
    text = unicodedata.normalize("NFC", str(raw or ""))
    text = "".join(ch for ch in text if _keep(ch))
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .")
    if not text:
        return ""
    if not limit:
        return text
    kept: list[str] = []
    used = 0
    for cluster in clusters(text):
        size = len(cluster.encode("utf-8"))
        if used + size > limit:
            break
        kept.append(cluster)
        used += size
    return "".join(kept).strip(" .")


def entropy(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def looks_opaque(title: str, video_id: str = "") -> bool:
    """True for a token wearing a title's clothes, never for a real title."""
    text = (title or "").strip()
    if not text:
        return False
    if video_id and text == video_id.strip():
        # "tiny [tiny]" is a file name, not a token: an id-shaped title only
        # counts when it is long enough to be one
        return len(text) >= 16 and bool(_ASCII_TOKEN.fullmatch(text))
    if len(text) < 24:
        return False
    if not _ASCII_TOKEN.fullmatch(text):
        return False
    if not any(c.isdigit() for c in text) or not any(c.isalpha() for c in text):
        return False
    return entropy(text) > 4.0


def fallback_title(info: dict, limit: int) -> str:
    """Who and when: readable in a list, sortable, and honest about its origin."""
    who = (info.get("uploader") or info.get("channel")
           or info.get("uploader_id") or info.get("extractor_key") or "")
    date = str(info.get("upload_date") or "")
    if len(date) == 8 and date.isdigit():
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    else:
        date = ""
    parts = [clean_title(who, 40), date]
    return clean_title(" - ".join(p for p in parts if p) or "video", limit)


def title_filter(limit: int):
    """A yt-dlp match_filter that rewrites the title before the name is built.

    yt-dlp calls match_filter before it prepares the filename, and the same
    dict is used afterwards, so this is the seam where a name can be fixed
    without a post-download rename (Carbon, 2026-11-12).
    """

    def _filter(info_dict, *, incomplete=False):
        if incomplete:
            return None
        title = str(info_dict.get("title") or "")
        if looks_opaque(title, str(info_dict.get("id") or "")):
            info_dict["title"] = fallback_title(info_dict, limit)
        else:
            info_dict["title"] = clean_title(title, limit)
        return None

    return _filter
