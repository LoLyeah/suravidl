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
        "version": "0.49.7",
        "title": "The index",
        "items": [
            "The yt-dlp options browser reads as one table: a header per category instead of the category under every flag, a full-width search, flags with their argument in a quieter voice, and a + on the row you mean.",
            "The list no longer runs past the card: the description stops inside it, and the very long ones are cut at a word with an ellipsis — the whole text stays in the tooltip.",
            "Deprecated switches yt-dlp hides from its own help are gone from the list instead of showing “SUPPRESSHELP” as their description.",
        ],
    },
    {
        "version": "0.49.6",
        "title": "The gate",
        "items": [
            "When the probe says a page has no extractor, Download now and START go dead for that link — with the reason in the tooltip — instead of queueing a download that can only fail.",
        ],
    },
    {
        "version": "0.49.5",
        "title": "The gap",
        "items": [
            "The dashed hint no longer sits flush against the TAKE plate — one 16px step, like every other gap on the deck.",
        ],
    },
    {
        "version": "0.49.4",
        "title": "The day",
        "items": [
            "Light mode's weakest controls, fixed: a disabled START stays in the accent family instead of turning dusty blue, the quick action stops looking like an empty field, and unlit scope lamps are hollow rings.",
        ],
    },
    {
        "version": "0.49.3",
        "title": "The ellipsis",
        "items": [
            "Long paths in the folder, rate and proxy fields end in an ellipsis instead of cutting a token in half — long-press shows the whole value.",
        ],
    },
    {
        "version": "0.49.2",
        "title": "The cue",
        "items": [
            "The URL field wears one focus cue instead of a ring stacked on a halo, and its hint ends in an ellipsis on a phone instead of cutting a word.",
        ],
    },
    {
        "version": "0.49.1",
        "title": "The thumb",
        "items": [
            "On a phone the fields finally match the rest of the controls: 44px tall at 16px, so iOS no longer zooms when you tap one.",
            "A phone on its side is 360px tall — the floating Save bar now waits at the end of the panel instead of covering the schemes.",
        ],
    },
    {
        "version": "0.49.0",
        "title": "The landing",
        "items": [
            "A finishing take lands: the COMPLETED pill stamps flat while a scanner pass runs along the row, once — the machine confirming the file.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
