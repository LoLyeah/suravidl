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
    {
        "version": "0.40.6",
        "title": "The tally",
        "items": [
            "The queue shows outside the window: the Dock wears a count badge on macOS, Linux docks that speak the launcher protocol get one too, and other desktops carry the count in the window title.",
            "A read that fails is silence \u2014 the badge holds its last truth rather than flashing a false zero.",
        ],
    },
    {
        "version": "0.40.5",
        "title": "The fill",
        "items": [
            "Quality chips now say what each pick will weigh when the site publishes sizes \u2014 the streams' own numbers, added the way the pick works. No sizes published, no claims made.",
            "The batch line counts out loud as you paste: how many links, and how many lines it skipped \u2014 one link is one link, and the button only appears when there is really a batch.",
        ],
    },
    {
        "version": "0.40.4",
        "title": "The marks",
        "items": [
            "The player can set your clip now: Mark in and Mark out write the player's own clock into the clip fields \u2014 cut a section from what you are watching, not from a time typed by memory.",
            "The marks appear for video players only; an audio file has no picture to cut from.",
        ],
    },
]


def payload() -> dict:
    """What the UI's one-time card renders: the engine version + the notes."""
    return {"version": __version__, "entries": list(ENTRIES)}
