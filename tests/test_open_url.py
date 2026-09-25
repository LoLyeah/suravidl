"""Opening external links (update banner): desktop shell + validation."""
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

AUTH = {"Authorization": "Bearer t"}


def _app(tmp_path, **kw):
    return create_app(download_dir=tmp_path / "dl", auth_token="t",
                      db_path=tmp_path / "jobs.db", **kw)


def test_info_reports_open_url_capability(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        assert c.get("/app/info", headers=AUTH).json()["can_open_url"] is False
    opened = []
    with TestClient(_app(tmp_path, desktop_actions={"open_url": opened.append})) as c:
        assert c.get("/app/info", headers=AUTH).json()["can_open_url"] is True


def test_open_url_calls_the_desktop_opener(tmp_path):
    opened = []
    with TestClient(_app(tmp_path, desktop_actions={"open_url": opened.append})) as c:
        r = c.post("/app/open-url",
                   json={"url": "https://github.com/LoLyeah/suravidl/releases/tag/v0.13.0"},
                   headers=AUTH)
        assert r.status_code == 200, r.text
        assert r.json()["opened"].startswith("https://github.com/")
    assert opened == ["https://github.com/LoLyeah/suravidl/releases/tag/v0.13.0"]


def test_open_url_rejects_non_https(tmp_path):
    opened = []
    with TestClient(_app(tmp_path, desktop_actions={"open_url": opened.append})) as c:
        for bad in ("http://example.com", "file:///etc/passwd",
                    "javascript:alert(1)", "", "   ", "not a url"):
            r = c.post("/app/open-url", json={"url": bad}, headers=AUTH)
            assert r.status_code == 400, (bad, r.status_code)
    assert opened == []


def test_open_url_501_without_desktop_shell(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.post("/app/open-url", json={"url": "https://example.com"},
                   headers=AUTH)
        assert r.status_code == 501


def test_open_url_requires_auth(tmp_path):
    with TestClient(_app(tmp_path, desktop_actions={"open_url": lambda u: None})) as c:
        r = c.post("/app/open-url", json={"url": "https://example.com"})
        assert r.status_code in (401, 403)
