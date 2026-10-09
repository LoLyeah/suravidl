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
    {
        "version": "0.45.20",
        "title": "The twin",
        "items": [
            "The Settings Save pours the same glass as the yt-dlp tab's Save now — on AMOLED the old denser pour read as a solid black card.",
        ],
    },
    {
        "version": "0.45.19",
        "title": "The shadow",
        "items": [
            "The dim behind popups is back everywhere — the AMOLED theme had silently told CSS “no shadows” in a way that also erased every popup’s backdrop dim on phones. One token, fixed.",
            "The Settings Save now floats as a proper glass card, exactly like the yt-dlp tab’s Save — same border, same frost (it used to be a flat full-width bar).",
        ],
    },
    {
        "version": "0.45.18",
        "title": "The fallback",
        "items": [
            "On phones the bundled ffmpeg cannot convert subtitles at all, so the fixer now drops a file-blocking subtitle track as its named last resort instead of failing the whole repair — desktop keeps converting it properly.",
            "The v0.45.17 note claimed that conversion worked everywhere — it does not; this is the correction, verified against both real ffmpeg builds.",
        ],
    },
    {
        "version": "0.45.17",
        "title": "The audit",
        "items": [
            "The stream fixer: text subtitles are converted for mp4 instead of failing the whole fix, and every flagged track is tested alone before removal — a healthy track can no longer be lost with a bad one.",
            "Engine audit fixes, the rest: deleting a download can neither take an unrelated file nor run while a job writes; resumed jobs find their partial file; dead playlists report an error; logs get secrets redacted.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
