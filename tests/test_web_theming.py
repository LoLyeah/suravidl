"""The appearance settings must actually DO something, on every host.

Written after a bug report — "the theme broke, glass style doesn't do
anything". On Android, one blanket host rule turned off the blur, the gloss
and the highlight for BOTH glass styles, so the two resolved to the same
solid panel and the toggle was a no-op on the platform most people use it on.
There was no test for any of it, which is why it shipped.

These assert the *difference* rather than the wording: every glass style must
change at least one visible property on every host, and the surfaces must
consume the tokens that carry that difference.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
CSS = (WEB / "style.css").read_text()


def _at(i, text=None):
    """From the `{` after index `i` through its matching close (never
    `split("}")` — these blocks contain braces of their own)."""
    text = CSS if text is None else text
    start = text.index("{", i)
    depth, j = 0, start
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[start:j]


def _block(marker):
    """The ONE rule that starts with this exact marker (the marker must be
    unambiguous — several rules share a selector like `.card {`)."""
    return _at(CSS.index(marker))


def _mobile_block(marker):
    """The `@media (max-width: 899px)` block that contains `marker` — there
    are two of them (layout and toasts) and they are not interchangeable."""
    start = 0
    while True:
        i = CSS.find("@media (max-width: 899px)", start)
        assert i != -1, "no mobile media block contains " + marker
        block = _at(i)
        if marker in block:
            return block
        start = i + 1


def test_every_theme_defines_the_same_core_tokens():
    """A theme that forgets a token inherits the :root value and looks wrong
    in exactly one corner of one screen."""
    core = ["--bg:", "--text:", "--muted:", "--glass-bg:", "--panel-solid:", "--accent:"]
    for theme in ("light", "dark", "amoled"):
        block = _block(f'html[data-theme="{theme}"]')
        for token in core:
            assert token in block, f"{theme} is missing {token}"


def test_the_two_glass_styles_differ_on_desktop():
    frosted = _block(':root, html[data-glass="frosted"]')
    liquid = _block('html[data-glass="liquid"]')
    assert "--glass-blur" in frosted and "--glass-blur" in liquid
    assert frosted.split("--glass-blur:")[1].split(";")[0] != \
        liquid.split("--glass-blur:")[1].split(";")[0], "same blur on both styles"
    # the gloss is what carries the look when a shell cannot blur
    assert "--glass-gloss: none" in frosted
    assert "linear-gradient" in liquid
    assert "--glass-border" in frosted and "--glass-border" in liquid


def test_android_glass_styles_are_not_the_same_panel():
    """The regression: the host block used to flatten both styles at once."""
    blanket = _block('html[data-host="android"] {\n  --glass-blur: none')
    assert "--glass-gloss: none" not in blanket, \
        "the blanket Android block must not flatten the glass styles"

    frosted = _block('html[data-host="android"][data-glass="frosted"]')
    liquid = _block('html[data-host="android"][data-glass="liquid"]')
    # frosted stays matte, liquid keeps a sheen — pure paint, no blur needed
    assert "--glass-gloss: none" in frosted
    assert "linear-gradient" in liquid
    # and the highlight/border must differ too, or the change is invisible
    assert frosted != liquid
    for token in ("--glass-hi", "--glass-border"):
        f = frosted.split(token)[1].split(";")[0]
        liq = liquid.split(token)[1].split(";")[0]
        assert f != liq, f"{token} is identical in both Android glass styles"


def test_the_glass_surfaces_consume_the_glass_tokens():
    """Cards, modals and toasts are the surfaces the setting is about: if they
    hard-code --line, liquid's tinted border never shows up."""
    assert CSS.count("border: 1px solid var(--glass-border)") >= 3
    # unambiguous markers: several rules begin with a bare `.card {`
    for surface in (".card {\n  background: var(--glass-bg);",
                    ".modal {\n  width: min(560px",
                    ".toast {\n  display: flex; align-items: center; gap: 10px;"):
        assert "border: 1px solid var(--glass-border)" in _block(surface)


def test_mobile_toasts_clear_the_tab_bar_and_its_safe_area():
    """The stack sat 84px up with no safe-area term, so on a phone with a
    gesture bar it sat that much lower — clipped behind the bar."""
    rule = _mobile_block("#toasts {")
    seg = rule.split("#toasts {")[1].split("}")[0]
    assert "env(safe-area-inset-bottom)" in seg, "toast lane ignores the inset"
    assert "calc(" in seg


def test_mobile_toasts_clear_the_settings_save_bar():
    """Settings pins a Save bar into the same lane. Two toasts over it left a
    sliver of the button showing through the gap — on the one screen where
    everyone taps a theme or glass swatch."""
    rule = _mobile_block('body[data-tab="settings"] #toasts')
    assert 'body[data-tab="settings"] #toasts' in rule
    default_bottom = rule.split("#toasts {")[1].split("bottom:")[1].split(";")[0]
    settings_bottom = rule.split('body[data-tab="settings"] #toasts')[1] \
        .split("bottom:")[1].split(";")[0]
    assert int(default_bottom.split("px")[0].split("(")[-1]) < \
        int(settings_bottom.split("px")[0].split("(")[-1]), \
        "the Settings lane must sit higher than the default one"


def test_show_tab_marks_the_body_so_css_can_react():
    seg = APP.split("function showTab(name, opts)")[1][:400]
    assert "document.body.dataset.tab = target" in seg
