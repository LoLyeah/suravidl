"""v0.37.1 — the device pass: five defects off the user's phone screenshots.

1. the What's-new list scrolled behind a fat desktop scrollbar — the custom
   webkit rules had overridden Android's native transient overlay;
2. (mis-diagnosis, reverted in v0.37.2) the floating glass was believed
   blur-less on the phone and briefly made near-opaque; device pixels prove
   the blur renders — the pin below guards the revert;
3. a tab swap was serial: the old screen faded out, and only after it was
   GONE did the new screen start arriving (plus an extra .4s panel wash);
4. Settings sub-tabs swapped with no transition at all — the only navigation
   in the app that did;
5. the android flatten rule painted EVERY `.modal-foot` a near-black slab —
   the black bar behind "Got it" / "Cancel"/"Delete" on glass dialogs.

The phone is where the app lives; each pin names the screenshot it answers.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def _block(marker, text=CSS):
    """The text from `marker` through its matching closing brace."""
    i = text.index(marker)
    start = text.index("{", i)
    depth, j = 0, start
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces after " + marker)


def _theme_block(theme):
    if theme == "dark":
        return _block(':root, html[data-theme="dark"]')
    return _block('html[data-theme="%s"]' % theme)


def _fn(name):
    assert "function " + name in APP, name + " is gone"
    return APP.split("function " + name, 1)[1].split("\nfunction ", 1)[0]


# --- 1. the dialog scroller ------------------------------------------------

def test_the_dialog_scroller_wears_a_hairline_and_loses_it_on_touch():
    """A 9px always-on bar inside a phone dialog — the bars were sized for a
    mouse and never yielded to the platform's own transient overlay."""
    assert "width: 6px; height: 6px" in CSS
    rule = CSS.split("::-webkit-scrollbar { width: 6px; height: 6px; }")[0] \
        .rsplit("}", 1)[-1]
    for sel in (".optlist", ".folderlist", ".wnlist", ".subtabs", "textarea",
                ".modal"):
        assert sel in rule, sel
    blk = CSS.split("@media (pointer: coarse)")[1]
    assert ".wnlist::-webkit-scrollbar" in blk, \
        "touch still gets a drag handle it cannot use"
    assert "scrollbar-width: none" in blk


# --- 2. the floating glass keeps its real blur (the revert) ----------------

def test_the_floating_glass_keeps_its_blur_on_the_phone():
    """History, for the record: v0.37.1 flipped the floating plates
    near-opaque on the premise that this WebView skips backdrop-filter;
    v0.37.2 reverted that on an edge-energy misread; v0.37.6 settled it —
    the device photos prove the WebView does not composite the pass for
    floating plates in EITHER geometry (fixed or sticky). The declarations
    stay (a WebView that composites lights them up) and the android bar
    pours dense so the readout never shares pixels with the page."""
    assert "--glass-float" not in CSS, "the near-opaque float plates are back"
    # v0.45.10: android re-veils the CARD's shadow only — never the material
    am = _block('html[data-host="android"] .modal {')
    assert "0 0 0 100vmax rgba(3, 5, 12, .72)" in am
    assert "backdrop-filter" not in am and "background:" not in am
    assert 'html[data-host="android"] .toast' not in CSS
    # the android transport may override the POUR only — never the material
    pour = _block('html[data-host="android"] .transport {')
    assert "color-mix" in pour and "85%" in pour
    assert "backdrop-filter" not in pour
    # the floating surfaces still consume the shared material
    for sel in (".modal {", ".transport {"):
        blk = _block(sel)
        assert "backdrop-filter: var(--glass-blur)" in blk, sel


def test_the_glass_blur_css_survives_somewhere_it_can_run():
    """The desktop/browser path must keep the real material."""
    assert "backdrop-filter: var(--glass-blur)" in CSS
    assert "@supports not" in CSS


# --- 3. the black bar behind the dialog buttons ----------------------------

def test_the_black_bar_behind_the_dialog_buttons_is_gone():
    """The flatten rule aimed at the Settings Save strip painted every
    `.modal-foot` panel-solid — on a glass dialog that slab read as a black
    bar behind the buttons (both photos)."""
    assert 'html[data-host="android"] .modal-foot {' not in CSS
    assert 'html[data-host="android"] #panel-settings .modal-foot {' in CSS


# --- 4. the tab swap -------------------------------------------------------

def test_the_tab_swap_starts_immediately_and_lands_in_a_beat():
    """Old: .14s exit → THEN swap → .4s panel wash. The next screen only
    STARTED arriving once the previous one had finished leaving."""
    assert ".panel { animation: panelIn" not in CSS
    assert "@keyframes panelIn" not in CSS, "the .4s wash is still defined"
    assert "tabOut" not in CSS, "the serial exit is still defined"
    assert ".tab-in { animation: tabIn var(--t-fast) var(--e-out) none; }" in CSS
    into = _block("@keyframes tabIn")
    assert "opacity" in into
    assert "transform" not in into, \
        "a transform arrival re-anchors the panel's fixed transport (v0.37.3)"
    assert "height" not in into and "max-height" not in into
    seg = APP.split("function showTab(")[1].split("TABS.forEach((t) => {")[0]
    assert '"tab-in"' in seg
    assert '"tab-out"' not in seg, "the swap waits on an exit again"
    assert "animationend" not in seg, "the swap waits on an event again"
    assert "switching" in seg
    assert "current !== target" in seg, "never fade on first paint"
    assert "includes(incoming)" in seg, \
        "a refresh of the visible tab must not restart the fade"


# --- 5. the Settings sub-tabs ----------------------------------------------

def test_settings_subtabs_swap_with_a_transition():
    """The sub-tabs were the only navigation in the app with no transition;
    the abrupt cut read as a page jump."""
    assert ".spanel-in { animation: spanelIn var(--t-fast) var(--e-out) none; }" \
        in CSS
    blk = _block("@keyframes spanelIn")
    # v0.39.12: opacity-only — a transform here re-anchors the panel's fixed
    # transport for the length of the fade (the tabIn law, the audit found it)
    assert "opacity" in blk and "transform" not in blk
    seg = APP.split("function showSettingsTab(")[1].split("/* ---------- the shell")[0]
    assert '"spanel-in"' in seg
    assert "offsetWidth" in seg, "rapid re-taps need the fade restarted"


# --- found on the way ------------------------------------------------------

def test_the_error_row_reads_at_full_width():
    """The raw engine text shared one flex line with Show details / Copy /
    Retry and wrapped to about one word per line on a phone (photo 2)."""
    seg = APP.split('j.status === "error" || j.status === "interrupted"')[1] \
        .split("} else if (j.filepath)")[0]
    assert "row.append(errEl)" in seg, "the message is boxed into the button row"
    assert "r.append(errEl)" not in seg
    assert '"Show details"' in seg
    blk = _block(".jerr {")
    assert "flex" not in blk, "it still fights the buttons for one line"


def test_the_subtabs_wrap_a_phone_row():
    """Six sub-tabs never fit one 393px row: the last one ran half-cut off
    the card edge (photo 3: "Auth" clipped). They wrap now, and the pills go
    to a phone size."""
    assert "  .subtabs .stab { padding: 7px 10px; font-size: 12px; }" in CSS, \
        "no phone-sized sub-tab pill"
    assert "  .subtabs { flex-wrap: wrap; }" in CSS, \
        "the row still runs off the edge instead of wrapping"
