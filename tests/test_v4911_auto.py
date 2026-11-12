"""v0.49.11 "the match" — cookies from browser: auto.

Detection is a read-only scan of the browsers' own cookie databases, ranked by
the site's session cookie and when it was last used. These tests build the two
database shapes on disk and check the answer, because the whole feature is
"which file says someone is signed in".
"""
from __future__ import annotations

import sqlite3
import time

import pytest

from suravidl_engine import auth


def _chromium_db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, "
                "expires_utc INTEGER, last_access_utc INTEGER)")
    con.executemany("INSERT INTO cookies VALUES (?,?,?,?)", rows)
    con.commit()
    con.close()


def _firefox_db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, "
                "expiry INTEGER, lastAccessed INTEGER)")
    con.executemany("INSERT INTO moz_cookies VALUES (?,?,?,?)", rows)
    con.commit()
    con.close()


def _chrome_time(when: float) -> int:
    return int((when + auth._CHROMIUM_EPOCH) * 1e6)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """Two browsers on disk; the test decides who is signed in."""
    chrome_root = tmp_path / "chrome"
    firefox_root = tmp_path / "ff"
    monkeypatch.setattr(auth, "_roots", lambda: [
        ("chrome", chrome_root, "chromium"),
        ("firefox", firefox_root, "firefox"),
    ])
    return {"chrome": chrome_root / "Default" / "Cookies",
            "firefox": firefox_root / "abc.default-release" / "cookies.sqlite"}


def test_the_browser_with_the_live_session_wins(rig):
    now = time.time()
    # Chrome has only the logged-out leftover; Firefox holds c_user
    _chromium_db(rig["chrome"], [(".facebook.com", "datr", 0, _chrome_time(now))])
    _firefox_db(rig["firefox"],
                [(".facebook.com", "c_user", 0, int((now - 60) * 1e6))])

    assert auth.detect_browser("facebook.com") == "firefox:abc.default-release"


def test_the_most_recently_used_session_wins_between_two(rig):
    now = time.time()
    _chromium_db(rig["chrome"],
                 [(".facebook.com", "c_user", 0, _chrome_time(now - 600))])
    _firefox_db(rig["firefox"],
                [(".facebook.com", "c_user", 0, int((now - 30) * 1e6))])

    assert auth.detect_browser().startswith("firefox:")


def test_a_profile_without_the_site_is_not_a_candidate(rig):
    _chromium_db(rig["chrome"], [(".example.com", "c_user", 0, _chrome_time(time.time()))])
    _firefox_db(rig["firefox"], [(".facebook.com", "c_user", 0, int(time.time() * 1e6))])

    assert auth.detect_browser("facebook.com").startswith("firefox:")


def test_nothing_signed_in_says_so(rig, monkeypatch):
    _chromium_db(rig["chrome"], [(".facebook.com", "datr", 0, _chrome_time(time.time()))])
    # a cookie for the site with no session among them is not a login
    assert auth.detect_browser("facebook.com") == ""
    monkeypatch.setattr(auth, "_roots", lambda: [])
    assert auth.detect_browser("facebook.com") == ""
    with pytest.raises(ValueError):
        auth.resolve_auto("facebook.com")


def test_expired_session_cookies_are_ignored(rig):
    past = time.time() - 86400
    _chromium_db(rig["chrome"],
                 [(".facebook.com", "c_user", int((past + auth._CHROMIUM_EPOCH) * 1e6),
                   _chrome_time(time.time()))])
    assert auth.detect_browser("facebook.com") == ""


def test_parse_browser_resolves_auto(rig):
    _firefox_db(rig["firefox"],
                [(".facebook.com", "c_user", 0, int(time.time() * 1e6))])
    spec = auth.parse_browser("auto")
    assert spec[0] == "firefox"
    assert "abc.default-release" in spec[1]


def test_settings_accept_auto_without_resolving(monkeypatch):
    from suravidl_engine import settings as settings_mod

    monkeypatch.setattr(auth, "_roots", lambda: [])
    store = settings_mod.Settings()
    out = store.update({"cookies_from_browser": "auto"})   # must not resolve
    assert out["cookies_from_browser"] == "auto"
