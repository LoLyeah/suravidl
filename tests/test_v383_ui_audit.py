"""v0.38.3 — the audit pass (impeccable + antislop via agy, confirmed here)
and the Pine & Cream scheme option.

Every finding was verified against the tree before this file was written.
The tests pin the fixes so they cannot rot back.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text()
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
SETTINGS = (ROOT / "src" / "suravidl_engine" / "settings.py").read_text()
API = (ROOT / "src" / "suravidl_engine" / "api.py").read_text()


def tag_of(html: str, el_id: str) -> str:
    i = html.find(f'id="{el_id}"')
    assert i != -1, el_id
    return html[html.rfind("<", 0, i):html.find(">", i) + 1]


# ---------- 1. liveries clear 4.5:1 in the light room ----------
def test_light_theme_liveries_use_dark_brand_inks():
    import re
    norm = re.sub(r"\s+", " ", CSS)
    for site, ink in (("youtube", "#c5221f"), ("twitter", "#1d68c9"),
                      ("vimeo", "#0073a8"), ("instagram", "#a82782"),
                      ("tiktok", "#077a6e")):
        assert (f'html[data-theme="light"] .card[data-livery="{site}"]'
                f' {{ --livery: {ink}; }}') in norm


# ---------- 2. the what's-new modal behaves like every dialog ----------
def test_whats_new_uses_the_dialog_lifecycle():
    seg = APP[APP.find("function showWhatsNew"):APP.find("function dismissWhatsNew")]
    assert 'const modal = $("whatsNewModal")' in seg
    assert "openModal(modal)" in seg
    assert 'closeModal($("whatsNewModal"))' in APP[
        APP.find("function dismissWhatsNew"):APP.find("async function maybeShowWhatsNew")]
    assert 'e.target === modal' in seg          # backdrop dismiss
    assert APP.count("wnVersion") >= 2          # Escape needs the version


def test_escape_closes_the_whats_new_card():
    i = APP.find('e.key !== "Escape"')
    seg = APP[i:i + 700]
    assert "dismissWhatsNew(wnVersion)" in seg


# ---------- 3. the expandable title is keyboard-operable ----------
def test_job_title_expands_from_the_keyboard():
    i = APP.find('"jobtitle"')
    seg = APP[i:i + 900]
    assert 'title.tabIndex = 0' in seg
    assert 'role", "button"' in seg or 'role", "button' in seg
    assert 'aria-expanded' in seg
    assert 'title.onclick = () =>' in seg       # the pinned wiring stays
    assert 'title.classList.toggle("open")' in seg
    assert 'title.onkeydown' in seg
    assert ".jobtitle:focus-visible" in CSS


# ---------- 4. an unarmed chip never glows like the lamp ----------
def test_the_best_chip_is_not_prematurely_prime():
    i = APP.find("function renderQualityRow")
    seg = APP[i:i + 2200]
    assert '" prime"' not in seg
    assert '" pick" : "")' in seg


# ---------- 5. the minimize button is a drawn glyph ----------
def test_min_button_is_a_drawn_svg_with_a_name():
    btn = tag_of(HTML, "minBtn")
    assert 'aria-label="Minimize window"' in btn
    assert ">—" not in HTML[HTML.find('id="minBtn"') - 30:HTML.find('id="minBtn"') + 200]
    assert 'id="i-minus"' in HTML
    assert 'href="#i-minus"' in HTML[HTML.find('id="minBtn"'):HTML.find('id="minBtn"') + 400]


# ---------- 6. the active tab icon clears 3:1 in every room ----------
def test_active_tab_icon_uses_the_readable_ink():
    assert ".tab.active .tab-ico { color: var(--accent-ink); }" in CSS


# ---------- 7. every control has a name ----------
def test_the_six_unnamed_controls_are_named():
    for el_id, label in (
        ("audioMore", "More audio presets"),
        ("playlistItems", "Playlist items to download"),
        ("ovClipEnd", "Clip end time"),
        ("setCookies", "Path to cookies file"),
        ("setCookiesBrowser", "Browser to take cookies from"),
        ("setImpersonate", "Browser to impersonate"),
    ):
        assert f'aria-label="{label}"' in tag_of(HTML, el_id), el_id


# ---------- 8. chips honour the craft floor ----------
def test_chips_meet_radius_touch_and_press_rules():
    i = CSS.find(".chip {")
    block = CSS[i:CSS.find("}", i) + 1]
    assert "border-radius: 8px" in block
    coarse = CSS[CSS.find("@media (pointer: coarse)"):]
    assert "button.chip { min-height: 44px" in coarse
    assert "button.chip:active" in CSS


# ---------- 9. the settings subtabs speak tablist ----------
def test_settings_subtabs_have_tab_semantics():
    tabs = tag_of(HTML, "settingsTabs")
    assert 'role="tablist"' in tabs and 'aria-label="Settings sections"' in tabs
    for name in ("general", "media", "presets", "network", "auth", "advanced"):
        btn = HTML[HTML.find(f'data-stab="{name}"') - 200:HTML.find(f'data-stab="{name}"') + 160]
        assert 'role="tab"' in btn, name
        assert f'aria-controls="spanel-{name}"' in btn, name
    assert HTML.count('role="tabpanel"') >= 6
    assert "aria-selected" in APP[APP.find("function showSettingsTab"):APP.find("function showSettingsTab") + 900]


# ---------- 10. the ok state clears 4.5:1 in the light room ----------
def test_light_ok_green_is_readable_on_the_light_ground():
    import re
    m = re.search(r'html\[data-theme="light"\] \{[^}]*--ok:\s*(#[0-9a-fA-F]{6})', CSS)
    assert m, "light --ok not found"
    # #1b6942 measures 5.26:1 on #e7e4de (the shipped #1f7a4d was 4.19:1)
    assert m.group(1).lower() in ("#1b6942", "#1b6a42", "#176341")


# ---------- 11. preset rows stop pretending to be buttons ----------
def test_preset_rows_are_read_only():
    assert "#presetList .optrow { cursor: default; }" in CSS


# ---------- 12. the armed strip's path is keyboard-operable ----------
def test_armed_text_is_keyboard_operable():
    i = APP.find('$("armedText").onclick')
    seg = APP[i - 300:i + 600]
    assert 'tabIndex = 0' in seg
    assert 'role", "button"' in seg or 'role", "button' in seg
    assert "$(\"armedText\").onkeydown" in seg
    assert "#armedText:focus-visible" in CSS


# ---------- 13. honest grammar, steady machine numbers ----------
def test_option_search_pluralizes_and_reads_tabular():
    assert '${list.length} match${list.length === 1 ? "" : "es"}' in APP
    assert 'class="muted small mono"' in tag_of(HTML, "optionsCount")


# ---------- 14. disclosure toggles announce themselves ----------
def test_disclosure_toggles_carry_aria_state():
    btn = tag_of(HTML, "probeDetails")
    assert 'aria-expanded="false"' in btn and 'aria-controls="probeMsg"' in btn
    i = APP.find('$("probeDetails").onclick')
    assert 'aria-expanded' in APP[i:i + 400]
    j = APP.find('jrr-toggle')
    assert 'aria-expanded' in APP[j - 100:j + 900]


# ---------- 15. the queue says what it is doing before the first poll ----------
def test_queue_opens_with_a_honest_loading_line():
    i = HTML.find('id="jobs"')
    seg = HTML[i:i + 200]
    assert "Checking the queue" in seg
    assert "jobsInitial" in seg
    assert "#jobsInitial" in APP or 'jobsInitial' in APP   # refreshJobs clears it


# ---------- the pine & cream scheme option ----------
def test_the_engine_persists_and_validates_the_scheme():
    assert 'ACCENTS = ("amber", "pine")' in SETTINGS
    assert '"accent": "amber"' in SETTINGS
    assert '"accent",' in SETTINGS            # an appearance key, not per-job
    assert 'value not in ACCENTS' in SETTINGS
    assert '"accent": settings.get()["accent"]' in API


def test_the_shell_applies_the_scheme_before_first_paint():
    boot = HTML[HTML.find("apply persisted"):HTML.find("</head>")]
    assert "dataset.accent" in boot
    assert 'id="schemeSwatches"' in HTML
    assert 'data-accent="pine"' in HTML and 'data-accent="amber"' in HTML
    assert 'dataset.accent' in APP[APP.find("function applyTheme"):APP.find("function applyTheme") + 900]
    assert "#schemeSwatches .swatch" in APP
    assert "accent: s.accent" in APP or "s.accent" in APP


def test_the_pine_scheme_swaps_the_accent_set_per_theme():
    light = CSS.find('html[data-accent="pine"][data-theme="light"]')
    dark = CSS.find('html[data-accent="pine"][data-theme="dark"]')
    assert light != -1 and dark != -1
    light_block = CSS[light:CSS.find("}", light) + 1]
    dark_block = CSS[dark:CSS.find("}", dark) + 1]
    assert "--accent: #14493C" in light_block and "--accent-fg: #F2E9D8" in light_block
    assert "--accent: #F2E9D8" in dark_block and "--accent-fg: #14493C" in dark_block


def test_the_hardcoded_button_ink_is_tokenized():
    assert "--accent-fg:" in CSS and "--accent-glow:" in CSS
    # the ink survives only as the three token declarations, never inline
    assert CSS.count("#1a1305") == 3
    assert "color: #1a1305" not in CSS
    assert "var(--accent-glow)" in CSS


def test_the_scheme_swatches_preview_both_voices():
    assert ".sw-amber" in CSS and ".sw-pine" in CSS
    # the theme previews follow the scheme too
    assert '[data-accent="pine"] .sw-dark' in CSS
