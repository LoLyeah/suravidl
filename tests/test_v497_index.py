"""v0.49.7 "the index" — the 322-row options browser as a table, not 322 cards.

Measured at 412 px before the pass: 51 px of horizontal overflow (help text
ran 24 px past the card edge and clipped mid-word), a 207 px search field in a
388 px card, the category repeated under every flag, 78 px rows, and the count
reading as a second clause of the heading ("All yt-dlp options 322 options").

The catalogue also printed yt-dlp's SUPPRESSHELP sentinel as the description of
72 deprecated switches — "--call-home: SUPPRESSHELP" — which yt-dlp itself
hides from --help.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.49.7" and e["title"].lower() == "the index"
               for e in ENTRIES)


def test_the_heading_keeps_its_own_line():
    head = HTML[HTML.index('id="optionsCard"'):]
    head = head[:head.index("</div>")]
    assert "<h2" in head and "optionsCount" in head
    assert 'class="count"' in head
    # the count is a sibling of the heading, never inside it
    assert 'id="optionsCount"' not in re.search(r"<h2[^>]*>.*?</h2>", head, re.S).group(0)


def test_the_search_field_fills_the_card():
    assert ".optsearch input { width: 100%;" in CSS
    assert ".optsearch .ico" in CSS
    # and it is found by the sprite, not a unicode glyph
    assert '<use href="#i-search"/>' in HTML[HTML.index('class="optsearch"'):][:300]
    assert '<symbol id="i-plus"' in HTML


def test_one_header_per_group_not_one_label_per_row():
    assert '.optgroup {' in CSS and "position: sticky" in CSS
    assert 'box.append(el("div", "optgroup", group))' in APP
    # the per-row category is gone
    assert 'left.append(el("div", "ogrp", o.group))' not in APP
    assert "o.group !== group" in APP


def test_general_leads_the_list():
    assert 'const lead = (g) => (/^general/i.test(g) ? "" : g.toLowerCase());' in APP


def test_rows_are_a_table_with_a_hairline_not_cards():
    assert "#optionsList .optrow {" in CSS
    block = CSS[CSS.index("#optionsList .optrow {"):]
    block = block[:block.index("\n}")]
    assert "grid-template-columns" in block
    assert "border-radius: 0" in block
    assert "border-top: 1px solid var(--line-soft)" in block


def test_the_longest_help_is_cut_in_the_string_not_by_a_clamp():
    # a -webkit-line-clamp clipped with no ellipsis at all (measured), so the
    # row stopped mid-sentence silently; the cut is explicit and visible
    assert "const HELP_MAX = 300;" in APP
    assert 'cut.slice(0, space) : cut).trimEnd() + " …"' in APP
    block = CSS[CSS.index("#optionsCard .card-head"):CSS.index("/* wide rooms: the flag gets its own column")]
    assert "line-clamp" not in block
    assert 'if (o.help) help.title = o.help;' in APP


def test_the_metavar_is_its_own_quiet_word():
    assert 'el("span", "metavar", o.metavar || "VALUE")' in APP
    assert "#optionsList .optrow .metavar" in CSS


def test_deprecated_switches_no_longer_print_the_sentinel():
    from suravidl_engine.options_catalogue import build_catalogue

    catalogue = build_catalogue()
    assert all(e["help"] != "SUPPRESSHELP" for e in catalogue)
    assert "--call-home" not in {e["name"] for e in catalogue}
