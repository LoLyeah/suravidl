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
        "version": "0.48.4",
        "title": "The rim",
        "items": [
            "The 1px hairline around every scheme chip is gone — it read as a bright warm edge along the top-left, which is the border that kept being circled.",
        ],
    },
    {
        "version": "0.48.3",
        "title": "The follow",
        "items": [
            "The Light / Dark / AMOLED previews now take their colour from the scheme you pick — no more amber diagonals under Cobalt.",
        ],
    },
    {
        "version": "0.48.2",
        "title": "The rollback",
        "items": [
            "The settings panel's outline and the dot beside a selected name are gone — both were mine, both were wrong.",
            "Wallpaper now sticks: the palette is read once and cached, so a failed bridge call can no longer make it do nothing.",
        ],
    },
    {
        "version": "0.48.1",
        "title": "The tint",
        "items": [
            "A selected swatch is a soft tint with a small LED, never a bright outline — the white edge on AMOLED is gone for good.",
            "Material You now actually appears on Android 12+: the Wallpaper scheme was hidden behind a state you could not reach, and its palette never parsed.",
        ],
    },
    {
        "version": "0.48.0",
        "title": "The palette",
        "items": [
            "Three more schemes: Cobalt (a grading monitor), Oxide (splicing tape) and Silver (halide mono), each with contrast measured rather than eyeballed.",
            "On Android 12+, Wallpaper follows your Material You palette. And the bright double ring on a selected swatch is gone.",
        ],
    },
    {
        "version": "0.47.31",
        "title": "The polish",
        "items": [
            "The queue stops re-reading a finished file's size on every poll, and idles at one request every ten seconds instead of fifty a minute.",
            "Cancelled jobs stop claiming the running lamp; a split keeps its subtitles and its second audio track; Download now obeys an empty field; Escape closes any dialog.",
        ],
    },
    {
        "version": "0.47.30",
        "title": "The line",
        "items": [
            "The source field is one line again: a flex basis from 0.47.28 became a 220px-tall box on phones, where the row turns into a column.",
        ],
    },
    {
        "version": "0.47.29",
        "title": "The hand",
        "items": [
            "A download can carry its own title and artist: the file is renamed and its tags rewritten, for that job only — no more site junk in your library.",
            "Split by chapters: one file per section, cut from the finished download in a single pass, named by chapter.",
        ],
    },
    {
        "version": "0.47.28",
        "title": "The tap",
        "items": [
            "Download now: one tap queues the pasted link at your default quality, no format list — and a link shared to the phone can skip it too (Settings).",
            "The notification now shows how far along the download is, how fast it runs and how long is left, with a Cancel button.",
        ],
    },
    {
        "version": "0.47.27",
        "title": "The flush",
        "items": [
            "A job that fails just as the app restarts now comes back as failed, not interrupted: the row is written before the state is shown.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
