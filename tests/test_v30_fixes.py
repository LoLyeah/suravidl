"""The browser refuses the app hand-off — and says so (v0.30.0).

The 2026-09-28 report, second half: a TikTok page inside "Find a video on a
page" navigated itself to `snssdk1180://aweme/detail/<id>` — TikTok's own
"open our app" move. Nothing refused it, so the navigation died half-way:
the scheme URL stuck in the address bar, the find list wiped, the page blank
(the screenshot the user sent). The engine side that day was innocent — the
probe runs yt-dlp directly and never touches this browser; its failure was
TikTok's known intermittent rate-limiting, reproduced 3/3 green from the
server the same hour.

What this pins: every door into the WebView refuses a non-web scheme BEFORE
the navigation starts, and the refusal is spoken on screen instead of dying
silently. The behavioral proof runs on the emulator images — SnifferTest
fires `snssdk1180://` from a live page and asserts the browser stays put;
these are the static halves that keep the wiring honest in between runs.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLIENT = (ROOT / "android/app/src/main/java/com/suravidl/app/SnifferWebViewClient.kt").read_text()
BROWSER = (ROOT / "android/app/src/main/java/com/suravidl/app/BrowserActivity.kt").read_text()
SNIFFER_TEST = (ROOT / "android/app/src/androidTest/java/com/suravidl/app/SnifferTest.kt").read_text()


# -- 1. the WebView client refuses non-web schemes ---------------------------

def test_the_webview_client_refuses_non_web_schemes():
    assert "shouldOverrideUrlLoading" in CLIENT, \
        "without the override the navigation is let through and dies half-way"
    assert "isWebUrl" in CLIENT, \
        "one shared definition of 'a web page' — used by every door"
    seg = CLIENT.split("override fun shouldOverrideUrlLoading")[1][:700]
    assert "onAppLinkBlocked" in seg, \
        "a refusal nobody hears is the old silent blank page again"
    assert "return true" in seg, \
        "returning false hands the scheme back to the WebView — the bug"


# -- 2. the refusal is said out loud -----------------------------------------

def test_the_refusal_note_has_its_own_line_and_its_own_tag():
    assert 'tag = "app-handoff-note"' in BROWSER, \
        "an untagged view is untestable on the device"
    assert "app link refused" in BROWSER, "the note's own words"
    assert "only web pages load here" in BROWSER, \
        "the note must say what the rule is, not just that something happened"
    assert "handoffNote.visibility = View.GONE" in BROWSER, \
        "the next real page hides the note — it was about the page before"
    assert "setOnClickListener { handoffNote.visibility = View.GONE }" in BROWSER, \
        "tap to hide, like the sign-in hint"


# -- 3. every door shares the one rule ---------------------------------------

def test_every_door_refuses_a_scheme():
    load_seg = BROWSER.split("private fun load(")[1][:500]
    assert "isWebUrl" in load_seg, \
        "the popup (target=_blank) and new-intent doors end up in load()"
    go_seg = BROWSER.split("private fun go(")[1][:600]
    assert "isWebUrl" in go_seg, \
        "a pasted app link must be named, not mangled into a fake https URL"


# -- 4. the emulators prove the behavior -------------------------------------

def test_the_sniffer_suite_proves_the_refusal_on_the_device():
    assert "theBrowserRefusesAnAppHandOffAndSaysSo" in SNIFFER_TEST, \
        "the static checks are decoration without an on-device assertion"
    assert "app-handoff-note" in SNIFFER_TEST, "the test reads the tagged view"
    assert "snssdk1180://" in SNIFFER_TEST, \
        "fire the exact scheme the user hit"
