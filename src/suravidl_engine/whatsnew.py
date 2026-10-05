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
        "version": "0.45.2",
        "title": "The measure",
        "items": [
            "The settings deck stopped changing size: its width followed whichever panel was open \u2014 every tab now keeps the deck\u2019s full measure.",
            "The Save strip frosts what scrolls beneath it \u2014 rows passing under the bar read as a smudge now, not a list.",
        ],
    },
    {
        "version": "0.45.1",
        "title": "The pane",
        "items": [
            "The menus wear the app\u2019s skin now: dropdowns drew the operating system\u2019s own chrome on macOS \u2014 bezel and double-chevron \u2014 and now draw their own edge and caret like every other control.",
            "The macOS room lets a little more of the desktop through: the page\u2019s wash eased a step on all three themes, still holding the text-contrast floor.",
        ],
    },
    {
        "version": "0.45.0",
        "title": "The ledger",
        "items": [
            "The queue grew bulk actions: clear everything finished, or retry everything failed, in one move \u2014 the counts sit right above the list, and clearing asks once.",
            "The verbose switch has a reader now: a Log card in the yt-dlp tab shows the last lines yt-dlp said, ready to copy. Turn Verbose log on for the deep one.",
            "Settings keeps its promises: the sub-tabs take arrow keys, the appearance swatches say what is selected, and Test cookies checks what you typed without quietly saving the rest of the form.",
            "The browser extension speaks Bahasa Indonesia too, following your browser\u2019s language \u2014 and the API token moved to Settings \u2192 Authentication, where its Copy button now lives.",
        ],
    },
    {
        "version": "0.44.0",
        "title": "The phrasebook",
        "items": [
            "The whole interface speaks Bahasa Indonesia now \u2014 switch in Settings \u2192 Appearance \u2192 Language and every button, tab, toast and confirmation answers in Indonesian on the spot. English stays the default.",
            "Also fixed: a faint 1px line sat above the top bar on desktop windows once you scrolled to the top. The bar meets the window chrome cleanly now.",
        ],
    },
    {
        "version": "0.43.4",
        "title": "The level",
        "items": [
            "Fixed: a toast clearing the settings Save strip floated a full row too high \u2014 over the Updates text you were reading. It now lands a breath above whatever is docked, exactly where it should.",
        ],
    },
    {
        "version": "0.43.3",
        "title": "The stitch",
        "items": [
            "The macOS self-update now stages its download in a fresh, private folder instead of a predictable name \u2014 a planted file can no longer stand where the update lands.",
            "The threat model now states it plainly: link-local and cloud-metadata addresses are refused at every door, with DNS-level tricks the one named, deliberate exception.",
        ],
    },
    {
        "version": "0.43.2",
        "title": "The rake",
        "items": [
            "Hardening pass: link-local and cloud-metadata addresses are refused everywhere \u2014 pasted, handed over from the browser, or queued as a download \u2014 with a plain reason.",
            "The download queue has a ceiling now, and oversized requests bounce before they are read: a runaway script cannot grow either without bound.",
            "Multi-select downloads from the browser extension carry each file's captured headers now, like the single download always did.",
            "Remove downloaded copy, while that copy is the one running, is applied on the next start \u2014 the tab says so instead of the files vanishing mid-session.",
            "Windows self-updates run through one opaque command: special characters in usernames or folders can no longer break the installer chain. Settings and token files are born owner-only.",
        ],
    },
    {
        "version": "0.43.1",
        "title": "The undo",
        "items": [
            "The downloaded yt-dlp can be removed again from its tab \u2014 a staged copy is canceled on the spot, and an active one hands back to the bundled copy from the next start.",
            "The tab now says where the running copy comes from: (bundled) or (downloaded) \u2014 no guessing which one is in use.",
        ],
    },
    {
        "version": "0.43.0",
        "title": "The refresh",
        "items": [
            "The yt-dlp button works on every build now: packaged installs (Windows, macOS, Linux, Android) fetch the newest release straight from PyPI, verify it, and apply it on the next start \u2014 no app update needed.",
            "The newer copy is the one that runs \u2014 and if an app update ever ships something even newer, that wins instead. A staged update says \"restart to use it\" until it is live.",
        ],
    },
    {
        "version": "0.42.1",
        "title": "The glide",
        "items": [
            "Motion polish all through the app: the armed strip folds instead of pushing the formats table down, subtitle picks and tab dots glide in, and the queue's filter eases rows out instead of jumping them.",
            "The FAQ folds like the download card; modal exits are quick where they lingered; and timer fallbacks now respect your system's reduced-motion setting everywhere.",
            "Housekeeping: a downloaded update file is deleted the moment it is spent \u2014 right after a self-update on Windows and macOS, and on the next launch on Android.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
