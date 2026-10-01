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
        "version": "0.38.4",
        "title": "The native glass",
        "items": [
            "On macOS the app window is no longer a painted box: it now sits on Apple's real glass material — Liquid Glass on macOS 26 and up, native vibrancy on every earlier release — and the dock icon is finally the pine mark.",
        ],
    },
    {
        "version": "0.38.3",
        "title": "The audit and the second voice",
        "items": [
            "A second color scheme joins the house amber: Pine & cream, the brand's own voice — pine by day, the cream chip at night. Pick it in Settings → Appearance → Scheme.",
            "Site badges (YouTube, X, Vimeo…) are now readable in the light theme, and a handful of dim labels, greens and state lamps got darker ink so everything clears the readability floor.",
            "The keyboard works everywhere now: a download's title opens with Enter, the what's-new card closes with Escape or by clicking outside, and buttons that looked pressed-in but did nothing were honest again.",
            "Smaller pass: the minimize button is a drawn icon, chips get a touch-sized press target on phones, sub-tabs and expanders announce themselves to screen readers, and the queue says it is loading.",
        ],
    },
    {
        "version": "0.38.2",
        "title": "The receipt and the lane",
        "items": [
            "Toasts and the update notice sit right above the bottom bar on tabs where nothing is docked \u2014 they only lift when your transport (or the Settings Save strip) is actually there. No more hovering over a gap.",
            "Tap a finished download's title and the card reads like a receipt now: the file size and the full saved location, in full \u2014 not just the name.",
        ],
    },
    {
        "version": "0.38.1",
        "title": "Straight to Download",
        "items": [
            "The app opens on the Download page again \u2014 quitting and reopening no longer drops you back on whichever tab you last touched. A URL that names a tab (like a #settings bookmark) still opens it.",
        ],
    },
    {
        "version": "0.38.0",
        "title": "Pine & cream",
        "items": [
            "A new mark: a big cream download arrow on a pine tile, with the play knocked out of it \u2014 it still reads at a 16px favicon, where the old blue icon turned to mush.",
            "The header mark follows your theme: the pine tile in the light room, the cream chip at night and on AMOLED \u2014 no more one-size icon sinking into dark rooms.",
        ],
    },
    {
        "version": "0.37.7",
        "title": "The readable queue",
        "items": [
            "The queue count rides the Queue tab's icon corner now — a number no longer nudges the button out of line with its neighbors.",
            "Tap a queue card's title to unfold the whole line — long titles read in full instead of \u201cJapanese Wagyu\u2026\u201d.",
        ],
    },
    {
        "version": "0.37.6",
        "title": "The board reads",
        "items": [
            "A probed list no longer runs off the phone's right edge — each format row re-stacks: quality and its Take button on top, the format beneath, the size last.",
            "Toasts dock right above the bottom bar on every tab (the settings tab no longer floats them over the page).",
            "The START bar and the update popup pour denser on the phone — the readout and the dialog never share pixels with the page behind them again.",
        ],
    },
    {
        "version": "0.37.5",
        "title": "The bar comes home",
        "items": [
            "The START bar blurs for real again: it rides in the page's flow now — this WebView only composites the blur for in-flow layers (and the bar can no longer sit on top of the text at the page's end).",
            "\"This download only\" opens and closes with a door now — it grows and settles instead of popping.",
        ],
    },
    {
        "version": "0.37.4",
        "title": "The backdrop pass",
        "items": [
            "Every dialog now frosts the whole screen behind it — on desktop and phone alike (the flat dim veil that made the popup look blur-less is gone).",
            "The liquid-glass material is written down properly — fill, blur, gloss and edge per style and per host, in DESIGN.md.",
        ],
    },
    {
        "version": "0.37.3",
        "title": "The steady pass",
        "items": [
            "The START · best bar stays at the bottom now — a tab switch used to re-anchor it to the page, leaving it stuck over the content.",
            "Opening What's new (or any dialog) frosts the whole screen behind it — the blur reaches the backdrop, not just the plate.",
            "The chosen tab in the bottom bar wears a squircle outline instead of a hairline.",
            "\"best available\" keeps its whole readout on a phone.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
