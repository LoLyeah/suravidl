"""What each release changed — the notes behind the one-time card after an
update.

The web UI shows the entries newer than the version THAT device last ran
(localStorage), once, and waits for "Got it". A fresh install shows nothing.
Settings can re-open the current version's notes any time.

House rule: ENTRIES[0] is the CURRENT version — the suite fails on a version
bump without notes, because the card is only as honest as this list. Text is
user-facing: what THEY get, not how it was built.
"""
from __future__ import annotations

from . import __version__

ENTRIES = [
    {
        "version": "0.46.15",
        "title": "The settle",
        "items": [
            "The Windows app installs as a folder now instead of one self-unpacking file: the unpack could lose a file to antivirus (the \"Failed to load Python DLL\" error) — a folder cannot, and the app starts faster.",
        ],
    },
    {
        "version": "0.46.14",
        "title": "The round",
        "items": [
            "The ETA reads like a time, not a calculator tape: 19s of estimate used to print as 19.126124260462905s — it now wears the same clock as every other duration (0:19, 2:05, 1:02:03).",
        ],
    },
    {
        "version": "0.46.13",
        "title": "The still",
        "items": [
            "The queue stops blinking: a failed card next to finished takes was re-inserted on every poll — its fade replaying every second. The failure caption now keeps its place above the failures, and the cards hold still.",
        ],
    },
    {
        "version": "0.46.12",
        "title": "The walk",
        "items": [
            "The seal's bridge check now applies only where it can protect every frame: older WebViews keep the frame walk's pre-seal model, so media inside players' iframes is found again.",
        ],
    },
    {
        "version": "0.46.11",
        "title": "The solder",
        "items": [
            "The phone build ships again: the in-browser sniffer's second injector was missing the wire the seal added — threaded through, and the APK is back on the release page.",
        ],
    },
    {
        "version": "0.46.10",
        "title": "The seal",
        "items": [
            "Holes closed, quietly: the engine's page no longer hands out its token to anything that asks — the app opens it with a key, and a bare address is refused with a sentence.",
            "A second resume of a paused download is refused instead of writing the file twice; proxy passwords and login headers never reach the log card or a diagnostics bundle.",
            "Small truths: live recordings show their real size on disk, cuts work for takes from before a folder change, and the Firefox extension stopped asking for a permission it never used.",
        ],
    },
    {
        "version": "0.46.9",
        "title": "The cut",
        "items": [
            "The marks keep their promise: Cut this take trims the file you are playing — local, lossless, filed as its own take. A section re-download of an existing file now says nothing was fetched.",
        ],
    },
    {
        "version": "0.46.8",
        "title": "The guide",
        "items": [
            "The watch list teaches itself: paste a link and Follow works from zero, with a three-step how-to until the first follow — and the audio-only picks light up.",
        ],
    },
    {
        "version": "0.46.7",
        "title": "The brief",
        "items": [
            "The queue gives you the brief: counts on the filters, one state line (nothing running · 2 filed · 3 failed), failures gathered below the finished takes, and each failure one red sentence.",
        ],
    },
    {
        "version": "0.46.6",
        "title": "The flare",
        "items": [
            "Failures now speak everywhere: a download that dies tells you wherever you are — one toast, a rose count on the Queue tab — and settled rows carry size · time · site.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
