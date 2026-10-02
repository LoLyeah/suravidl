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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
