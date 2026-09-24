"""Version + self-update endpoints (updater injectable for tests)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def vclient(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="t")
    with TestClient(app) as c:
        yield c


def test_version_endpoint_reports_engine_and_yt_dlp(tmp_path):
    import suravidl_engine.api as api
    import suravidl_engine as pkg

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="t")
    with TestClient(app) as c:
        r = c.get("/version", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200
        body = r.json()
        assert body["engine"] == pkg.__version__
        assert body["yt_dlp"], "expected a yt-dlp version string"


def test_version_requires_auth(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="t")
    with TestClient(app) as c:
        assert c.get("/version").status_code == 401


def test_update_endpoint_runs_injected_updater(tmp_path):
    import suravidl_engine.api as api

    calls = []

    def fake_update():
        calls.append(1)
        return {"ok": True, "updated": True, "before": "2026.01.01",
                "after": "2026.02.01", "detail": "fake"}

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="t",
                         update_fn=fake_update)
    with TestClient(app) as c:
        r = c.post("/update", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200
        body = r.json()
        assert body["updated"] is True
        assert body["after"] == "2026.02.01"
        assert calls, "injected updater must have been called"


def test_update_requires_auth(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="t")
    with TestClient(app) as c:
        assert c.post("/update").status_code == 401
