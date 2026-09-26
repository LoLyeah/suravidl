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
    assert "!hidden.containsKey(it.url)" in browser, "hidden means hidden"
    assert "fragments belong to a playlist above" in browser, \
        "hiding must be visible, not silent"
