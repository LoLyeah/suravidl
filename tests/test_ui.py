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
                    "quitBtn", "minBtn", "settingsModal",
                    "setCookies", "setCookiesBrowser", "browseCookies",
                    "importCookies", "browserRow",
                    "audioRow", "audioNativeBtn", "audioM4aBtn", "audioMp3Btn",
                    "playlistRow", "playlistItems", "playlistBtn",
                    "settingsTabs", "spanel-general", "spanel-media",
                    "spanel-network", "spanel-auth", "spanel-device",
                    "setTemplate", "setEmbMeta", "setEmbThumb", "setSubMode",
                    "setSubLangs", "setSubAuto", "setSbMode", "setSbCats",
                    "setArchive", "setFragments", "setRateLimit", "setProxy"):
        assert f'id="{elem_id}"' in html, elem_id


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
