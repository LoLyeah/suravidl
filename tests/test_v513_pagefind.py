"""v0.5.13 — the page side: the extension reads the player itself.

Field doctrine (docs/SNIFFING.md): "What the player itself asks for is
evidence." The network listeners see requests; a <video>/<source> the
player has not asked for yet — and any stream served from a URL with no
extension at all — are invisible there, and a miss on the second costs
the user a video (mp4-06.overfetch.video served one with no extension).
The content script ports the phone's layer: element sweep, a timeline
scan for what ran before it loaded, and an observer for late players.
It runs in the isolated world, so the page can never forge a find; blob
and data sources are never listed — proof of streaming, not a download.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_both_manifests_carry_the_page_script():
    for rel in ("extension/manifest.json", "extension/firefox/manifest.json"):
        m = json.loads((ROOT / rel).read_text())
        cs = m.get("content_scripts") or []
        assert len(cs) == 1, rel
        block = cs[0]
        assert block["js"] == ["pagefind.js"], rel
        assert block["run_at"] == "document_start", rel
        assert block["all_frames"] is True, rel
        assert "<all_urls>" in block["matches"], rel


def test_the_page_script_sweeps_the_player_and_reports():
    src = (ROOT / "extension/pagefind.js").read_text()
    assert '"video, audio, source"' in src
    assert 'type: "pageFind"' in src
    assert "MutationObserver" in src
    assert "getEntriesByType" in src
    # never listed: proof of streaming, not a fetchable URL
    assert "blob|data|mse" in src


def test_the_background_only_accepts_reports_with_a_sender_tab():
    src = (ROOT / "extension/background.js").read_text()
    i = src.index('msg.type === "pageFind"')
    window = src[i:i + 700]
    assert "_sender && _sender.tab" in window
    assert "remember(tabId" in window
