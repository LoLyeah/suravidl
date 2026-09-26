"""Engine serves the web UI on / with the API token injected."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

WEB = Path(__file__).resolve().parents[1] / "src" / "suravidl_engine" / "web"


def _app_js() -> str:
    return (WEB / "app.js").read_text()


def _app(tmp_path):
    import suravidl_engine.api as api

    return api.create_app(download_dir=tmp_path / "dl", auth_token="tok-123")


def test_index_serves_html_with_injected_token(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "suravidl" in r.text.lower()
        assert 'window.__SURAVIDL__' in r.text
        assert '\"token\": \"tok-123\"' in r.text
        assert '"theme": "dark"' in r.text
        assert '"glass": "frosted"' in r.text
        assert r.headers["content-type"].startswith("text/html")


def test_index_has_new_controls(tmp_path):
    """Settings + host controls the JS expects must exist in the markup."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        html = c.get("/").text
    for elem_id in ("setResume", "androidSection", "batteryBtn", "quitAppBtn",
                    "quitBtn", "minBtn", "ytdlpVer",
                    "setCookies", "setCookiesBrowser", "browseCookies",
                    "importCookies", "browserRow",
                    "audioRow", "audioNativeBtn", "audioM4aBtn", "audioMp3Btn",
                    "playlistRow", "playlistItems", "playlistBtn",
                    "settingsTabs", "spanel-general", "spanel-media",
                    "spanel-network", "spanel-auth", "spanel-device",
                    "spanel-advanced", "subwrap", "dlWhere", "copyDir",
                    "vaultSection", "vaultStatus", "deleteCookiesBtn",
                    "storageSection", "storageInfo", "clearDownloadsBtn",
                    "setTemplate", "setEmbMeta", "setEmbThumb", "setSubMode",
                    "setSubLangs", "setSubAuto", "setSbMode", "setSbCats",
                    "setArchive", "setFragments", "setRateLimit", "setProxy",
                    "setRawEnabled", "setRawArgs", "optionsBtn",
                    "optionsSearch", "optionsList", "optionsCount",
                    "sniffRow", "sniffBtn", "browserOffer", "browserOfferBtn"):
        assert f'id="{elem_id}"' in html, elem_id


def test_index_is_a_four_tab_shell(tmp_path):
    """Download · Queue · Settings · yt-dlp, with the curated groups in the
    yt-dlp tab (the shell the plan called M11)."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        html = c.get("/").text
    assert 'id="tabs"' in html and 'id="panels"' in html
    for tab in ("download", "queue", "settings", "ytdlp"):
        assert f'data-tab="{tab}"' in html, tab
        assert f'id="panel-{tab}"' in html, tab
    # exactly one panel is visible on load (the rest carry .hidden)
    assert 'class="panel" id="panel-download"' in html
    for tab in ("queue", "settings", "ytdlp"):
        assert f'class="panel hidden" id="panel-{tab}"' in html, tab
    # curated groups + the raw-args visibility switch
    for elem_id in ("setVerbose", "setIpVersion", "setNoCheckCerts",
                    "setSleepRequests", "setGeoBypass", "setGeoCountry",
                    "setExtractorArgs", "ytdlpSave", "ytdlpMsg",
                    "rawEditor", "rawOffHint", "queueCount",
                    # M18: retries / playlist limit / quality picks / cookie test
                    "setRetries", "setMaxDownloads", "qualityRow", "qualityBtns",
                    "testCookies", "cookiesMsg",
                    # M17: per-download overrides + presets + empty states
                    "ovBlock", "ovCount", "ovPreset", "ovApply", "ovClear",
                    "ovSubs", "ovSubLangs", "ovSb", "ovMeta", "ovThumb",
                    "ovRawRow", "ovRaw", "ovHint", "dlEmpty", "stabPresets",
                    "spanel-presets", "presetList", "presetName", "presetSave",
                    "presetMsg"):
        assert f'id="{elem_id}"' in html, elem_id
    # the old modal shells are gone: settings and the catalogue are tabs now
    assert 'id="settingsModal"' not in html
    assert 'id="optionsModal"' not in html
    # the confirm dialog is still a modal (small, transient)
    assert 'id="confirmModal"' in html


def test_static_assets_served(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as c:
        r = c.get("/static/app.js")
        assert r.status_code == 200
        assert "javascript" in r.headers["content-type"]
        r2 = c.get("/static/style.css")
        assert r2.status_code == 200
        assert "css" in r2.headers["content-type"]


def test_unknown_static_path_404s(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as c:
        assert c.get("/static/../../etc/passwd").status_code == 404


def test_app_js_wires_the_trash_button_and_the_android_flags(tmp_path):
    """The per-download delete is JS-side: pin the call and the confirm."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        js = c.get("/static/app.js").text
    assert "function deleteButton" in js
    assert "/delete`" in js or "/delete" in js
    assert "askConfirm" in js                 # never delete without asking
    assert "deleteMediaNamed" in js           # Android library copy goes too
    assert "settleThenDelete" in js           # a running job is stopped first
    # Android's WebView gets the no-blur flag (it smears backdrop-filter)
    assert 'dataset.host = "android"' in js


def test_progress_bar_styles_stay_scoped(tmp_path):
    """Regression: a bare `.fill` also hit the settings layout helper
    <div class="col fill"> and painted a giant gradient capsule over the
    fields. Component styles must not be bare single-word class selectors."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        css = c.get("/static/style.css").text
        html = c.get("/").text
    assert ".bar .fill {" in css and ".bar .fill.active::after {" in css
    assert re.search(r"(?m)^\.fill\s*\{", css) is None
    assert 'class="col fill"' not in html


def test_app_js_wires_the_minimal_inline_ids():
    """The quality picks and the cookie test are wired inline (the wheel is
    small here): make sure the halves stay together."""
    js = _app_js()
    assert "renderQualityRow" in js and "qualityBtns" in js
    assert "OV.qualities" in js and "renderQualityRow(url, info.site_quality)" in js
    assert "/auth/check" in js and 'testCookies").onclick' in js
    # the list must come from the engine, never hard-coded here
    assert "height<=1080" not in js
    assert "setRetries" in js and "setMaxDownloads" in js


def test_app_js_builds_the_playlist_pick_list():
    """M20 + v0.21.1: the entries are pickable and the range field stays the
    single thing handed to the engine — but the pick list only edits what it
    shows (a typed range past the listed entries is never narrowed), junk in
    the field disables the button, and "None" never means "the whole list"."""
    js = _app_js()
    assert "function parseItemRange" in js
    assert "function selectedPlaylistItems" in js
    assert "function syncPlaylistPicks" in js and "function checkboxFromRange" in js
    assert '"plpick"' in js and "b.dataset.index" in js
    assert '$("plAll").onclick = () => pickAll(true)' in js
    assert '$("plNone").onclick = () => pickAll(false)' in js
    assert '$("playlistItems").addEventListener("change", checkboxFromRange)' in js
    # the range field remains the single thing handed to the engine
    assert "body.playlist_items = playlistFieldText()" in js
    # and the button says how many videos it would start
    assert "Download ${count} picked" in js
    # v0.21.1 audit: "None" is a state of its own, because a blank field means
    # *everything* to the engine
    assert "PLAYLIST_NONE" in js and "pick items first" in js
    assert "pick at least one item first" in js
    # a typed range the list cannot represent survives, and junk is refused
    assert "representable" in js
    assert 'btn.textContent = junk ? "fix the range"' in js
    assert 'btn.disabled = Boolean(junk || none)' in js


def test_app_js_marks_the_remembered_quality_without_applying_it():
    """M20: a remembered pick is an offer — the chip is marked, not clicked."""
    js = _app_js()
    assert "renderQualityRow(url, info.site_quality)" in js
    assert "function renderQualityRow(url, remembered)" in js
    assert 'q.key === remembered' in js and "last ? q.label" in js
    # every chip still starts a download only on click
    # the trigger button rides along so a slow start can disable it (motion pass)
    assert "btn.onclick = () => startJob(url, q.fmt, null, false, btn)" in js


def test_index_has_the_playlist_pick_controls(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as c:
        html = c.get("/").text
    for elem_id in ('id="plAll"', 'id="plNone"', 'id="plCount"'):
        assert elem_id in html, elem_id


def test_app_js_accepts_a_shared_link_from_android():
    """M19: MainActivity calls window.suravidlShared(url) once the page is up.
    The hook must prefill and probe — never auto-download (the format is the
    user's choice, same as a paste)."""
    js = _app_js()
    assert "window.suravidlShared" in js
    hook = js.split("window.suravidlShared", 1)[1].split("/* ---------- boot", 1)[0]
    assert 'showTab("download")' in hook
    assert "$(\"url\").value" in hook and "doProbe()" in hook
    # no job is started behind the user's back
    assert "startJob" not in hook and 'api("/jobs"' not in hook


# ---------------------------------------------------------------------------
# v0.21.1 audit: the UI half — every one of these failed before the fix.
# ---------------------------------------------------------------------------

def test_app_js_spends_the_one_off_block_on_one_download():
    """"This download only" applied to every later job (and a preset value
    survived a field the user had cleared)."""
    js = _app_js()
    assert "clearOv();\n    PLAYLIST_NONE = false;\n" in js
    # emptying a field removes the preset's value instead of leaving it in force
    assert "delete patch.subtitles_mode;" in js
    assert "delete patch.sponsorblock_mode;" in js
    assert "delete patch.embed_metadata;" in js
    assert "delete patch.embed_thumbnail;" in js

def test_app_js_polls_once_at_a_time_and_says_when_it_cannot():
    """"A slow /jobs answer could repaint newer state, and a failing poll left
    an empty queue that read as 'nothing downloaded'."""
    js = _app_js()
    assert "if (JOBS_BUSY) return;" in js
    assert "if (seq !== JOBS_SEQ) return;" in js
    assert "function showQueueTrouble" in js and ".trouble" in js
    assert "cannot reach the engine" in js

def test_app_js_drops_a_stale_probe_and_its_chips():
    """A failed probe left the previous URL's quality chips armed, so a click
    downloaded the link the user had already replaced."""
    js = _app_js()
    assert "if (seq !== PROBE_SEQ) return;" in js
    assert '$("qualityRow").classList.add("hidden");' in js
    assert '$("qualityBtns").replaceChildren();' in js

def test_app_js_reports_a_preset_load_failure_as_what_it_is():
    """A 500 from /presets was rendered as "No presets yet"."""
    js = _app_js()
    assert "PRESETS_ERROR" in js
    assert "could not load presets" in js
    assert "your saved presets are not gone" in js

def test_app_js_only_closes_settings_when_it_is_open():
    """Escape was bound document-wide and yanked the user to Download from any
    tab; the hash router also ignored the hash changing under it."""
    js = _app_js()
    assert 'const panel = $("panel-settings");' in js
    assert 'if (panel && !panel.classList.contains("hidden")) closeSettings();' in js
    assert 'window.addEventListener("hashchange"，'.replace("，", ",") in js

def test_app_js_surfaces_a_failed_window_action_and_an_unreadable_size():
    js = _app_js()
    assert 'toast("could not minimize: " + e.message, "bad")' in js
    # the wipe confirm must not promise "0 files (0 B)" when the summary failed
    assert "size could not be read" in js
    assert 'catch(() => ({ files: 0, bytes: 0 }))' not in js

def test_app_js_keeps_unsaved_settings_through_a_tab_switch():
    js = _app_js()
    assert "let SETTINGS_DIRTY = false;" in js
    assert 'if (target === "settings" && !SETTINGS_DIRTY) loadSettings();' in js
    # the flag is set through the helper now, which also dots the tab
    assert "function markSettingsDirty(on)" in js
    assert "panel.addEventListener(ev, () => { markSettingsDirty(true); });" in js
    assert 'tab.classList.toggle("has-dirty", on)' in js
