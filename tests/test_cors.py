"""Extension handoff contract: CORS preflight from chrome-extension:// origins."""
from fastapi.testclient import TestClient


def test_preflight_from_extension_origin_is_allowed(tmp_path):
    import vidl_engine.api as api

    app = api.create_app(download_dir=tmp_path, auth_token="t")
    client = TestClient(app)
    r = client.options(
        "/jobs",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnop",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == "chrome-extension://abcdefghijklmnop"
    assert "authorization" in r.headers.get("access-control-allow-headers", "").lower()


def test_preflight_from_random_site_is_not_allowed(tmp_path):
    import vidl_engine.api as api

    app = api.create_app(download_dir=tmp_path, auth_token="t")
    client = TestClient(app)
    r = client.options(
        "/jobs",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"
