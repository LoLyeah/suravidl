"""One extraction call for the whole engine, with TikTok's flaky anti-bot
handled in ONE place.

TikTok's web front refuses a fraction of fetches from any given network
("Unexpected response from webpage request" — the challenge page never
arrives); yt-dlp's own tracker treats it as intermittent: "roughly a third
of requests fail ... the same videos download fine individually, and that's
what the repeated passes are for" (yt-dlp/yt-dlp#17604). Two more attempts
turn that refusal into a non-event. Every other error raises on the spot —
a retry must never paper over a real answer.
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

ATTEMPTS = 3
BACKOFF = (0.8, 2.0)


def is_tiktok_flake(error: object) -> bool:
    """Is this failure TikTok's intermittent refusal (safe to retry)?"""
    text = str(error).lower()
    return any(phrase in text for phrase in TIKTOK_FLAKE_PHRASES)


def extract_info(opts: dict, url: str, *, download: bool, sleep=time.sleep):
    """ydl.extract_info with a second (and third) chance for TikTok.

    `sleep` is injectable so tests never actually wait.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.sanitize_info(ydl.extract_info(url, download=download))
        except yt_dlp.utils.YoutubeDLError as exc:
            if attempt >= ATTEMPTS or not is_tiktok_flake(exc):
                raise
            print(f"[TikTok] refused the attempt ({attempt}/{ATTEMPTS}) — "
                  "retrying the webpage fetch", flush=True)
            sleep(BACKOFF[attempt - 1])
    raise AssertionError("unreachable")  # pragma: no cover
