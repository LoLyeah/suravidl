"""v0.45.1 "the pane" — the select wears the app's skin; the darwin wash
eases a step toward the material.

Two reports on the released desktop (2026-10-05):

1. "Fix the ugly drop down list in mac version." WKWebView kept its native
   bezel and double-chevron on <select> — the one borrowed widget in the
   room — so Subfolders / Container / Subtitles ignored the instrument
   styling. The select now resets the native appearance and draws its caret
   in the theme's own ink.

2. "Add a little bit more transparency to the background." The darwin wash
   eases from .88/.90/.88 to .86/.88/.86 — down to the documented contrast
   floor at night and AMOLED, one step short of it at day.

Plus the pipeline fix this round rode on: the amo workflow used to resubmit
on every tag; a tag whose extension version is unchanged since the previous
release now skips (AMO refuses a version it already has pending or live).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text()
DESIGN = (ROOT / "DESIGN.md").read_text()
AMO = (ROOT / ".github" / "workflows" / "amo.yml").read_text()


def test_the_select_draws_its_own_chrome():
    """appearance:none resets the WKWebView bezel; the caret is two theme-ink
    gradients, so it re-values with every theme automatically."""
    rule = CSS.split("\nselect {")[1].split("}")[0]
    assert "-webkit-appearance: none" in rule and "appearance: none" in rule
    assert "linear-gradient(45deg, transparent 50%, var(--muted) 50%)" in rule
    assert "linear-gradient(135deg, var(--muted) 50%, transparent 50%)" in rule
    assert "padding: 9px 34px 9px 10px;" in rule, "room for the drawn caret"
    assert "border-radius: 8px" in rule, "the skin stays in-system"
    assert "background-color: var(--input-bg)" in rule, "the ink well stays"


def test_the_rule_is_unscoped_so_every_menu_gets_it():
    assert CSS.count("\nselect {") == 1
    assert "\nselect.appearance" not in CSS


def test_the_wash_eases_without_breaking_the_floor():
    """.86 at night and AMOLED is the documented contrast floor; day stops one
    step short of it. The old, more opaque values are gone for good."""
    assert "--darwin-wash: rgba(15,18,22,.86);" in CSS
    assert "--darwin-wash: rgba(231,228,222,.88);" in CSS
    assert "--darwin-wash: rgba(0,0,0,.86);" in CSS
    assert "rgba(15,18,22,.88)" not in CSS
    assert "rgba(231,228,222,.90)" not in CSS
    # DESIGN.md carries the same numbers — the doc never drifts from the CSS
    assert "rgba(15,18,22,.86)" in DESIGN and "rgba(15, 18, 22, 0.86)" in DESIGN
    assert "rgba(15, 18, 22, 0.88)" not in DESIGN


def test_amo_skips_an_unchanged_extension():
    """The v0.45.1 tag ships no extension change; the submit step must be
    gated on the version delta, with workflow_dispatch force as the escape."""
    assert "Did the extension change since the last release?" in AMO
    assert 'git tag --sort=v:refname | grep -B1 -x "$GITHUB_REF_NAME"' in AMO
    assert 'echo "changed=false" >> "$GITHUB_OUTPUT"' in AMO
    assert "steps.changed.outputs.changed == 'true'" in AMO
    assert "github.event.inputs.force == 'true'" in AMO
