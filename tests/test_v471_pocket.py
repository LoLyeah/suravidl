"""v0.47.1 "the pocket" — the phone's sniffer lifts the key too.

The desktop extension learned to read a scrambled player's decode key
(window.__pk) in v0.47.0; the phone kept only half the feature — the
engine in the APK could eat a keyed job, but the in-app browser had no
way to capture one. This round closes that: the injected script (which
already runs in the page) reads the key, the bridge carries it under the
same token rule as every find, and the handoff rides it to the engine,
which validates it against the stream.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KT = ROOT / "android/app/src/main/java/com/suravidl/app"


def test_the_phone_sniffer_lifts_the_key():
    """Source pins: the injected script reads window.__pk and posts it;
    the bridge carries it under the find rule; the handoff rides it."""
    script = (KT / "SniffScript.kt").read_text()
    assert "window.__pk" in script and "B.pk" in script
    activity = (KT / "BrowserActivity.kt").read_text()
    assert "fun pk(" in activity and "sniffPk" in activity
    assert ("downloadWhenReady(engineOrigin(), token, c.url, headers, sniffPk)"
            in activity)
    handoff = (KT / "Handoff.kt").read_text()
    assert 'put("xor_key"' in handoff
    assert 'xorKey: String = ""' in handoff, \
        "the doors keep their positional shape — new params go last"


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__, whatsnew

    assert __version__ == "0.47.1"
    top = whatsnew.ENTRIES[0]
    assert top["version"] == "0.47.1"
    assert top["title"].lower() == "the pocket"
    assert len(whatsnew.ENTRIES) == 10
