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
        "version": "0.45.8",
        "title": "The reach",
        "items": [
            "Expanding a queue card no longer needs a tap on one word at the top left — the whole card folds and unfolds it now, everything except the buttons and links that do their own thing.",
            "The card reads as tappable everywhere, and the keyboard path is unchanged: Tab to the title, then Enter or Space.",
        ],
    },
    {
        "version": "0.45.7",
        "title": "The sound",
        "items": [
            "TikTok picks could end with the sound dying at 1:00 — the site serves the video’s music as its own file, often a 60-second preview, and it was being used as the soundtrack. Picks now take the video’s own complete audio.",
            "For those videos that means the single complete copy with its real soundtrack; nothing else about the presets changes.",
        ],
    },
    {
        "version": "0.45.6",
        "title": "The cover",
        "items": [
            "Covers that arrive without a usable file extension \u2014 TikTok\u2019s end in \u201c.image\u201d \u2014 no longer break a download with thumbnails turned on: the file\u2019s own bytes decide its name, so it converts and embeds cleanly.",
            "That was the \u201cError opening output files: Invalid argument\u201d wall those downloads ended on; the fix rides the desktop and the phone alike.",
        ],
    },
    {
        "version": "0.45.5",
        "title": "The disguise",
        "items": [
            "TikTok\u2019s \u201cunexpected response\u201d refusal is retried with a different browser identity each attempt \u2014 a refused fetch no longer repeats itself into the same wall.",
            "The first attempt stays exactly what you configured; only the retries step aside \u2014 and only for TikTok\u2019s challenge, never for a real error.",
        ],
    },
    {
        "version": "0.45.4",
        "title": "The answers",
        "items": [
            "Every FAQ entry sits on its own glass card now \u2014 the same material as every popup \u2014 and the answers learned the current app: where updates live, how to pair the extension, and where the log hides when a download fails.",
            "Where things live, corrected: the updater is at Settings \u2192 General, and the cookies and the pairing token at Settings \u2192 Authentication.",
        ],
    },
    {
        "version": "0.45.3",
        "title": "The summons",
        "items": [
            "The tour card\u2019s blur and transparency is the standard for every popup: the room behind a dialog dims but stays sharp, and the popup is the room\u2019s only frosted glass \u2014 nothing behind it smears flat anymore.",
            "It\u2019s lighter on the machine too \u2014 one less full-screen blur pass rides every dialog.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
