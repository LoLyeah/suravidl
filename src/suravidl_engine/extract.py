"""One extraction call for the whole engine, with the two refusals that are
worth a second attempt handled in ONE place.

TikTok's web front refuses a fraction of fetches from any given network
("Unexpected response from webpage request" — the challenge page never
arrives); yt-dlp's own tracker treats it as intermittent: "roughly a third
of requests fail ... the same videos download fine individually, and that's
what the repeated passes are for" (yt-dlp/yt-dlp#17604). Two more attempts
turn that refusal into a non-event — and they step aside from the exact
request that was refused: a refusal is per-fingerprint, so three identical
requests earn three identical answers. Each retry wears a different user
agent (the served-when-different workaround the tracker documents).

The second: signed CDN links rotate mid-transfer. A download that dies on an
HTTP 403/410 *after bytes had arrived* was not refused — its link expired
while it ran. cobalt calls the cure a transplant (it rewrites the running
stream); here it falls out of re-running the extraction: yt-dlp's own
`continuedl` resumes the `.part` from where it stopped, with a fresh URL
under it. The transplant is offered once, and only when bytes actually
arrived — a 403 before any progress is the site's answer, and is passed
through untouched.

Third: covers that arrive without a usable name. TikTok serves cover
images from URLs that end in `.image` — the file lands as `<title>.image`
while its bytes are a plain JPEG. When the thumbnail is embedded, yt-dlp
reads that name, decides it cannot be jpg/jpeg/png, and converts — and the
conversion hands ffmpeg an extensionless name no build can map to a codec
("Error opening output files: Invalid argument", seen on Android first,
2026-10-05; the desktop failed identically). The file's bytes know what it
is, so the name is corrected before any reader runs.

Every other error raises on the spot — a retry must never paper over a real
answer.
"""
from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import yt_dlp

from .download_opts import tiktok_safe_format

TIKTOK_FLAKE_PHRASES = (
    # the webpage came back with neither challenge nor hydration data
    "unexpected response from webpage request",
    # the challenge page arrived but its payload could not be read / solved
    "unable to extract challenge data",
    "unable to solve js challenge",
    # challenge solved, but the second fetch still carried no hydration data
    "unable to extract universal data for rehydration",
)

REFRESH_PHRASES = (
    "http error 403",   # the signature rotated mid-transfer
    "http error 410",   # the link is gone
    "expired",
    "signature",
)

ATTEMPTS = 3
BACKOFF = (0.8, 2.0)
REFRESH_PAUSE = 0.5

# The faces the TikTok retries wear. Attempt one is exactly what the caller
# asked for; a refusal is per-fingerprint (the same request earns the same
# answer), so the retries step aside from it the way the community does —
# a user agent that does not match the impersonated browser is served where
# the newest Chrome profile is turned away (yt-dlp/yt-dlp#17604).
RETRY_USER_AGENTS = (
    None,   # attempt 1: the caller's own options, untouched
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 OPR/118.0.0.0",
)


def _with_user_agent(opts: dict, ua: str) -> dict:
    """A copy of opts whose request wears the given User-Agent."""
    headers = dict(opts.get("http_headers") or {})
    headers["User-Agent"] = ua
    return {**opts, "http_headers": headers}


def is_tiktok_flake(error: object) -> bool:
    """Is this failure TikTok's intermittent refusal (safe to retry)?"""
    text = str(error).lower()
    return any(phrase in text for phrase in TIKTOK_FLAKE_PHRASES)


def is_expired_link(error: object) -> bool:
    """Did a download die on a link that expired while it ran?"""
    text = str(error).lower()
    return any(phrase in text for phrase in REFRESH_PHRASES)


def _watching_progress(opts: dict, seen: dict) -> dict:
    """opts with a progress note chained in front of the caller's hooks.

    The note is how the transplant knows bytes had arrived; the caller's hooks
    keep their order, their events, and their right to raise (a cancel still
    cancels). The caller's dict is copied, never mutated.
    """
    hooks = list(opts.get("progress_hooks") or [])

    def note(d):
        if (d.get("status") in ("downloading", "finished")
                and (d.get("downloaded_bytes") or 0) > 0):
            seen["bytes"] = True
        for h in hooks:
            h(d)

    return {**opts, "progress_hooks": [note]}


# ---- covers that arrive without a usable name (v0.45.6) --------------------
#
# The file's first bytes claim its type; the name is made to agree before
# any reader runs. yt-dlp itself corrects a wrong *webp* extension inside
# the embedder (#25687) — but only webp, and only after it has already read
# the name once. This runs earlier and wider: any unusable extension
# (missing, `.image`, anything unknown) is renamed to what the bytes say.
# Files whose extension is already a known one are left exactly as they
# are, so nothing that worked before changes behaviour.

_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)
_KNOWN_IMAGE_EXTS = frozenset(("jpg", "jpeg", "png", "webp", "gif", "bmp", "avif"))


def _sniff_image_ext(head: bytes):
    """The extension the file's own first bytes claim, or None."""
    for magic, ext in _IMAGE_MAGIC:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if len(head) >= 12 and head[4:8] == b"ftyp" and head[8:12] in (b"avif", b"avis"):
        return "avif"
    return None


class ThumbnailExtFixPP(yt_dlp.postprocessor.PostProcessor):
    """Gives a thumbnail file the extension its own bytes claim."""

    def run(self, info):
        for thumb in info.get("thumbnails") or []:
            path = thumb.get("filepath")
            if not path:
                continue
            current = os.path.splitext(path)[1].lstrip(".").lower()
            if current in _KNOWN_IMAGE_EXTS:
                continue
            try:
                with open(path, "rb") as fh:
                    head = fh.read(16)
            except OSError:
                continue
            real = _sniff_image_ext(head)
            if real is None:
                continue
            fixed = os.path.splitext(path)[0] + "." + real
            try:
                os.replace(path, fixed)
            except OSError:
                continue
            self.to_screen(f'Correcting thumbnail "{path}" extension to {real}')
            thumb["filepath"] = fixed
            moves = info.get("__files_to_move")
            if isinstance(moves, dict) and path in moves:
                moves[fixed] = os.path.splitext(moves.pop(path))[0] + "." + real
        return [], info


def _attach_thumbnail_ext_fix(ydl) -> None:
    """Insert the fixer at the head of the post-process chain.

    The embedder converts — and tears the whole job down — on a lying
    extension, so the truth has to run first. `_pps` is private and yt-dlp
    offers no public ordering hook; guarded, so a future yt-dlp can only
    cost the ordering, never a job.
    """
    try:
        pp = ThumbnailExtFixPP(ydl)
        ydl.add_post_processor(pp, when="post_process")
        chain = ydl._pps.get("post_process")
        if chain and chain[-1] is pp and len(chain) > 1:
            chain.remove(pp)
            chain.insert(0, pp)
    except Exception:  # noqa: BLE001 - best-effort ordering, never fatal
        pass


def extract_info(opts: dict, url: str, *, download: bool, sleep=time.sleep,
                 retry_refresh: bool = False):
    """ydl.extract_info with a second (and third) chance for TikTok, and one
    re-extraction for a download that outlived its link (the transplant).

    `retry_refresh=True` is for downloads: after a refusal that arrived *after*
    bytes had been written, the extraction is re-run once for fresh links and
    yt-dlp's own `continuedl` resumes the `.part`. `sleep` is injectable so
    tests never actually wait.
    """
    # TikTok's "audio" is the video's music file, not its soundtrack — for
    # licensed songs a 60 s preview (v0.45.7: "the audio cut after a
    # minute"). Every pick gets its audio side made safe before it runs.
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        host = ""
    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        opts = {**opts, "format": tiktok_safe_format(opts.get("format"))}

    seen = {"bytes": False}
    refresh_left = 1 if (download and retry_refresh) else 0
    tiktok_left = ATTEMPTS - 1
    while True:
        face = RETRY_USER_AGENTS[ATTEMPTS - 1 - tiktok_left]
        base = _with_user_agent(opts, face) if face else opts
        run_opts = _watching_progress(base, seen) if download else base
        seen["bytes"] = False
        try:
            with yt_dlp.YoutubeDL(run_opts) as ydl:
                if download:
                    _attach_thumbnail_ext_fix(ydl)
                return ydl.sanitize_info(ydl.extract_info(url, download=download))
        except yt_dlp.utils.YoutubeDLError as exc:
            if (refresh_left and seen["bytes"] and is_expired_link(exc)
                    and not is_tiktok_flake(exc)):
                refresh_left -= 1
                print("[link refresh] the download hit a refused/expired link "
                      "after bytes had arrived — re-extracting for fresh links "
                      "and resuming", flush=True)
                sleep(REFRESH_PAUSE)
                continue
            if tiktok_left <= 0 or not is_tiktok_flake(exc):
                raise
            print(f"[TikTok] refused the attempt "
                  f"({ATTEMPTS - tiktok_left}/{ATTEMPTS}) — retrying the "
                  "webpage fetch", flush=True)
            sleep(BACKOFF[ATTEMPTS - 1 - tiktok_left])
            tiktok_left -= 1
