"""v0.39.4: the welcome mat — FAQ + tutorial in the footer row, and a fresh
playlist probe that offers the whole playlist.

Reported/observed (2026-10-02): probing a playlist landed on "none picked"
with the start button disabled — the designed "all N · Download playlist"
state was unreachable, because the uncheck-to-nothing trap (made for a human
unchecking the last box) also fired on the fresh render. And the footer row
below the download path grew the two doors users keep asking for: FAQ and a
replayable in-app tour.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src" / "suravidl_engine" / "web"
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()
JS = (WEB / "app.js").read_text()


def test_the_fresh_probe_offers_the_whole_playlist():
    """The trap stays for a human who unchecks the last box; a fresh probe is
    not that human."""
    assert "function syncPlaylistPicks(fromUser = true)" in JS
    assert "fromUser && boxes.length > 0" in JS
    assert "syncPlaylistPicks(false)" in JS          # the fresh render passes it
    assert "box.onchange = () => syncPlaylistPicks();" in JS  # the human path


def test_the_footer_grew_faq_and_tutorial():
    assert 'id="faqBtn"' in HTML and 'id="tourBtn"' in HTML
    assert 'id="faqModal"' in HTML and 'id="faqList"' in HTML
    assert 'id="tourShade"' in HTML and 'id="tourNext"' in HTML and 'id="tourSkip"' in HTML
    assert "function openFaq(" in JS
    assert "const FAQ = [" in JS and "const TOUR = [" in JS
    assert "function startTour(" in JS
    assert "// the FAQ card answers on Escape like every dialog" in JS
    assert ".faq-item" in CSS and ".tour-ring" in CSS and ".tour-card" in CSS
