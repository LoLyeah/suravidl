"""One extraction call for the whole engine, with the two refusals that are
worth a second attempt handled in ONE place.

TikTok's web front refuses a fraction of fetches from any given network
("Unexpected response from webpage request" — the challenge page never
arrives); yt-dlp's own tracker treats it as intermittent: "roughly a third
of requests fail ... the same videos download fine individually, and that's
what the repeated passes are for" (yt-dlp/yt-dlp#17604). Two more attempts
turn that refusal into a non-event.

The second: signed CDN links rotate mid-transfer. A download that dies on an
HTTP 403/410 *after bytes had arrived* was not refused — its link expired
while it ran. cobalt calls the cure a transplant (it rewrites the running
stream); here it falls out of re-running the extraction: yt-dlp's own
`continuedl` resumes the `.part` from where it stopped, with a fresh URL
under it. The transplant is offered once, and only when bytes actually
arrived — a 403 before any progress is the site's answer, and is passed
through untouched.

Every other error raises on the spot — a retry must never paper over a real
answer.
"""
from __future__ import annotations

import time

import yt_dlp

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


def extract_info(opts: dict, url: str, *, download: bool, sleep=time.sleep,
                 retry_refresh: bool = False):
    """ydl.extract_info with a second (and third) chance for TikTok, and one
    re-extraction for a download that outlived its link (the transplant).

    `retry_refresh=True` is for downloads: after a refusal that arrived *after*
    bytes had been written, the extraction is re-run once for fresh links and
    yt-dlp's own `continuedl` resumes the `.part`. `sleep` is injectable so
    tests never actually wait.
    """
    seen = {"bytes": False}
    run_opts = _watching_progress(opts, seen) if download else opts
    refresh_left = 1 if (download and retry_refresh) else 0
    tiktok_left = ATTEMPTS - 1
    while True:
        seen["bytes"] = False
        try:
            with yt_dlp.YoutubeDL(run_opts) as ydl:
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
