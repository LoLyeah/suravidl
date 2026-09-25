"""Engine serves the web UI on / with the API token injected."""
from fastapi.testclient import TestClient


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
                    "quitBtn", "minBtn", "settingsBtn", "setClose",
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
                    "optionsSearch", "optionsList", "optionsCount"):
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
                    "rawEditor", "rawOffHint", "queueCount"):
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
