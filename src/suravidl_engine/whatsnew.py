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
        "version": "0.47.25",
        "title": "The dissolve",
        "items": [
            "Tab switches now leave the frosted plates alone and dissolve only what sits on them: the blur never blinks, and the pinned bars no longer stay bright while everything else fades.",
        ],
    },
    {
        "version": "0.47.24",
        "title": "The wash",
        "items": [
            "Switching tabs no longer blanks the frosted blur for the length of the fade and snaps it back at the end — the arrival is a wash that clears while the glass keeps its blur.",
        ],
    },
    {
        "version": "0.47.23",
        "title": "The report",
        "items": [
            "A video whose server forgets its intermediate certificate now plays in the in-app browser: media only, and only for an untrusted chain — with a note on screen. Expired or mismatched certificates are still refused.",
            "The browser also says why a resource failed (network, HTTP status or certificate) instead of leaving a spinner with no answer.",
        ],
    },
    {
        "version": "0.47.22",
        "title": "The redo",
        "items": [
            "\"Retry without certificate check\" now keeps the page the link came from — without it the site refused the file again and the row looked like it had not changed.",
            "The in-app browser can start a video after you tap play even when the page's player calls play() from its own script, which Android's WebView blocks by default.",
            "An incomplete certificate chain is no longer called \"self-signed\": they are different problems with different fixes.",
        ],
    },
    {
        "version": "0.47.21",
        "title": "The layer",
        "items": [
            "A failed download now names the layer that broke — the name does not resolve, the port refused, the handshake failed, or the server accepted and stalled — instead of only \"the site never answered in time\".",
        ],
    },
    {
        "version": "0.47.20",
        "title": "The witness",
        "items": [
            "A failed download now says what actually went wrong — an expired certificate, a self-signed server, a host that no longer exists — instead of blaming a proxy every time.",
            "A certificate failure offers \"retry without certificate check\" for that one job, and a failed row shows the file's name rather than the whole address.",
            "The fold caret no longer disappears from a row after the first progress poll — the title rewrite was deleting it.",
            "A stream that plays in Chrome but failed in the app now works: the engine trusts the device's own certificate store, not only the list bundled with Python.",
            "A site whose server forgets to send its intermediate certificate now downloads like it plays in a browser: the missing CA is fetched and the job retried.",
        ],
    },
    {
        "version": "0.47.18",
        "title": "The twin",
        "items": [
            "Deleting one video no longer takes a same-named twin with it: the trash removes exactly the copy that row made, instead of every file sharing its name.",
        ],
    },
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
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
