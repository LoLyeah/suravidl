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
    {
        "version": "0.46.19",
        "title": "The knock",
        "items": [
            "The app lands front when an update restarts it, and takes clicks immediately. A script-relaunched window used to open in the background — the update looked like it never came back, clicks dead until an app switch.",
        ],
    },
    {
        "version": "0.46.18",
        "title": "The nickname",
        "items": [
            "A stream's whole signed address used to become its name — “master [master.m3u8?token=…]”. Long or messy ids now wear a short stable tag (“master [4f8a2b9c3d1e].mp4”); compact ids stay as they are.",
        ],
    },
    {
        "version": "0.46.17",
        "title": "The namesake",
        "items": [
            "Two different videos could end up under one filename: one was silently skipped, or replaced the other outright. Every download now wears the site's own id — takes never fight over a name.",
            "A custom template without the id gets its own guards: an incoming file that finds its name taken by another video lands beside it and says so — never a quiet skip, never a quiet replacement.",
            "Caveats attached after a download (a removed stream, a skipped thumbnail) now actually reach the card — they used to be written where nothing read them.",
        ],
    },
    {
        "version": "0.46.16",
        "title": "The pickup",
        "items": [
            "When a page hides its player, the desktop now points the way through: the companion extension hands the stream over, probed — a short guide opens right there, linked from the FAQ. The phone keeps browser + Scan.",
        ],
    },
    {
        "version": "0.46.15",
        "title": "The settle",
        "items": [
            "The Windows app installs as a folder now instead of one self-unpacking file: the unpack could lose a file to antivirus (the \"Failed to load Python DLL\" error) — a folder cannot, and the app starts faster.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
