"""Authenticated video, round two (v0.27.0).

The plan agreed 2026-09-28: cookies already exist everywhere (file, browser,
encrypted Android vault, the in-app browser's own jar at handoff). The two
real gaps were:

- **Facebook-class fingerprinting**: with cookies alone, yt-dlp still gets
  "Cannot parse data" from sites that gatekeep on HTTP header fingerprints.
  Upstream's fix is impersonation (curl_cffi) — the app did not have it
  anywhere. It is a settings field now, validated at save time, refused with
  the missing package's name when the backend is not there, carried by the
  ONE options path to probes and downloads alike, and the desktop builds
  travel with curl_cffi (selftest-gated in CI).
- **Stale-cookie silence**: an expired cookies.txt failed with the same words
  as no cookies at all. The sign-in-wall hint now says the cookies may have
  expired; the Android vault says *when* the cookies were imported.
"""
import importlib.util
import functools
import http.server
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

ROOT = Path(__file__).parent.parent
ENGINE = ROOT / "src" / "suravidl_engine"
WEB = ENGINE / "web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer t"}

CLIENTS = ("chrome", "firefox", "safari", "edge")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture()
def fixture_server():
    handler = functools.partial(QuietHandler, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def make_app(tmp_path, **kw):
    return create_app(download_dir=tmp_path / "dl", auth_token="t",
                      db_path=tmp_path / "jobs.db", **kw)


def _seg(source: str, start: str, end: str = "\nfunction ") -> str:
    return source.split(start)[1].split(end, 1)[0]


# -- 1. the setting itself --------------------------------------------------

def test_impersonate_defaults_to_off_and_is_a_settings_key(tmp_path):
    from suravidl_engine.settings import DEFAULTS

    assert DEFAULTS.get("impersonate") == "", "off by default"
    c = TestClient(make_app(tmp_path))
    s = c.get("/settings", headers=AUTH).json()
    assert s["impersonate"] == "", "every shell reads it from the engine"


def test_only_the_known_clients_are_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr("suravidl_engine.download_opts.impersonate_available",
                        lambda: True)
    c = TestClient(make_app(tmp_path))
    r = c.post("/settings", headers=AUTH, json={"impersonate": "netscrape"})
    assert r.status_code == 400
    assert "chrome" in r.json()["detail"], "the refusal names the real options"
    ok = c.post("/settings", headers=AUTH, json={"impersonate": "chrome"})
    assert ok.status_code == 200 and ok.json()["impersonate"] == "chrome"
    off = c.post("/settings", headers=AUTH, json={"impersonate": ""})
    assert off.status_code == 200 and off.json()["impersonate"] == ""


def test_saving_impersonate_without_the_backend_is_refused(tmp_path, monkeypatch):
    """A setting that cannot possibly work must not save silently."""
    monkeypatch.setattr("suravidl_engine.download_opts.impersonate_available",
                        lambda: False)
    c = TestClient(make_app(tmp_path))
    r = c.post("/settings", headers=AUTH, json={"impersonate": "chrome"})
    assert r.status_code == 400
    assert "curl_cffi" in r.json()["detail"], \
        "the message names the missing piece, not a mystery"


def test_every_client_is_one_yt_dlp_resolves(tmp_path, monkeypatch):
    """The four names are yt-dlp's, not ours — each must build a real target."""
    monkeypatch.setattr("suravidl_engine.download_opts.impersonate_available",
                        lambda: True)
    from suravidl_engine.download_opts import IMPERSONATE_CLIENTS

    assert tuple(IMPERSONATE_CLIENTS) == CLIENTS
    import yt_dlp

    for who in CLIENTS:
        cli = yt_dlp.parse_options(["--impersonate", who]).ydl_opts["impersonate"]
        assert str(cli).lower().startswith(who), f"{who} is not a real target"


# -- 2. the one options path ----------------------------------------------

def test_probe_and_download_alike_carry_impersonate(tmp_path, monkeypatch):
    monkeypatch.setattr("suravidl_engine.download_opts.impersonate_available",
                        lambda: True)
    from suravidl_engine.download_opts import build_download_opts, probe_extra_opts

    settings = {"impersonate": "chrome"}
    dl = build_download_opts(settings, tmp_path)
    assert str(dl.get("impersonate")) == "chrome", \
        "the download options must carry it"
    assert str(probe_extra_opts(settings).get("impersonate")) == "chrome", \
        "a probe hits the same bot wall first — it must impersonate too"
    # the target is yt-dlp's own object, spelled the way its CLI spells it
    import yt_dlp

    cli = yt_dlp.parse_options(["--impersonate", "chrome"]).ydl_opts["impersonate"]
    assert str(cli) == str(dl["impersonate"])


def test_building_with_impersonate_and_no_backend_fails_loudly(tmp_path, monkeypatch):
    """Defense in depth: if the saved setting outlives the package, the job
    must fail with words, not quietly download without impersonation."""
    monkeypatch.setattr("suravidl_engine.download_opts.impersonate_available",
                        lambda: False)
    from suravidl_engine.download_opts import build_download_opts

    with pytest.raises(ValueError, match="curl_cffi"):
        build_download_opts({"impersonate": "chrome"}, tmp_path)


def test_an_impersonated_probe_really_goes_through(tmp_path, fixture_server):
    """The real client, the real fetch — no monkeypatching here. Runs wherever
    curl_cffi is installed (the venv, CI via the dev extra, the desktop
    builds); skipped only where it was never a dependency (Android)."""
    if not importlib.util.find_spec("curl_cffi"):
        pytest.skip("curl_cffi not installed here (Android / dev-lite)")
    c = TestClient(make_app(tmp_path))
    ok = c.post("/settings", headers=AUTH, json={"impersonate": "chrome"})
    assert ok.status_code == 200, ok.text
    r = c.post("/probe", headers=AUTH, json={"url": f"{fixture_server}/tiny.mp4"})
    assert r.status_code == 200, r.text
    assert r.json().get("title"), "the impersonated request must really work"


# -- 3. the stale-cookie hint ----------------------------------------------

def test_the_wall_hint_says_the_cookies_may_have_expired():
    from suravidl_engine.auth import explain_download_error

    out = explain_download_error("ERROR: Sign in to confirm you're not a bot.")
    assert "Settings → Authentication" in out
    assert "expired" in out, "an expired cookie fails like no cookie — say so"
    assert "Instagram" in out, "name the case people actually hit"


# -- 4. the shells ----------------------------------------------------------

def test_the_settings_screen_offers_impersonation():
    seg = HTML.split('id="setImpersonate"')[1].split("</select>")[0]
    for who in CLIENTS:
        assert f'value="{who}"' in seg, f"{who} must be pickable"
    assert 'value=""' in seg, "off must be the default pick"
    assert "Facebook" in seg, "say what it is actually for"
    assert 'id="impersonateRow"' in HTML
    # loaded, saved, and hidden on the phone (no curl_cffi there)
    assert 's.impersonate' in _seg(APP, "async function loadSettings()")
    assert 'impersonate: $("setImpersonate").value' in _seg(APP, "function saveSettings()")
    assert '"impersonateRow"' in APP and 'classList.add("hidden")' in APP


def test_the_vault_reports_when_the_cookies_were_imported():
    kt = (ROOT / "android/app/src/main/java/com/suravidl/app/CookieVault.kt").read_text()
    assert "imported" in kt and "SimpleDateFormat" in kt, \
        "status must carry the import date"
    test = (ROOT / "android/app/src/androidTest/java/com/suravidl/app/CookieVaultTest.kt").read_text()
    assert 'contains("imported")' in test, "and the device test must pin it"


# -- 5. packaging: the desktop builds travel with the backend --------------

def test_desktop_builds_carry_the_impersonation_backend():
    rel = (ROOT / ".github/workflows/release.yml").read_text()
    assert "curl_cffi" in rel, "the release build must install it"
    assert "SURAVIDL_EXPECT_IMPERSONATE" in rel, \
        "and the smoke test must fail a build that lost it"
    spec = (ROOT / "suravidl.spec").read_text()
    assert 'collect_all("curl_cffi")' in spec, "PyInstaller must collect it"
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "curl_cffi" in pyproject, \
        "the dev extra keeps CI able to prove the real thing"


def test_the_selftest_gate_fails_a_build_without_it(tmp_path, monkeypatch):
    import suravidl_engine.__main__ as m

    monkeypatch.setenv("SURAVIDL_EXPECT_IMPERSONATE", "1")
    monkeypatch.setattr(m, "_impersonation_probe",
                        lambda: (False, "no curl_cffi"))
    assert m.self_test(tmp_path / "dl1") is False, \
        "expected-but-missing must fail the build's smoke test"
    monkeypatch.setattr(m, "_impersonation_probe",
                        lambda: (True, "curl_cffi 0.x, chrome target loads"))
    assert m.self_test(tmp_path / "dl2") is True


def test_without_the_expectation_the_selftest_still_passes(tmp_path, monkeypatch):
    """The Android shell and dev-lite runs have no backend and must stay OK."""
    import suravidl_engine.__main__ as m

    monkeypatch.delenv("SURAVIDL_EXPECT_IMPERSONATE", raising=False)
    monkeypatch.setattr(m, "_impersonation_probe",
                        lambda: (False, "no curl_cffi"))
    assert m.self_test(tmp_path / "dl3") is True
