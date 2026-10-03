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
        "version": "0.40.3",
        "title": "The wide view",
        "items": [
            "The phone's browser can ask for the desktop page now: a mobile site / desktop site switch sits beside the ads one \u2014 flip it, reload, and the site serves its full-width layout. Same session, same finds.",
            "The switch remembers itself, so the next visit opens wide on its own.",
        ],
    },
    {
        "version": "0.40.2",
        "title": "The sieve",
        "items": [
            "The queue has a sieve now: All / Active / Filed / Errors chips hide what you are not looking for \u2014 and when a view hides everything, a line says exactly how many are hidden, one tap from All.",
            "The chips stay out of the way until there is a queue worth filtering.",
        ],
    },
    {
        "version": "0.40.1",
        "title": "The dial",
        "items": [
            "Videos with several audio languages now show a chooser in the patch bay: pick one and a video-only take pairs THAT track \u2014 the site\u2019s own pick still stands behind it if the video lacks your choice.",
            "The formats list stopped hiding dubs: two languages of one quality are two rows now, each saying which language it is.",
        ],
    },
    {
        "version": "0.40.0",
        "title": "The workbench",
        "items": [
            "Big batches stay light: the queue now runs on a small fixed team of workers instead of parking a thread per link \u2014 twenty pasted links cost the same as one, and the queue keeps its order.",
            "The download history got sturdier: it runs in WAL mode now (parallel downloads stop stepping on each other), carries a version stamp, and upgrades older histories on first launch.",
            "Signed links keep their secrets: token, sig and key values in URLs are now redacted from any error the app shows or stores.",
        ],
    },
    {
        "version": "0.39.13",
        "title": "The shade",
        "items": [
            "On macOS the page no longer floats straight on the desktop: it sits on a near-opaque wash of its own room, so the wallpaper reads as a faint hint behind the glass instead of as the background.",
            "Toasts find their spot on the desktop too: the lane now measures what is really docked at the bottom — the transport, the settings Save strip — and tucks into the corner when nothing is.",
        ],
    },
    {
        "version": "0.39.12",
        "title": "The comb",
        "items": [
            "An external audit of the motion system, confirmed finding by finding: the glass tracks resizes, macOS calls ride the main thread, the calm flips once and nudges, and the probe reports what it actually found.",
        ],
    },
    {
        "version": "0.39.11",
        "title": "The sibling",
        "items": [
            "The glass covered the page — everything a blur. The material now hosts in the webview's own superview, framed to it, never as a child. The probe serves a real URL so the webview gets parented and the walk answers.",
        ],
    },
    {
        "version": "0.39.10",
        "title": "The walkabout",
        "items": [
            "The dressing was happening before the webview even existed in the window (pywebview parents it at first load), so the calm and the native glass silently never ran on macOS. They now wait for the page to land.",
        ],
    },
    {
        "version": "0.39.9",
        "title": "The calm",
        "items": [
            "The shell stops flinching at its own window: WKWebView's occlusion detection goes off, so the page is no longer born hidden and CSS animations play on macOS. Also fixed: the native glass never actually inserted.",
        ],
    },
    {
        "version": "0.39.8",
        "title": "The truce",
        "items": [
            "Some pages notice their ad networks served empty and refuse to run. The phone browser now has a truce switch — “ads blocked / ads allowed” in its second row: flip and reload to let the page in.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
