"""The polish pass, pinned — 2026-09-30.

Found by using the app, not by reading it: every item below is a state a real
click or a real viewport reached (a dead link, an 8-second clip, a 390px
phone, a scrolled preset list on dark glass).

- The error line under Probe kept the muted "hint" voice — the design system
  says error text is Nova Rose and machine text is mono.
- A sub-minute clip's meta chip read "0 min"; "0 min" is not a duration.
- The option rows (Quality / Audio only / Subtitles) sat 20px deeper than the
  card's own title and format table — chips indented, table flush.
- Scrollbars, text selection, the caret and data numerals still shipped
  browser defaults, and the footer's underlined labels read as "copy_path".

(One earlier suspicion — the active Settings sub-tab sitting cut off at 390px
— turned out to be a viewport-shrink artifact: `showSettingsTab` already
scrolls the active sub-tab into view. The last test pins that behavior
instead of fixing it.)

Each test asserts the rule, so a later edit that re-opens the hole fails here.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
CSS = (WEB / "style.css").read_text()


def _theme_block(theme: str) -> str:
    anchor = f'html[data-theme="{theme}"]'
    return CSS.split(anchor, 1)[1].split("}", 1)[0]


def test_a_failed_probe_reads_as_an_error_in_machine_voice():
    """`probeMsg` kept class "msg muted": the one failure message in the app
    that rendered grey. Errors are Nova Rose, engine text is mono."""
    assert '$("probeMsg").className = "msg bad mono";' in APP
    # and the next probe clears the previous verdict before it starts
    assert '$("probeMsg").className = "msg muted";' in APP


def test_sub_minute_durations_never_read_zero():
    """`Math.round(8 / 60) + " min"` = "0 min" — seen on the HLS fixture."""
    assert "info.duration < 60" in APP and 't("<1 min")' in APP
    assert '" · " + Math.round(info.duration / 60) + " min" : ""' not in APP, \
        "the old one-liner still rounds an 8-second clip to \"0 min\""


def test_the_option_rows_align_with_the_card_content():
    """Chips rows carried their own 20px side padding on top of the card's
    18px — every other element in the card sits flush."""
    block = CSS.split(".audioRow {", 1)[1].split("}", 1)[0]
    assert "padding: 0 0 14px" in block, \
        "the chips rows drift 20px inside the card's own edge"


def test_scrollbars_carry_the_palette():
    """Stock scrollbars on dark glass were the loudest un-themed surface."""
    assert "scrollbar-width: thin; scrollbar-color: var(--dim) transparent" in CSS
    rule = CSS.split(
        "scrollbar-width: thin; scrollbar-color: var(--dim) transparent"
    )[0].rsplit("}", 1)[-1]
    for sel in (".optlist", ".folderlist", ".wnlist", ".subtabs", "textarea"):
        assert sel in rule, sel


def test_selection_and_the_caret_are_themed():
    for theme in ("dark", "light", "amoled"):
        assert "--sel:" in _theme_block(theme), f"{theme} has no selection tint"
    assert "::selection { background: var(--sel" in CSS
    assert "caret-color: var(--accent)" in CSS


def test_machine_numerals_are_tabular():
    """A percent or a size that changes between two polls must not shift the
    text beside it."""
    assert "font-variant-numeric: tabular-nums" in CSS
    rule = CSS.split("font-variant-numeric: tabular-nums")[0].rsplit("}", 1)[-1]
    for sel in (".meta", ".jmeta", ".fmt-s", ".fsize"):
        assert sel in rule, sel


def test_link_underlines_sit_below_the_baseline():
    """Un-tuned underlines ran through the space between words, so the
    footer read "copy_path / open_folder"."""
    block = CSS.split("\n.linkbtn {", 1)[1].split("}", 1)[0]
    assert "text-underline-offset" in block


def test_the_active_settings_tab_scrolls_itself_into_view():
    """At 390px the sub-tabs scroll horizontally; switching to one past the
    fold left it cut off at the edge ("Au|" for Authentication)."""
    seg = APP.split("function showSettingsTab(", 1)[1].split("\nfunction ", 1)[0]
    assert "scrollIntoView" in seg


def test_placeholders_meet_the_contrast_floor():
    """The rendered-pass detector caught what the file pass could not: the
    paste field's hint sat at 3.7:1 (--dim), and every other input fell back
    to the browser's own grey (4.3:1) — both under the floor for placeholder
    text. Placeholders now carry their own per-theme token."""
    assert "input::placeholder, textarea::placeholder { color: var(--ph); }" in CSS
    for theme in ("dark", "light", "amoled"):
        assert "--ph:" in _theme_block(theme), f"{theme} has no placeholder tone"
    assert ".paste input::placeholder { color: var(--dim); }" not in CSS
