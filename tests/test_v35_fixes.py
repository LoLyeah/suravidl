"""v0.35.0 — the download end of the preset workflow.

"Applying for preset looks good, but how about downloading the video with
applied presets? The ux workflow doesn't makes sense for it." Reproduced
off the live UI (phone width): the armed set hid in the collapsed block
below the card — nowhere near a download button; the start toast never
said what rode the job; a quality pick silently replaced an audio preset's
format; and after one download the armed state vanished with no notice.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text(encoding="utf-8")


def _fn(name):
    assert "function " + name in APP, name + " is gone"
    body = APP.split("function " + name, 1)[1]
    return body.split("\nfunction ", 1)[0]


# -- the card carries the armed state ---------------------------------------

def test_the_card_has_the_armed_strip():
    for el in ("armedBar", "armedText", "armedClear"):
        assert 'id="' + el + '"' in HTML, el


def test_the_strip_paints_from_the_count_that_already_updates():
    body = _fn("renderOvCount")
    assert '$("armedBar")' in body and '$("armedText")' in body
    assert "next download:" in body
    # both branches: hidden when nothing is armed, shown otherwise
    assert 'bar.classList.add("hidden")' in body
    assert 'bar.classList.remove("hidden")' in body


def test_the_strip_names_the_preset_and_its_description():
    body = _fn("renderOvCount")
    # the preset's own description rides along, like the block's info line
    assert "entry.description" in body
    # and the manual-only case points at the block
    assert "set below" in body


# -- the start toast says what rode -----------------------------------------

def test_the_start_toast_names_the_preset_that_rode():
    body = _fn("startJob")
    assert "with preset “" in body
    assert '") + note, "info"' in body


def test_a_format_pick_that_drops_an_intent_says_so():
    body = _fn("startJob")
    assert "skipped: your format pick replaces it" in body


def test_manual_options_are_named_in_the_start_toast():
    assert "set below" in _fn("startJob")


# -- clear / open wiring ----------------------------------------------------

def test_the_strip_is_wired_to_clear_and_to_open_the_block():
    body = _fn("initOverrides")
    assert 'armedClear' in body and 'armedText' in body
    assert "clearOv()" in body
    assert "scrollIntoView" in body and '$("ovBlock").open' in body


def test_the_strip_ink_clears_the_contrast_floor_in_light():
    """#0a6fd8 on the light strip composite measured 3.65:1 — under the 4.5
    floor this repo holds every small-text token to. The Post House re-valued
    the whole light palette; #6b4308 measures ~5.98:1 on the same composite
    (accent-soft over the card over the page), and the v0.37 suite recomputes
    every theme's ratios instead of trusting these literals."""
    css = (ROOT / "src/suravidl_engine/web/style.css").read_text(encoding="utf-8")
    light = css.split('html[data-theme="light"]', 1)[1].split("}", 1)[0]
    assert "--accent-ink: #6b4308" in light
