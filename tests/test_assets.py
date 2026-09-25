"""The UI assets must never go stale in an embedded WebView.

Root cause of the v0.11-CSS-on-v0.13-HTML report: `/` is a dynamic route
(always fresh) while `/static/*` came from StaticFiles with a Last-Modified
validator — Android's WebView kept serving the old style.css/app.js from its
heuristic cache. Two defences, both tested here.
"""
from fastapi.testclient import TestClient

from suravidl_engine import __version__


def _app(tmp_path):
    import suravidl_engine.api as api

    return api.create_app(download_dir=tmp_path / "dl", auth_token="tok-123")


def test_asset_urls_are_version_stamped(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        html = c.get("/").text
    for asset in ("style.css", "app.js", "icon.png"):
        assert f"/static/{asset}?v={__version__}" in html, asset


def test_static_assets_forbid_caching(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        for path in ("/static/style.css", "/static/app.js"):
            r = c.get(path)
            assert r.status_code == 200, path
            assert r.headers.get("cache-control") == "no-store", path


def test_versioned_asset_url_still_serves_the_file(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.get(f"/static/style.css?v={__version__}")
    assert r.status_code == 200
    assert "--accent" in r.text          # a real stylesheet, not a 404 page
