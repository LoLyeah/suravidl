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
    {
        "version": "0.46.5",
        "title": "The desk",
        "items": [
            "Download names its three jobs: Link, Batch, Watch list. Batch gets its own box — a multi-link paste carries over in one tap — and the Watch list label counts what you follow.",
        ],
    },
    {
        "version": "0.46.4",
        "title": "The comeback",
        "items": [
            "macOS updates come back on their own. The reopen after an update now forces a fresh instance, ends a lingering old process, and writes every attempt to ~/Library/Logs/suravidl-update.log.",
        ],
    },
    {
        "version": "0.46.2",
        "title": "The follower",
        "items": [
            "Follow a playlist or channel: its new videos come in on their own. Following starts from now, nothing is ever grabbed twice, and a watch-list grab wears a quiet tag on its card.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
