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
    {
        "version": "0.39.7",
        "title": "The bouncer",
        "items": [
            "The phone app\u2019s built-in browser refuses to be bounced: an off-site redirect or pop-up mid-hunt is stopped cold \u2014 the page and the find list stay put. A refused hop is named and one tap from following.",
            "Classic ad networks no longer load at all in there \u2014 a short deny list serves them empty, which is exactly what they deserve.",
            "The engine no longer lets a fussy notification take it down on start: the mark it wears is dress-up, so a modern Android that dressed it differently gets a graceful fallback, not a dead engine.",
        ],
    },
    {
        "version": "0.39.6",
        "title": "The shelf",
        "items": [
            "The bottom bar stands in the flow now, like the header \u2014 on Android that is what makes it frost the content scrolling underneath instead of showing it crisp. Same glass, same pin at the thumb.",
            "The engine notification carries suravidl\u2019s own mark at last: a white take-arrow in the status line and the pine tile beside it \u2014 drawn from this build, not the system\u2019s generic download glyph.",
        ],
    },
    {
        "version": "0.39.5",
        "title": "The frost",
        "items": [
            "The tour\u2019s caption card now wears the same frosted glass as every dialog \u2014 a real-compositor shot caught the page reading through it, and it was re-shot to prove the fix.",
        ],
    },
    {
        "version": "0.39.4",
        "title": "The welcome mat",
        "items": [
            "The footer row, under the download path, gained two doors: FAQ answers the common questions \u2014 cookies, \u201cunsupported URL\u201d, missing 4K, where files go \u2014 and a short tour walks the room, replayable any time.",
            "Probing a playlist now offers the whole thing by default (\u201call 3 \u00b7 Download playlist\u201d) instead of landing on \u201cnone picked\u201d with a dead button; un-ticking everything by hand still refuses politely.",
        ],
    },
    {
        "version": "0.39.3",
        "title": "The hem",
        "items": [
            "The filed-takes rail keeps its contents inside itself now. Its file line shows just the name \u2014 a Windows path used to arrive whole, slide out of the rail and bleed through the glass onto the neighbouring card's title.",
            "Long names shorten politely at the rail's edge, and nothing filed in the rail can paint outside it.",
        ],
    },
    {
        "version": "0.39.2",
        "title": "The lantern",
        "items": [
            "If another program is using suravidl's usual port when the app starts, the app now steps one port over instead of vanishing somewhere random \u2014 and the browser extension knows to look there.",
            "The Firefox extension searches those neighbouring ports before it ever says \"suravidl isn't running\" \u2014 a running app is found whether it sits on its usual port or one step beside it.",
            "Engine checks no longer depend on the exact shape of the browser's own extension address, so a browser update cannot quietly cut the popup and the app apart.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
