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
        "version": "0.46.1",
        "title": "The recorder",
        "items": [
            "Live streams are recorded now, not chased: a LIVE link shows ● REC with time on air and bytes — no fake percentage — and Stop & keep keeps everything recorded so far.",
        ],
    },
    {
        "version": "0.46.0",
        "title": "The toolbox",
        "items": [
            "Several links at once now get checked before anything queues: each is probed, named, and given its own honest answer — tick what is good, then queue just those.",
            "Copy diagnostics bundles a bug report in one paste — versions, what this ffmpeg can do, settings (secrets redacted by the engine), and the log tail.",
        ],
    },
    {
        "version": "0.45.32",
        "title": "The slideshow",
        "items": [
            "A TikTok photo post now says what it is — a slideshow, not a video, with nothing for a downloader to save and where its audio might still be caught.",
        ],
    },
    {
        "version": "0.45.31",
        "title": "The frames",
        "items": [
            "The in-app browser's sniffer now runs inside cross-origin frames too — a player there is caught by the script layers, not only its network requests — and its DOM watching is debounced on heavy pages.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
