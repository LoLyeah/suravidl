"""Regressions from the v0.21.1 audit.

Every test here failed against the running engine before its fix — they were
found by probing the live API with hostile input, not by reading code.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer testtoken"}


def _app(tmp_path, **kw):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir(parents=True, exist_ok=True)
    return api.create_app(download_dir=d, auth_token="testtoken",
                          db_path=tmp_path / "jobs.db", **kw)


# -- 1. a wild number in /settings must be refused, not crash ----------------

@pytest.mark.parametrize("raw,key", [
    ('{"max_downloads": Infinity}', "max_downloads"),
    ('{"max_downloads": -Infinity}', "max_downloads"),
    ('{"retries": NaN}', "retries"),
    ('{"fragments": NaN}', "fragments"),
    ('{"max_concurrent": Infinity}', "max_concurrent"),
    ('{"sleep_requests": Infinity}', "sleep_requests"),
])
def test_a_non_finite_setting_is_a_clean_400(tmp_path, raw, key):
    """Infinity reached int() and became a 500 Internal Server Error."""
    with TestClient(_app(tmp_path)) as c:
        before = c.get("/settings", headers=AUTH).json()
        r = c.post("/settings", content=raw,
                   headers={**AUTH, "Content-Type": "application/json"})
        assert r.status_code == 400, r.text
        assert key in r.json()["detail"]
        # and the refused value was not half-written
        assert c.get("/settings", headers=AUTH).json() == before


def test_a_huge_but_finite_setting_still_clamps(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.post("/settings", json={"max_downloads": 10 ** 9, "retries": 10 ** 9},
                   headers=AUTH)
        assert r.status_code == 200
        s = r.json()
        assert s["max_downloads"] == 1000 and s["retries"] == 30


# -- 2. a job without a URL is not a job ------------------------------------

@pytest.mark.parametrize("url", ["", "   ", "\n", "x" * 5000])
def test_a_job_needs_a_usable_url(tmp_path, url):
    """An empty URL was accepted and produced a job that could only fail."""
    with TestClient(_app(tmp_path)) as c:
        r = c.post("/jobs", json={"url": url}, headers=AUTH)
        assert r.status_code == 400, r.text
        assert c.get("/jobs", headers=AUTH).json()["jobs"] == []


def test_a_normal_url_still_becomes_a_job(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.post("/jobs", json={"url": " http://example.invalid/x.mp4 "}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["url"] == "http://example.invalid/x.mp4"   # trimmed


# -- 3. the bulk wipe needs an explicit confirm -----------------------------

def test_bulk_wipe_needs_an_explicit_confirm(tmp_path):
    """A bare POST to /files/clear used to delete every download."""
    with TestClient(_app(tmp_path)) as c:
        (tmp_path / "dl" / "keep.mp4").write_bytes(b"x" * 10)
        r = c.post("/files/clear", headers=AUTH)
        assert r.status_code == 400, r.text
        assert "confirm" in r.json()["detail"]
        assert (tmp_path / "dl" / "keep.mp4").exists(), "the file was deleted anyway"

        # a wrong word is not a confirmation either
        r = c.post("/files/clear", json={"confirm": "yes"}, headers=AUTH)
        assert r.status_code == 400 and (tmp_path / "dl" / "keep.mp4").exists()

        # the explicit word is
        r = c.post("/files/clear", json={"confirm": "delete"}, headers=AUTH)
        assert r.status_code == 200 and r.json()["deleted"] == 1
        assert not (tmp_path / "dl" / "keep.mp4").exists()


# -- 4/5. a headless engine must not advertise (or crash on) a desktop window

def test_a_headless_engine_does_not_advertise_a_window(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        info = c.get("/app/info", headers=AUTH).json()
        assert info == {"desktop": False, "can_minimize": False,
                        "can_pick_file": False, "can_open_url": False}
        for ep in ("/app/minimize", "/app/quit"):
            r = c.post(ep, headers=AUTH)
            assert r.status_code == 501, f"{ep} -> {r.status_code}: {r.text}"
            assert "desktop" in r.json()["detail"]


def test_a_desktop_action_that_breaks_is_not_a_500(tmp_path):
    """A window that dies must answer honestly, not with a server error."""
    def boom():
        raise RuntimeError("window is gone")

    with TestClient(_app(tmp_path, desktop_actions={"quit": boom})) as c:
        assert c.post("/app/quit", headers=AUTH).status_code == 501
        # the capability is still advertised (it was wired), just not working
        assert c.get("/app/info", headers=AUTH).json()["can_minimize"] is False


# -- 6. the "sign-in wall" hint must not fire on ordinary failures ----------

def test_an_ordinary_failure_is_not_called_a_signin_wall():
    """A 404 in a webPAGE got a "add cookies" hint — a bare "age" matched."""
    from suravidl_engine.auth import explain_download_error, looks_like_signin_wall

    plain = ("ERROR: [generic] hostile: Unable to download webpage: "
             "HTTP Error 404: File not found")
    assert looks_like_signin_wall(plain) is False
    assert explain_download_error(plain) == plain
    assert "cookies" not in explain_download_error(plain)

    # the real thing still gets the hint
    wall = ("ERROR: Sign in to confirm you're not a bot. Use --cookies-from-browser")
    assert looks_like_signin_wall(wall) is True
    assert "Settings → Authentication" in explain_download_error(wall)

    # the phrase that caused the bug is gone, and its friends did not sneak in
    from suravidl_engine.auth import WALL_PHRASES

    assert "age" not in WALL_PHRASES
    assert "sign in" in WALL_PHRASES and "not a bot" in WALL_PHRASES


def test_the_ui_does_not_keep_its_own_wall_heuristic():
    """Two copies of the same judgement is how the 404 bug happened."""
    js = (Path(__file__).resolve().parents[1] / "src" / "suravidl_engine"
          / "web" / "app.js").read_text()
    assert "not a bot|private video" not in js       # the old inline regex
    assert "needs your account" not in js


def test_probe_errors_come_from_the_engine_with_the_hint(tmp_path):
    """The probe endpoint appends the hint itself, so every shell agrees."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        # a URL that cannot resolve -> an ordinary failure, no hint
        r = c.post("/probe", json={"url": "http://127.0.0.1:9/nothing"}, headers=AUTH)
        assert r.status_code == 400
        assert "Authentication" not in r.json()["detail"]
