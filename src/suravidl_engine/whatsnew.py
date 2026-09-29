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
        "version": "0.35.0",
        "title": "Presets you can see",
        "items": [
            "An applied preset now shows on the video card — name, what it does, and a ✕ — instead of hiding in the collapsed block below the table.",
            "Tap the strip to open that block and change or clear it.",
            "The toast after a download names the preset that went with it.",
            "Picking a quality no longer silently throws away an audio preset — the app says what happened.",
        ],
    },
    {
        "version": "0.34.0",
        "title": "Presets that make sense",
        "items": [
            "A site that refuses subtitles no longer kills the download — the media still comes down, and the row says why the captions are missing.",
            "Presets are editable now: apply one, change the fields, and press Update to change it for good.",
            "You can save the This download only block as a preset, right from the download tab.",
            "An applied preset spells out every option it carries — including ones the block has no field for.",
        ],
    },
    {
        "version": "0.33.0",
        "title": "The polish pass",
        "items": [
            "A failed probe now shows in red, like every other error — it used to whisper in grey.",
            "Short clips stop claiming to be \"0 min\".",
            "The Quality, Audio and Subtitles rows line up flush with the rest of the card.",
            "Scrollbars, text selection, the caret, input hints and number columns follow the theme — not the browser's defaults.",
            "The footer's copy path / open folder links finally read as words.",
        ],
    },
    {
        "version": "0.32.1",
        "title": "The robustness pass",
        "items": [
            "Deleting a download can no longer take an older download folder with it.",
            "Retry works with presets again, and switching between a preset and a "
            "format no longer fails.",
            "Files with non-English names (CJK, Cyrillic, emoji) play and open correctly.",
            "Deleted videos take their subtitles along — including converted .srt files.",
            "Streaming sizes stay honest, and a playlist can no longer point the "
            "engine at local or internal addresses.",
        ],
    },
    {
        "version": "0.32.0",
        "title": "The What's new card",
        "items": [
            "After every update, the app shows what changed — once, on the first launch.",
            "Re-read it any time from Settings → What's new.",
        ],
    },
    {
        "version": "0.31.0",
        "title": "Downloads survive expired links",
        "items": [
            "A download that hits an expired link now refreshes it and resumes, "
            "instead of dying half-way (Instagram/Facebook/TikTok-style links).",
            "Streaming (HLS) finds now show an estimated size — like "
            "\"HLS · ~42 MB\" — instead of nothing.",
        ],
    },
    {
        "version": "0.30.0",
        "title": "The in-app browser stays put",
        "items": [
            "Pages that try to kick you into another app (TikTok's app link) are "
            "refused — the page stays open and your finds are kept.",
        ],
    },
    {
        "version": "0.29.0",
        "title": "Cache button, more presets",
        "items": [
            "Clear the app cache with its own button — file deletes no longer touch it.",
            "New built-in presets: MP4 1080p/720p, subtitles (sidecar or embedded), cover art.",
        ],
    },
    {
        "version": "0.28.0",
        "title": "Sign-in guidance where you need it",
        "items": [
            "The in-app browser explains the sign-in routes, so gated videos make sense sooner.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
