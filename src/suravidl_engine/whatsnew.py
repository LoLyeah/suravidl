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
        "version": "0.47.9",
        "title": "The ghost",
        "items": [
            "The phone app sweeps its own abandoned gallery imports at every start: a killed copy left an invisible file that managers counted but never showed (an 'empty' folder claiming 18 items, 516 MB).",
        ],
    },
    {
        "version": "0.47.8",
        "title": "The path",
        "items": [
            "Restart & Install starts PowerShell by its exact system path now — on one machine the bare name could not be found (WinError 2), so a verified update never began. The update log records the path it tried.",
        ],
    },
    {
        "version": "0.47.7",
        "title": "The drawer",
        "items": [
            "A finished download can be renamed from its card — the file and its subtitles/thumbnail follow the new name together, and names Windows would refuse are refused before anything moves.",
            "Clear history forgets the finished rows and keeps the files in your downloads folder (desktop only — on the phone the files live in app storage).",
        ],
    },
    {
        "version": "0.47.6",
        "title": "The clock",
        "items": [
            "The finishing phase now names its step and counts up — 'joining video and audio · 2:14' instead of a dead bar while a big file is copied.",
        ],
    },
    {
        "version": "0.47.5",
        "title": "The carrier",
        "items": [
            "A server that wraps its segments in fake images (only its own player can unwrap them) now says so before downloading, with the way out — and 'auto' picks MKV when subtitles are embedded.",
        ],
    },
    {
        "version": "0.47.4",
        "title": "The minutes",
        "items": [
            "A failed finish now explains itself: the log keeps what yt-dlp and ffmpeg actually said, and an output file that cannot be opened says what that usually means (name, disk, antivirus).",
        ],
    },
    {
        "version": "0.47.3",
        "title": "The legend",
        "items": [
            "The stream list names each row from the manifest itself — a real resolution, the audio track's name, one 'All qualities' row — the what's-new card now survives a restart, and a refused update says why.",
        ],
    },
    {
        "version": "0.47.2",
        "title": "The masquerade",
        "items": [
            "Streams that disguise their segments as images (.png/.webp) now download the whole episode, audio tracks included — and the extension's list names what each row is: all qualities, a resolution, or an audio track.",
        ],
    },
    {
        "version": "0.47.1",
        "title": "The pocket",
        "items": [
            "Scrambled playlists now work on the phone too: the in-app browser's sniffer lifts the player's decode key while you watch, and the download rides it to the engine — reanime.to and friends download like any other site.",
        ],
    },
    {
        "version": "0.47.0",
        "title": "The veil",
        "items": [
            "Sites that scramble their playlists (reanime.to and friends) now download like any other: the extension lifts the player's decode key while sniffing, and the engine unscrambles the tree before the normal path.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
