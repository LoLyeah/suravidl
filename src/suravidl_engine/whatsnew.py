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
    {
        "version": "0.42.0",
        "title": "The crossing",
        "items": [
            "macOS joins the self-updating line: suravidl checks, downloads and verifies the new version \u2014 then one tap swaps the app in place and reopens it. No more dmg trips.",
            "The swap is guarded: a copy running from the download image or a folder it cannot write says so in words, and a failed swap rolls back to the version you have.",
        ],
    },
    {
        "version": "0.41.1",
        "title": "The delivery",
        "items": [
            "Releases are full releases again \u2014 the update feed is live: suravidl fetches the next version itself, verifies it, and installs it in place with one tap. No more release-page trips.",
            "First stable release of the self-updating line: install the Windows setup or the Android APK once, and every version after this arrives in-app.",
            "Polish pass: an update download can be cancelled mid-flight, a failed update says so wherever you are, and the ready notice carries the install button.",
        ],
    },
    {
        "version": "0.41.0",
        "title": "The courier",
        "items": [
            "Windows gets a real installer: per-user, no admin prompts, a Start Menu entry and a proper uninstall in Windows Settings \u2014 the portable exe stays for anyone who prefers it.",
            "The app updates itself now: check, download, verify by checksum \u2014 then one tap to install (Windows restarts into it; Android shows its own single confirmation). No more release-page trips.",
        ],
    },
    {
        "version": "0.40.11",
        "title": "The shelf",
        "items": [
            "The in-app find-a-video browser's status line got its own full-width row \u2014 on narrow phones five buttons used to squeeze it to one letter per line: a tall stack of letters with the buttons floating in its middle.",
            "The button row (ads \u00b7 site \u00b7 Scan \u00b7 Clear list \u00b7 Clear data) slides sideways when your screen is too narrow, so no control runs out of reach.",
        ],
    },
    {
        "version": "0.40.10",
        "title": "The mend",
        "items": [
            "Two fresh-eyes audits went through the whole app; the sharpest fix: trashing the leftover card of a paused-and-resumed download no longer risks the finished file.",
            "Keyboard and touch on the deck: dialogs keep Tab inside and hand focus back, the main tabs answer to arrow keys, the day theme's focus ring is visible again, and small tap targets grew.",
            "The raw-arguments deny list learned the flags it was missing, and a bundled build now says where yt-dlp updates come from instead of failing quietly.",
        ],
    },
    {
        "version": "0.40.9",
        "title": "The front door",
        "items": [
            "suravidl can put itself in your menu now: run the release binary once with --install-desktop and it appears like an installed app \u2014 Start Menu on Windows, applications menu on Linux.",
            "No admin rights, nothing outside your own folders, and --uninstall-desktop takes it back out; installing never starts the engine or opens a window.",
        ],
    },
    {
        "version": "0.40.8",
        "title": "The swarm",
        "items": [
            "Everything the project checks now runs on all the machine's cores at once \u2014 the same careful checks in a fraction of the time, so fixes and features reach you sooner.",
        ],
    },
    {
        "version": "0.40.7",
        "title": "The handful",
        "items": [
            "The extension popup's stream list is a checkbox list now \u2014 tick several finds and the quick door queues them all at best quality in one go.",
            "Right-click any link, video, or page for \"Download with suravidl\" \u2014 straight to the app's quality picker, no trip through the toolbar.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
