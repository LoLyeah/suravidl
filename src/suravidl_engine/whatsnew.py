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
        "version": "0.45.17",
        "title": "The audit",
        "items": [
            "The stream fixer: text subtitles are converted for mp4 instead of failing the whole fix, and every flagged track is tested alone before removal — a healthy track can no longer be lost with a bad one.",
            "Engine audit fixes, the rest: deleting a download can neither take an unrelated file nor run while a job writes; resumed jobs find their partial file; dead playlists report an error; logs get secrets redacted.",
        ],
    },
    {
        "version": "0.45.16",
        "title": "The proof",
        "items": [
            "The fix no longer trusts stream warnings — it asks the actual copy whether each stream can pass, and only drops what the copy itself refuses. If your video vanished into a 60 MB file, that was this false alarm.",
            "Every drop is still named in the log — and the video is only ever dropped as the last resort, after the copy has refused it twice.",
        ],
    },
    {
        "version": "0.45.15",
        "title": "The keeper",
        "items": [
            "The stream fix now removes only what it names as broken — anything it can’t read is kept untouched rather than silently gone. Re-add the link — it comes out whole now.",
            "If the check can’t read a file’s stream report, it says so and leaves the file alone — never a silent guess.",
        ],
    },
    {
        "version": "0.45.14",
        "title": "The oracle",
        "items": [
            "The merge fix now takes its verdict from ffmpeg itself, not the app’s tiny probe — on Android that probe reads every audio track as broken, which is why the fix kept missing. Healthy tracks are never touched now.",
            "When the fix cannot apply, the log says so — it can never skip silently again.",
        ],
    },
    {
        "version": "0.45.13",
        "title": "The hook",
        "items": [
            "Fresh downloads now survive the junk-audio stream too: v0.45.12 only saved retries — a first download died even earlier, inside yt-dlp’s own cleanup. The stream is cleaned the moment it lands.",
            "Deleting a job no longer moves your screen: the queue keeps your spot while rows leave (the deleted row used to visibly sail to the list’s end — it read as scrolling to the bottom).",
        ],
    },
    {
        "version": "0.45.12",
        "title": "The merge",
        "items": [
            "The 953 MB download that died with \"Conversion failed!\" no longer does: a junk audio track inside the stream is dropped before the metadata pass, and the file lands as a real .mp4. Retry that job — no re-download needed.",
            "The yt-dlp tab's Save floats now like Settings', and the Save strip frosts on Android too.",
        ],
    },
    {
        "version": "0.45.11",
        "title": "The strip",
        "items": [
            "Every blur renders for real now: the fades that lingered after landing kept Chromium from painting ANY frost beneath them — the Save strip, the queue bar, the popups, the FAQ cards were all silently flat.",
            "Scroll the Settings card: rows melt under the Save strip, exactly the way it was always meant to look.",
        ],
    },
    {
        "version": "0.45.10",
        "title": "The ring",
        "items": [
            "Every popup — What’s new, FAQ, the dialogs — shows the real room through its glass now: the dim rides the card itself (the tutorial ring’s exact trick) instead of darkening everything the card looks through.",
            "Same card, same blur, one mechanism on every popup; the room behind stays dimmed exactly as before.",
        ],
    },
    {
        "version": "0.45.9",
        "title": "The handoff",
        "items": [
            "On Windows, Restart & Install could quit the app and install nothing — the installer found a half-gone app and quietly asked a question nobody could see. It now waits for the app to fully exit first, then installs.",
            "Every run leaves a short trail at .suravidl\\update.log in your user folder, so a hiccup is never invisible again.",
        ],
    },
    {
        "version": "0.45.8",
        "title": "The reach",
        "items": [
            "Expanding a queue card no longer needs a tap on one word at the top left — the whole card folds and unfolds it now, everything except the buttons and links that do their own thing.",
            "The card reads as tappable everywhere, and the keyboard path is unchanged: Tab to the title, then Enter or Space.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
