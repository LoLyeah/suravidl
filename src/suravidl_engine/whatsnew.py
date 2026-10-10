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
        "version": "0.45.30",
        "title": "The poster",
        "items": [
            "A cover image that cannot be embedded no longer kills the download — the thumbnail step failing (this phone cannot read some image formats) leaves the video intact and says so on the card.",
        ],
    },
    {
        "version": "0.45.29",
        "title": "The note",
        "items": [
            "A download that finishes with a caveat now wears an ⓘ and says why — subtitles kept as files instead of embedded, an unusable stream removed — so a successful job never hides what it could not do.",
        ],
    },
    {
        "version": "0.45.28",
        "title": "The captions",
        "items": [
            "Subtitles no longer break a download on the phone: the app checks what its ffmpeg can really do and keeps them as files beside the video when it cannot embed them (MKV still embeds).",
            "Reddit share links (“/s/” shortcuts) now say what they are: browser-only shortcuts, with the trick to get the full link.",
        ],
    },
    {
        "version": "0.45.27",
        "title": "The silence",
        "items": [
            "Deleting a just-cancelled download waits for the writer to actually go quiet first — a race could leave a leftover fragment behind on slow machines.",
        ],
    },
    {
        "version": "0.45.26",
        "title": "The column",
        "items": [
            "A job database from an older version repairs itself on the first start — a missing column on upgraded installs had quietly broken new downloads and deleting jobs.",
        ],
    },
    {
        "version": "0.45.25",
        "title": "The trace",
        "items": [
            "If anything inside the engine ever fails unexpectedly, the app now says what failed — the error's own name and message — instead of a bare “500”.",
        ],
    },
    {
        "version": "0.45.24",
        "title": "The spare",
        "items": [
            "A download stalled by a dead source no longer shrinks the engine — its worker is replaced, so a queue can never quietly stop moving.",
        ],
    },
    {
        "version": "0.45.23",
        "title": "The wait",
        "items": [
            "The in-app browser now waits for the engine when it is still starting — tapping a sniffed link seconds after opening the app queues it instead of saying the engine refused it.",
        ],
    },
    {
        "version": "0.45.22",
        "title": "The watch",
        "items": [
            "A download whose source stops sending data no longer hangs forever — after eight silent minutes it fails with a clear message instead of staring at a stuck row.",
            "Cancelled downloads always delete now, even when the engine is still cleaning up behind them.",
        ],
    },
    {
        "version": "0.45.21",
        "title": "The start",
        "items": [
            "A claimed download now says so right away — a job stuck before its first byte used to sit at “Queued” forever instead of showing it was already running.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
