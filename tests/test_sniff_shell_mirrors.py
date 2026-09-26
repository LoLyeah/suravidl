"""Each shell prefilters with a copy of the engine's media-pattern list.

The list deliberately exists more than once: the engine's `/sniff/patterns` (the
source of truth), the extension's fallback (it fetches the engine's list; the
copy only stands when the engine is not answering), and the Android browser's
baked-in fallback. The rule that keeps that honest is a *subset* relation: a
shell may look at fewer URLs than the engine can name, never at URLs the engine
does not know — a miss costs a candidate, a wrong shape costs trust. The
extension half is pinned in test_classify.py and test_extension_sniff.py; this
is the browser's.
"""
import re
from pathlib import Path

from suravidl_engine.classify import MEDIA_EXT, URL_HINTS

ROOT = Path(__file__).parent.parent
KOTLIN = ROOT / "android/app/src/main/java/com/suravidl/app/Sniff.kt"
MAIN = ROOT / "android/app/src/main/java/com/suravidl/app/MainActivity.kt"
BROWSER = ROOT / "android/app/src/main/java/com/suravidl/app/BrowserActivity.kt"
HTML = ROOT / "src/suravidl_engine/web/index.html"
JS = ROOT / "src/suravidl_engine/web/app.js"


def _kotlin_list(source: str, name: str) -> list:
    block = source.split(f"val {name} = listOf(")[1].split(")")[0]
    return re.findall(r'"([^"]+)"', block)


def test_the_browser_prefilter_stays_inside_the_engine_list():
    src = KOTLIN.read_text()
    ext = _kotlin_list(src, "FALLBACK_EXT")
    hints = _kotlin_list(src, "FALLBACK_HINTS")
    assert ext and hints, "the baked-in fallback list vanished"
    unknown_ext = [e for e in ext if e not in MEDIA_EXT]
    assert not unknown_ext, \
        f"the browser bakes in extensions the engine does not know: {unknown_ext}"
    known_hints = [h.lower() for h in URL_HINTS]
    unknown_hints = [h for h in hints if h.lower() not in known_hints]
    assert not unknown_hints, \
        f"the browser bakes in hints the engine does not know: {unknown_hints}"
    # and the engine's list is still the one the browser fetches at start
    assert "/sniff/patterns" in src, "the browser must prefer the engine's list"


def test_the_browser_entry_point_exists_and_asks_the_host():
    html = HTML.read_text()
    js = JS.read_text()
    browser = BROWSER.read_text()
    assert 'id="sniffBtn"' in html and 'id="sniffRow"' in html
    assert "sniffRow" in js and "sniffBtn" in js
    assert "AndroidHost.openBrowser" in js, \
        "the button must ask the host — desktop has no such browser"
    assert "openBrowser" in MAIN.read_text(), "the host has to implement it"
    assert "BrowserActivity::class.java" in MAIN.read_text()
    # the browser itself: not exported, and it carries the sniffer
    manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text()
    assert 'android:name=".BrowserActivity" android:exported="false"' in manifest
    assert "SnifferWebViewClient" in browser
    assert "addJavascriptInterface" in browser and "SuravidlSniff" in browser


def test_the_browser_hides_fragments_only_on_the_engines_word():
    """M4: the shape rule is the engine's, so the phone and the extension hide
    the same rows — and a shell that cannot get an answer hides nothing."""
    browser = BROWSER.read_text()
    handoff = (ROOT / "android/app/src/main/java/com/suravidl/app/Handoff.kt").read_text()
    assert '"/sniff/rank"' in handoff, "the browser must ask the engine"
    assert "Handoff.rank(" in browser
    # and it must actually *ask*, on every new list — a defined function that is
    # never reached is exactly the decoration this project refuses
    assert browser.count("rankIfNeeded(") >= 2, "the rule must be asked, not only defined"
    assert "!hidden.containsKey(it.url)" in browser, "hidden means hidden"
    assert "fragments belong to a playlist above" in browser, \
        "hiding must be visible, not silent"


def test_the_injected_hooks_cannot_be_swapped_by_the_page():
    """The source has to live on the window (a script cannot quote its own final
    form into child frames), so it is defined un-swappable instead of assigned —
    a page must not be able to make our injector eval its payload into its own
    same-origin frames."""
    script = (ROOT / "android/app/src/main/java/com/suravidl/app/SniffScript.kt").read_text()
    assert "Object.defineProperty(window, '__svSniffSrc'" in script
    assert "writable: false, configurable: false" in script
    assert "Object.defineProperty(window, '__svSniffDoc'" in script


def test_a_download_button_carries_the_url_it_belongs_to():
    """The row's Download chip is tagged with its URL, so an instrumented test
    can prove the button exists for a find instead of only that the code does."""
    browser = BROWSER.read_text()
    assert 'chip("Download", "download:" + c.url)' in browser
    test_src = (ROOT / "android/app/src/androidTest/java/com/suravidl/app/"
                "SnifferTest.kt").read_text()
    assert '"download:" + ' in test_src, "the tag must be looked for on device"


def test_clearing_browsing_data_clears_the_finds_too():
    """Leaving the URLs of a sensitive session on screen would defeat the whole
    gesture."""
    browser = BROWSER.read_text()
    block = browser.split("private fun clearBrowsingData()")[1].split("private fun")[0]
    assert "SniffLog.clear()" in block
    assert "info.clear()" in block
    assert "list of finds above" in block, "and the confirm must say so"


def test_the_players_own_source_is_evidence_not_a_guess():
    """An extension-less stream cannot match any pattern — a real site served
    one (`mp4-06.overfetch.video/<id>`, no extension, another host, inside a
    same-origin player frame). The prefilter exists to keep *network noise*
    out, so a media element's own source is reported as it is and the engine
    classifies it before a row is drawn. Proven on device in `SnifferTest`;
    this pins the wiring."""
    script = (ROOT / "android/app/src/main/java/com/suravidl/app/SniffScript.kt").read_text()
    assert "function rep(u, via, direct)" in script
    assert "if (!direct && !P(u) && via !== 'mse') return;" in script
    assert "rep(s, 'player', true)" in script, "the DOM source must not be filtered"
    assert "rep(s, 'mse', true)" in script
    assert "rep(u, 'player', true)" in script, "the src setter must not be filtered"


def test_a_second_link_reaches_the_browser_that_is_already_open():
    """The activity is singleTask: without an onNewIntent override a second
    "Open in the browser" was dropped on the floor while the user kept scanning
    the previous page."""
    browser = BROWSER.read_text()
    assert "override fun onNewIntent(" in browser
    body = browser.split("override fun onNewIntent(")[1].split("// -- chrome")[0]
    assert "getStringExtra(EXTRA_URL)" in body, "the new link must be read there"
    assert "load(url)" in body, "and loaded"
