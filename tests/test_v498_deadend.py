"""v0.49.8 "the dead end" — the gate reads the verdict, not one raw spelling.

v0.49.6 only believed two spellings: `detail.unsupported` and the literal
"Unsupported URL". Every other dead end — a page whose player yt-dlp cannot
read, a TikTok photo post, a media server that wants the page it came from, a
Reddit /s/ shortcut — kept "Download now" live, so the app offered a button its
own sentence said could not work.

The rule is now the rendered line: if the card sends you to the browser, the
start controls are off. Comparing through t() keeps it true in Indonesian too.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.49.8" and e["title"].lower() == "the dead end"
               for e in ENTRIES)


def test_every_browser_only_verdict_is_listed():
    block = APP[APP.index("const BROWSER_ONLY = ["):]
    block = block[:block.index("];")]
    for sentence in (
        "no extractor knows this page",
        "this page has a player yt-dlp cannot read",
        "slideshow with music",
        "media server refuses requests that do not come from its page",
        "Reddit share links",
    ):
        assert sentence in block, sentence
    assert block.count('"') // 2 == 7


def test_a_retryable_failure_stays_live():
    block = APP[APP.index("const BROWSER_ONLY = ["):]
    block = block[:block.index("];")]
    # a 403, a plain 404 and a TLS failure are "could not read it now"
    assert "403" not in block and "certificate" not in block.lower()


def test_the_gate_reads_the_rendered_sentence():
    assert "function browserOnlySay(said)" in APP
    assert "BROWSER_ONLY.some((k) => said === t(k))" in APP
    assert 'browserOnlySay($("probeSay").textContent.trim())' in APP


def test_the_reddit_sentence_can_actually_appear():
    # humanErr keys that arm on the link too; the probe used to call it without
    assert 't(humanErr(msg, detail, url))' in APP
    assert 't(humanErr(e.message, e.detail, it.url))' in APP


def test_the_reason_names_the_platforms_own_route():
    # the phone scans, the desktop hands over with the extension
    assert "open it in the browser, press play, then Scan" in APP
    assert "open it in the browser, then hand the stream over with the extension" in APP
    assert "tautan ini tidak bisa dibaca di sini" in APP
