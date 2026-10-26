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
        "version": "0.47.17",
        "title": "The hoist",
        "items": [
            "The phone's Settings no longer shows an ffmpeg row that could only ever say \"checking…\" — the code meant to hide it ran before its own helper existed, so it crashed silently.",
            "If the check really fails on a desktop, the row now says so instead of spinning forever.",
        ],
    },
    {
        "version": "0.47.16",
        "title": "The catch",
        "items": [
            "The phone build's new guard stopped its own release: it looked for a string every build carries. It now looks only for the downloader's own code, so the update installs again.",
            "Impersonation now refuses honestly: if the installed curl_cffi is a version yt-dlp cannot use, Settings says so instead of failing at download time.",
        ],
    },
    {
        "version": "0.47.15",
        "title": "The spare",
        "items": [
            "The phone no longer carries the desktop's ffmpeg downloader at all — its ffmpeg already sits inside the app, so that part was only ever useful on a Mac or a PC.",
        ],
    },
    {
        "version": "0.47.14",
        "title": "The seal",
        "items": [
            "An update is now installed only when it is signed by the same key as the app you already have — a hijacked download can no longer hand Android a different app.",
            "The in-app browser no longer treats two different sites under co.uk, com.au, github.io and friends as one site, and a downloaded file can only be handed to another app from the downloads folder.",
            "On the phone, Settings no longer offers an ffmpeg download that could never work there — the app already carries its own.",
        ],
    },
    {
        "version": "0.47.13",
        "title": "The fetch",
        "items": [
            "ffmpeg is no longer something you have to know about: Settings shows whether one is reachable and downloads a pinned static build when it isn't — the join video+audio step and every audio conversion need it.",
        ],
    },
    {
        "version": "0.47.12",
        "title": "The whole",
        "items": [
            "On a machine without ffmpeg the default pick is now the best stream that is already whole, instead of a video+audio pair it could never join — and a Homebrew ffmpeg is found even when the app was opened from Finder.",
        ],
    },
    {
        "version": "0.47.11",
        "title": "The sheet",
        "items": [
            "The extension's engine page — where the address and token go — now looks like the app it belongs to, with Show/Hide on the token. The browser extension is 0.5.19.",
        ],
    },
    {
        "version": "0.47.10",
        "title": "The trim",
        "items": [
            "A finished row says COMPLETED once — the FILED stamp repeated it on exactly the same rows. And the red dot beside YouTube rows is gone: the host is already printed in the line.",
        ],
    },
    {
        "version": "0.47.9",
        "title": "The ghost",
        "items": [
            "The phone app sweeps its own abandoned gallery imports at every start: a killed copy left an invisible file that managers counted but never showed (an 'empty' folder claiming 18 items, 516 MB).",
        ],
    },
    {
        "version": "0.47.8",
        "title": "The path",
        "items": [
            "Restart & Install starts PowerShell by its exact system path now — on one machine the bare name could not be found (WinError 2), so a verified update never began. The update log records the path it tried.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
