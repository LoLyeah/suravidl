"""Fixes from the fourth `agy` audit pass (v0.44.x) — the Settings screen,
the shell's a11y gaps, and the extension's small debts.

Two parallel agy audits ran over the v0.44.0 tree (Settings deep-dive, and
the rest of the UI). Every pin below reproduced a defect confirmed against
the real tree first — and where the audit overstated a finding, the test
records the narrower truth and says so (see the reduced-motion and
number-clamp entries).

Behaviour tests cover the engine half: the cookie test rides transient
overrides, and using it may never commit settings.
"""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src" / "suravidl_engine"
WEB = SRC / "web"
ROOT = Path(__file__).resolve().parents[1]

APP = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")
API = (SRC / "api.py").read_text(encoding="utf-8")

AUTH = {"Authorization": "Bearer t"}


def _app(tmp_path):
    import suravidl_engine.api as api

    return api.create_app(download_dir=tmp_path / "dl", auth_token="t",
                          db_path=tmp_path / "jobs.db")


# -- settings: the sub-tabs keep the APG promise -----------------------------

def test_settings_sub_tabs_take_one_tab_stop_and_arrows_move():
    assert "function syncStabTabs(" in APP
    assert "b.tabIndex = on ? 0 : -1;" in APP
    i = APP.index("function syncStabTabs(")
    seg = APP[i:i + 2600]
    assert '"ArrowRight"' in seg and '"ArrowLeft"' in seg
    assert '"Home"' in seg and '"End"' in seg
    # every sub-tab panel names the tab that owns it
    for name, btn in (("general", "stabGeneral"), ("media", "stabMedia"),
                      ("presets", "stabPresets"), ("network", "stabNetwork"),
                      ("auth", "stabAuth"), ("advanced", "stabAdvanced"),
                      ("device", "tabDevice")):
        assert f'aria-labelledby="{btn}"' in HTML, name


def test_the_settings_panels_sit_in_tab_order_in_the_dom():
    assert HTML.index('id="spanel-media"') < HTML.index('id="spanel-presets"')


# -- settings: appearance swatches announce their state ----------------------

def test_the_swatches_announce_the_selected_state():
    i = APP.index("function markSwatches(")
    seg = APP[i:i + 1400]
    assert 'setAttribute("aria-pressed"' in seg
    for group, label in (("themeSwatches", "lblAppearance"),
                         ("glassSwatches", "lblGlass"),
                         ("schemeSwatches", "lblScheme")):
        assert f'role="group" aria-labelledby="{label}"' in HTML
        assert f'id="{group}"' in HTML


def test_the_scheme_selection_survives_a_settings_load():
    """loadSettings() dropped accent from CURRENT, so the scheme swatches
    showed no selection until clicked (found while wiring aria-pressed)."""
    seg = APP[APP.index("async function loadSettings()"):]
    assert "CURRENT = { theme: s.theme, glass: s.glass, accent: s.accent };" in seg[:400]


# -- settings: the dirty dot tells the truth ---------------------------------

def test_the_dirty_dot_ignores_self_persisting_controls():
    assert "DIRTY_IGNORE" in APP
    seg = APP[APP.index("DIRTY_IGNORE"):APP.index("DIRTY_IGNORE") + 600]
    for control in ("setLang", "defaultPreset", "setConc", "presetName",
                    "archiveEntry"):
        assert f'"{control}"' in seg, control
    assert "markSettingsDirty(true);" in APP


# -- settings: "applied live" is true now ------------------------------------

def test_concurrent_downloads_apply_live():
    assert '$("setConc").onchange = async () => {' in APP
    assert 'JSON.stringify({ max_concurrent: n })' in APP


# -- settings: one payload builder, two readers ------------------------------

def test_the_preset_diff_reads_the_live_form():
    assert "function settingsFormPayload()" in APP
    assert "body: JSON.stringify(settingsFormPayload())" in APP
    i = APP.index("function presetPatchFromSettings(")
    seg = APP[i:i + 900]
    assert "const form = settingsFormPayload();" in seg
    assert "form[k]" in seg
    assert "SETTINGS_SNAPSHOT ? SETTINGS_SNAPSHOT[k]" not in APP


def test_the_form_mirrors_what_the_engine_clamped():
    i = APP.index("function saveSettings()")
    seg = APP[i:i + 1200]
    assert '$("setFragments").value = s.fragments;' in seg
    assert '$("setRetries").value = s.retries;' in seg
    assert '$("setMaxDownloads").value = s.max_downloads;' in seg


def test_the_number_range_claim_is_the_server_side_truth():
    """The audit said empty inputs corrupt settings; the engine actually
    clamps every number key (0 -> lo, junk refused) — the narrower truth."""
    settings = (SRC / "settings.py").read_text(encoding="utf-8")
    assert 'int_in(value, "fragments", 1, 16)' in settings
    assert 'int_in(value, "max_concurrent", 1, 4)' in settings


# -- settings: the cookie test never commits the form ------------------------

def test_the_cookie_test_rides_transient_overrides():
    i = APP.index("async function testCookies()")
    seg = APP[i:i + 1200]
    assert "await saveSettings();" not in seg
    assert 'cookies_file: $("setCookies").value.trim()' in seg
    assert "cookies_from_browser" in seg
    assert "cookies_file: str | None = None" in API
    assert 's["cookies_file"] = body.cookies_file.strip()' in API


def test_auth_check_overrides_stay_transient(tmp_path):
    c = TestClient(_app(tmp_path))
    before = c.get("/settings", headers=AUTH).json()["cookies_file"]
    r = c.post("/auth/check",
               json={"cookies_file": str(tmp_path / "definitely-missing.txt")},
               headers=AUTH)
    assert r.status_code == 200
    assert "not found" in r.json()["message"]
    # a test, not a save: the stored value stayed untouched
    assert c.get("/settings", headers=AUTH).json()["cookies_file"] == before


# -- settings: the vault wipe and other destructions ask first ---------------

def test_the_vault_wipe_asks_before_it_wipes():
    i = APP.index('$("deleteCookiesBtn").onclick')
    seg = APP[i:i + 500]
    assert "askConfirm(" in seg


def test_a_preset_needs_a_name_before_the_round_trip():
    i = APP.index("async function saveCurrentAsPreset()")
    seg = APP[i:i + 1600]
    assert 't("a preset needs a name")' in seg


# -- settings: token copy and names on delete buttons ------------------------

def test_the_token_copy_reveals_the_full_token_when_the_clipboard_fails():
    i = APP.index("function wireToken()")
    seg = APP[i:i + 2400]
    assert "legacy(tok)" in seg
    assert "el.textContent = tok;" in seg


def test_delete_buttons_name_their_target():
    assert 't("Forget archive entry {entry}", { entry: line })' in APP
    assert 't("Delete preset “{name}”", { name: p.name })' in APP


def test_settings_hints_are_linked_for_screen_readers():
    for hint in ("setConcHint", "setFragmentsHint", "setRetriesHint",
                 "setMaxDownloadsHint"):
        assert f'aria-describedby="{hint}"' in HTML
        assert f'id="{hint}"' in HTML


# -- the shell: probe announcement, queue semantics, the door ----------------

def test_a_successful_probe_is_announced():
    assert 'id="probeLive"' in HTML and 'class="sr-only"' in HTML
    assert 't("probe ready — the formats are below")' in APP


def test_queue_rows_carry_list_and_progress_semantics():
    assert '<div id="jobs" role="list">' in HTML
    assert 'row.setAttribute("role", "listitem");' in APP
    assert 'bar.setAttribute("role", "progressbar");' in APP
    assert 'bar.setAttribute("aria-valuenow", progressPct(j).toFixed(0));' in APP
    assert 'title.setAttribute("aria-controls", details.id);' in APP


def test_the_studio_button_follows_the_bay_door():
    assert 'aria-controls="ovBlock" aria-expanded="false"' in HTML
    assert 'b.setAttribute("aria-expanded", d.open ? "true" : "false");' in APP


def test_the_no_sound_listener_left_the_folder_sheet():
    """It was the last line of initFolderSheet() — a download-deck control
    riding an Android dialog initializer."""
    assert APP.index('$("noSound").addEventListener("change", refreshSoundLabels)') \
        < APP.index("function initFolderSheet()")


def test_the_desktop_only_row_hides_where_it_cannot_work():
    assert 'class="field hidden" id="revealField"' in HTML
    assert 'revealField.classList.remove("hidden")' in APP


def test_probe_rows_skip_the_stagger_when_motion_is_off():
    assert APP.count("if (motionMs(150) > 0) tr.style.animationDelay") == 2


def test_the_empty_state_sits_above_the_probe_card():
    assert HTML.index('id="dlEmpty"') < HTML.index('id="probeCard"')


def test_the_archive_master_toggle_sits_above_its_controls():
    assert HTML.index('for="setArchive"') < HTML.index('id="archiveField"')


# -- css: the audit's claims, held to their evidence -------------------------

def test_light_theme_selected_outlines_clear_three_to_one():
    assert 'html[data-theme="light"] .swatch.on { border-color: var(--accent2); }' in CSS
    ground, accent2 = "#e7e4de", "#a8670f"

    def _lum(h):
        rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]

        def f(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = map(f, rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lo, hi = sorted((_lum(ground), _lum(accent2)))
    assert (hi + 0.05) / (lo + 0.05) >= 3.0, "the darker voice must clear 3:1"


def test_the_no_blur_fallback_covers_every_glass_plate():
    i = CSS.index("@supports not ((backdrop-filter")
    seg = CSS[i:i + 420]
    for sel in (".scope", ".job", ".bin", ".optrow", ".swatch", ".tour-card"):
        assert sel in seg, sel


def test_the_rail_stays_put_on_wide_screens():
    assert "position: sticky; top: 74px; align-self: start;" in CSS


def test_machine_string_inputs_wear_the_machine_voice():
    assert "input.mono { font-family:" in CSS
    for i in ("setDir", "setRateLimit", "setProxy"):
        assert f'id="{i}" class="mono"' in HTML, i


def test_reduced_motion_keeps_the_documented_kill():
    """The audit read the .001s clamps as a violation; they are the load-
    bearing technique here — the door's transitionend needs an end, and the
    iteration-count + delay pins stop the loops. Recorded as narrowed."""
    block = CSS[CSS.index("prefers-reduced-motion"):][:1400]
    assert "animation-iteration-count: 1 !important" in block
    assert "animation-delay: 0s !important" in block
    assert "body::before { animation: none !important; }" in CSS


# -- the extension's small debts ---------------------------------------------

def test_the_options_page_labels_point_at_their_inputs():
    ext = (ROOT / "extension" / "options.html").read_text(encoding="utf-8")
    assert '<label for="engineUrl">' in ext
    assert '<label for="engineToken">' in ext


def test_the_popup_version_reads_the_manifest():
    popup = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
    assert "api.runtime.getManifest()" in popup
    assert '$("ver").textContent = "v" + MANIFEST.version;' in popup


# -- i18n: the split-string duplicate word -----------------------------------

def test_the_ytdlp_tab_usher_line_reads_once():
    m = re.search(r"const STRINGS = \{ en: \{\}, id: \{(.*?)\n\} \};", APP, re.S)
    assert m, "STRINGS block shape changed"
    d = json.loads("{" + m.group(1) + "}")
    frag = d["The literal “every feature” switch. Once it is on, the arguments field in the "]
    assert frag.endswith("di ")
    assert "tab tab" not in frag + d["yt-dlp tab →"]
