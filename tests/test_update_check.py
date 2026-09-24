"""App update checker: compare engine version with the latest GitHub release."""
from fastapi.testclient import TestClient

from suravidl_engine import __version__
from suravidl_engine.api import create_app
from suravidl_engine.updater import check_update


def test_update_available_when_release_is_newer():
    r = check_update("0.5.0", fetch_fn=lambda repo: {
        "tag_name": "v0.6.0", "html_url": "https://example/releases/v0.6.0"})
    assert r["update_available"] is True
    assert r["latest"] == "0.6.0"
    assert r["url"].endswith("v0.6.0")


def test_no_update_when_same_or_older():
    same = check_update("0.6.0", fetch_fn=lambda repo: {"tag_name": "v0.6.0"})
    assert same["update_available"] is False

    older = check_update("0.6.0", fetch_fn=lambda repo: {"tag_name": "v0.5.9"})
    assert older["update_available"] is False


def test_newer_minor_and_patch_ordering():
    assert check_update(
        "0.5.10", fetch_fn=lambda repo: {"tag_name": "v0.5.9"}
    )["update_available"] is False  # 10 > 9 patches, we're ahead
    assert check_update(
        "0.5.9", fetch_fn=lambda repo: {"tag_name": "v0.5.10"}
    )["update_available"] is True


def test_network_error_is_reported_not_raised():
    def boom(repo):
        raise OSError("no network")

    r = check_update("0.5.0", fetch_fn=boom)
    assert r["update_available"] is False
    assert "no network" in r["error"]


def test_endpoint_reports_update_with_injected_checker():
    app = create_app(download_dir="/tmp/uc_test", auth_token="t",
                     db_path=":memory:",
                     update_check_fn=lambda: {
                         "current": __version__, "latest": "99.0.0",
                         "update_available": True,
                         "url": "https://example/releases/v99.0.0"})
    c = TestClient(app)
    r = c.get("/update-check", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    body = r.json()
    assert body["update_available"] is True
    assert body["latest"] == "99.0.0"


def test_endpoint_requires_auth():
    app = create_app(download_dir="/tmp/uc_test2", auth_token="t",
                     db_path=":memory:")
    c = TestClient(app)
    assert c.get("/update-check").status_code in (401, 403)
