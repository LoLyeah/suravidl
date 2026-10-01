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
        "version": "0.39.1",
        "title": "The hush",
        "items": [
            "On Windows, suravidl no longer opens a console window beside the app \u2014 launches are quiet from the first double-click.",
            "The quick black flickers go too: when yt-dlp merges a video, or a yt-dlp update runs, helper processes stay invisible.",
            "And if something ever goes wrong at boot, the trail now lands in a log file beside the app data (app.log in the suravidl folder) instead of nowhere.",
        ],
    },
    {
        "version": "0.39.0",
        "title": "The doorman",
        "items": [
            "The extension got a front door: it names what a page is playing in plain words, and one button hands it to suravidl \u2014 the format list opens in the app, ready for you to pick the quality.",
            "A page that offers several streams gets a quiet choice first (playlist or video) \u2014 not a wall of links. The extension stays a doorman; the work stays in the engine.",
            "For this the engine catches a browser-handed stream: it reads the link itself, with the page's request details, and keeps those details engine-side \u2014 reads show the video, never the credentials.",
            "When a handoff arrives, the suravidl window comes to the front \u2014 so the quality picker is already where you are looking.",
        ],
    },
    {
        "version": "0.38.8",
        "title": "The trust bundle",
        "items": [
            "Update checks work on macOS again: a packaged Mac app was asking the system for a list of trusted certificates that packaged apps never get — suravidl now brings its own, so Check now answers on the first try.",
            "The same repair reaches the link inspector \u2014 scanned video links on https verify properly on every platform.",
            "If a certificate check ever fails again, the update row explains it in plain words and opens the releases page for you.",
        ],
    },
    {
        "version": "0.38.7",
        "title": "The tuck",
        "items": [
            "The minimize button tucks suravidl away instead of parking it in the Dock — on macOS a menu-bar icon keeps \"Show suravidl\" a click away, and Windows and Linux get a tray icon.",
            "If the app ever sits still, Settings → Appearance now names the reason — for instance your system asking for reduced motion — and where to change it.",
        ],
    },
    {
        "version": "0.38.6",
        "title": "The straight answer",
        "items": [
            "Failure summaries no longer guess wrong: the short line follows the engine's own verdict, and unsupported links always say: open it in the browser, press play, then Scan.",
        ],
    },
    {
        "version": "0.38.5",
        "title": "The fold",
        "items": [
            "A finished download's card now folds open and shut — the receipt grows and shrinks instead of popping, and once it's open the short /stor… path next to the buttons steps aside for the full one.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
