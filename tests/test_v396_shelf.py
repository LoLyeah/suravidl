"""v0.39.6: the shelf — the bottom bar joins the glass the header wears, and
the notification carries suravidl's own mark.

Why (2026-10-02, two reports from the phone):
1. "the top bar has beautiful blur — why doesn't the bottom bar?" Because on
   this WebView the backdrop pass composites in flow but not for fixed layers
   over scrolling content (the transport learned this first). The bar was the
   one fixed layer left; it now stands in flow, sticky at the document's end.
2. "why is the notification still using the old logo?" The big tile there is
   whatever icon the phone keeps for the app. The notification now sets its
   own: a white take-arrow as the small icon (path pinned to the master below)
   and the pine tile as the large icon — both from the build's own resources.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src" / "suravidl_engine" / "web"
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()
KOTLIN = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
          "suravidl" / "app" / "EngineService.kt").read_text()
DRAWABLE = (ROOT / "android" / "app" / "src" / "main" / "res" / "drawable" /
            "ic_stat_suravidl.xml").read_text()
MASTER = (ROOT / "assets" / "brand" / "arrow-cream.svg").read_text()


def test_the_bar_stands_in_flow_at_the_documents_end():
    """Source order: it is the last thing (after main); the wide screen
    re-orders it back under the header, the phone pins it at the thumb."""
    assert HTML.index("</main>") < HTML.index('id="tabs"') < HTML.index("<footer")
    assert "display: flex; flex-direction: column; min-height: 100vh;" in CSS
    assert ".tabs { order: 2; }" in CSS
    assert "position: sticky; bottom: 0; z-index: 40;" in CSS
    assert "order: 4;\n    position: sticky" in CSS      # the phone's slot
    assert "margin-top: auto;" in CSS
    assert "position: fixed; left: 0; right: 0; bottom: 0; z-index: 40;" not in CSS


def test_the_notification_carries_our_mark():
    assert "setSmallIcon(R.drawable.ic_stat_suravidl)" in KOTLIN
    assert KOTLIN.count("setLargeIcon(notifLogo)") == 2
    assert "stat_sys_download" not in KOTLIN
    assert 'android:fillColor="#FFFFFFFF"' in DRAWABLE
    assert 'android:fillType="evenOdd"' in DRAWABLE


def test_the_notification_glyph_is_the_masters_arrow():
    """The drawable's path must BE the master's path — brand art comes from
    the masters, and a test keeps a future edit from quietly drifting."""
    master_path = re.search(r'<path d="([^"]+)"', MASTER).group(1)
    drawable_path = re.search(r'android:pathData="([^"]+)"', DRAWABLE).group(1)

    def squash(s):
        return re.sub(r"\s+", " ", s).strip()

    assert squash(drawable_path) == squash(master_path)
