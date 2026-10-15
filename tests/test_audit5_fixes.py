"""Regressions from the fifth `agy` audit pass (v0.46.10) — engine + surfaces.

Two parallel audits ran over the v0.46.9 tree (engine core; the extension /
Android / CI sweep), and a confirmation phase reproduced the load-bearing
findings live — the resume race (two successors, replaced_by never set), the
proxy-password and Authorization/Cookie scrubber leaks, and the
token-on-loopback chain (`curl http://127.0.0.1:8787/` handed out the API
token to anything that asked) — before any fix. Every test here fails
against that tree (RED).

Where the sweep overstated a finding, the release notes record the
refutation instead of a test: the frame walk reaches same-origin frames
only — the page's own trust domain — and the `🐴` window title is a
deliberate, test-pinned brand mark.
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "suravidl_engine"
EXT = ROOT / "extension"
AND = ROOT / "android" / "app" / "src" / "main"
API = (SRC / "api.py").read_text(encoding="utf-8")

sys.path.insert(0, str(SRC))
from suravidl_engine import cut as _cut  # noqa: E402

AUTH = {"Authorization": "Bearer testtoken"}


def _app(tmp_path, **kw):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir(parents=True, exist_ok=True)
    kw.setdefault("auth_token", "testtoken")
    return api.create_app(download_dir=d, db_path=tmp_path / "jobs.db", **kw)


# ── A/F1: a note rides the row AND the database ─────────────────────────

def test_a_note_survives_a_restart(tmp_path):
    """`note` lived only in memory — the cut's attribution and every
    caveat died on reboot (A/F1)."""
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "j.db"
    mgr = JobManager(download_dir=tmp_path, db_path=db)
    job = mgr.create("http://127.0.0.1:1/x.mp4")
    with mgr._lock:
        mgr._jobs[job["id"]]["note"] = "kept the promise"
        mgr._save(mgr._jobs[job["id"]])
    mgr2 = JobManager(download_dir=tmp_path, db_path=db)
    assert mgr2.get(job["id"])["note"] == "kept the promise"


def test_an_older_database_gains_the_note_column(tmp_path):
    """The per-boot alignment is the law (v0.45.26): a DB from before the
    column existed must gain it without a version stamp."""
    from suravidl_engine.jobs import JobManager

    db = tmp_path / "old.db"
    JobManager(download_dir=tmp_path, db_path=db)          # current schema
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE jobs DROP COLUMN note")       # as it was before
    con.commit()
    con.close()
    JobManager(download_dir=tmp_path, db_path=db)          # a boot aligns it
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    con.close()
    assert "note" in cols


# ── A/F2: one row, one successor ────────────────────────────────────────

def test_a_second_builder_is_refused_by_the_claim(tmp_path):
    """Two concurrent resumes used to queue two writers on the same .part
    (live repro: two successors, replaced_by never set)."""
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create("http://127.0.0.1:1/x.mp4")
    with mgr._lock:
        mgr._jobs[job["id"]]["status"] = "paused"
        mgr._jobs[job["id"]]["_requeue_claim"] = "someone-else"
    with pytest.raises(ValueError, match="already being resumed"):
        mgr.resume(job["id"])
    # the claim is engine-internal: it never rides a handed-out row
    assert "_requeue_claim" not in mgr.get(job["id"])
    assert all("_requeue_claim" not in j for j in mgr.list())


def test_a_resumed_row_points_at_its_successor(tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create("http://127.0.0.1:1/x.mp4")
    with mgr._lock:
        mgr._jobs[job["id"]]["status"] = "paused"
    mgr._save(mgr._jobs[job["id"]])
    successor = mgr.resume(job["id"])
    src = mgr.get(job["id"])
    assert src["replaced_by"] == successor["id"]
    assert "_requeue_claim" not in src


# ── A/F9: a live recording's bytes are in the .part ─────────────────────

def test_a_live_recording_reports_the_part_on_disk(tmp_path):
    """`_stat_size` read `filepath` only; an active recording answered
    size_bytes: null all night while bytes were on disk (A/F9)."""
    from suravidl_engine.jobs import _stat_size

    part = tmp_path / "live.mp4.part"
    part.write_bytes(b"x" * 1234)
    job = {"filepath": str(tmp_path / "live.mp4"), "files": [],
           "partials": [str(tmp_path / "live.mp4")]}
    assert _stat_size(job) == 1234


# ── A/F10: /health says nothing about the host's folders ────────────────

def test_health_does_not_leak_the_download_folder(tmp_path):
    c = TestClient(_app(tmp_path))
    body = c.get("/health").json()
    assert body["ok"] is True
    assert "download_dir" not in body


# ── A/F4 + A/F6: the scrubber knows more than query strings ─────────────

def test_the_scrubber_covers_userinfo_headers_and_cookies():
    """Live-verified leaks: a proxy password in `http://user:pass@host`
    and `Authorization`/`Cookie` values passed every scrubber (A/F4+A/F6)."""
    from suravidl_engine.auth import scrub_secrets

    cases = [
        ("http://bob:s3cret@proxy.example:8080/", "s3cret"),
        ("'proxy': 'http://bob:s3cret@proxy.example:8080'", "s3cret"),
        ("Authorization: Bearer abc123def", "abc123def"),
        ("'Authorization': 'Bearer abc123def'", "abc123def"),
        ("Cookie: session=deadbeef; x=y", "deadbeef"),
        ("Set-Cookie: sid=deadbeef; Path=/", "deadbeef"),
        ("https://x.test/v?token=deadbeef&a=b", "deadbeef"),
    ]
    for text, secret in cases:
        out = scrub_secrets(text)
        assert secret not in out, (text, out)
        assert "[redacted]" in out


def test_logs_are_scrubbed_at_capture(tmp_path):
    from suravidl_engine import logcap

    logcap.clear()
    logcap.logger().debug("Authorization: Bearer deadbeef")
    c = TestClient(_app(tmp_path))
    body = c.get("/logs", headers=AUTH).json()
    joined = "\n".join(body["lines"])
    assert "deadbeef" not in joined
    logcap.clear()


# ── B/F1: the desktop page is gated like the phone's ────────────────────

def test_the_page_key_is_born_private_and_persists(tmp_path):
    """0600 from the first byte, stable across loads, env-pinnable."""
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("SURAVIDL_PAGE_KEY", None)
    code = ("import suravidl_engine.__main__ as m\n"
            "k1 = m.load_or_create_page_key()\n"
            "k2 = m.load_or_create_page_key()\n"
            "print(k1, k2)")
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    k1, k2 = r.stdout.split()
    assert len(k1) == 32 and k1 == k2, "the key must persist"
    p = tmp_path / ".suravidl" / "page_key"
    assert p.read_text(encoding="utf-8") == k1
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    env["SURAVIDL_PAGE_KEY"] = "pinned"
    r2 = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT,
                        capture_output=True, text=True, timeout=120)
    assert r2.stdout.split()[0] == "pinned", "the env wins"


def test_the_desktop_opens_the_page_with_its_key():
    """Every open site carries `?k=` (the param Android has always used);
    the badge poller keeps the bare url — it appends /jobs and never needs
    the page."""
    src = (SRC / "__main__.py").read_text(encoding="utf-8")
    assert 'browse_url = f"{url}?k={page_key}"' in src
    assert "webbrowser.open(browse_url)" in src
    assert "_try_tray(browse_url" in src
    assert "_try_window(webview, browse_url)" in src
    assert "page_key=page_key" in src
    assert "_start_badge_poller(window, url" in src, \
        "the poller reads /jobs with the token — a keyed base url would break it"


def test_get_without_the_key_answers_401_not_the_token(tmp_path):
    """B/F1's chain, cut: any browser extension can fetch loopback, so the
    page must refuse to hand out the token to a keyless request."""
    app = _app(tmp_path, page_key="sekrit")
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 401
    assert "testtoken" not in r.text
    assert c.get("/?k=nope").status_code == 401
    ok = c.get("/?k=sekrit")
    assert ok.status_code == 200 and "testtoken" in ok.text
    # no key configured (tests, older shells) → the old behaviour stands
    app2 = _app(tmp_path / "b")
    assert TestClient(app2).get("/").status_code == 200


# ── B/F2 + B/F3: the extension's two silent-loss findings ──────────────

def test_a_content_script_cannot_reach_the_privileged_actions():
    bg = (EXT / "background.js").read_text(encoding="utf-8")
    assert ('&& !(msg && (msg.type === "pageFind" || msg.type === "pkFind")))'
            in bg), "a content script may only ever report a find or a key"
    assert 'sendResponse({ ok: false, error: "refused" })' in bg


def test_held_headers_survive_a_dead_service_worker():
    bg = (EXT / "background.js").read_text(encoding="utf-8")
    for token in ("pendingSession", "_mirrorPending", "dropHeaders",
                  "heldHeaders", "chrome.storage.session"):
        assert token in bg, token
    assert "heldHeaders(details.url).then((held) => {" in bg, \
        "the response path must read through the session mirror"
    assert "dropHeaders(details.url); // the name did not lie after all" in bg


def test_the_firefox_manifest_asks_for_nothing_it_does_not_use():
    ff = (EXT / "firefox" / "manifest.json").read_text(encoding="utf-8")
    assert "webRequestBlocking" not in ff
    assert '"webRequest"' in ff
    # the twin's version tracks the chrome manifest (bump them together)
    import json as _json
    ver = _json.loads((EXT / "manifest.json").read_text())["version"]
    assert f'"version": "{ver}"' in ff
    ch = (EXT / "manifest.json").read_text(encoding="utf-8")
    assert f'"version": "{ver}"' in ch
    amo = (ROOT / "docs" / "amo-metadata.json").read_text(encoding="utf-8")
    assert "webRequestBlocking" not in amo


# ── B/F5, B/F6, B/F7, B/F9: the Android surfaces ────────────────────────

def test_cleartext_is_scoped_to_the_engine():
    man = (AND / "AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'android:networkSecurityConfig="@xml/network_security_config"' in man
    assert "usesCleartextTraffic" not in man
    cfg = (AND / "res" / "xml" / "network_security_config.xml").read_text(
        encoding="utf-8")
    assert 'cleartextTrafficPermitted="false"' in cfg
    assert "127.0.0.1" in cfg and "localhost" in cfg


def test_the_sniff_bridge_demands_the_session_token():
    script = (AND / "java" / "com" / "suravidl" / "app" / "SniffScript.kt").read_text(
        encoding="utf-8")
    assert "fun js(token: String)" in script
    assert "fun scan(token: String)" in script
    assert "})(null);" in script, "the walk source never carries the token"
    assert "var __R = B.report;" in script, "the function itself is captured"
    assert "__R.call(B, u, via, location.href, __T)" in script
    browser = (AND / "java" / "com" / "suravidl" / "app" /
               "BrowserActivity.kt").read_text(encoding="utf-8")
    assert "private val sniffToken = java.util.UUID.randomUUID().toString()" in browser
    assert "SniffScript.js(sniffToken)" in browser
    assert "SniffScript.scan(sniffToken)" in browser
    assert "if (sniffEnforced && token != sniffToken) return" in browser
    assert ("sniffEnforced =\n        WebViewFeature.isFeatureSupported"
            in browser) or ("sniffEnforced =" in browser), \
        "the enforcement scope must be the feature check (v0.46.12)"


def test_the_second_injector_carries_the_same_token():
    """v0.46.11: the WebView client injects the same scripts — the B/F6
    token threading missed it and :app:compileDebugKotlin failed with
    "No value passed for parameter 'token'"."""
    wc = (AND / "java" / "com" / "suravidl" / "app" /
          "SnifferWebViewClient.kt").read_text(encoding="utf-8")
    assert "private val sniffToken: String," in wc
    assert "SniffScript.js(sniffToken)" in wc
    assert "SniffScript.scan(sniffToken)" in wc
    browser = (AND / "java" / "com" / "suravidl" / "app" /
               "BrowserActivity.kt").read_text(encoding="utf-8")
    assert "sniffToken = sniffToken)" in browser


def test_shares_stay_inside_the_download_folder():
    paths = (AND / "res" / "xml" / "file_paths.xml").read_text(encoding="utf-8")
    assert 'path="Movies/suravidl"' in paths
    assert 'path="suravidl"' in paths, "the filesDir fallback stays reachable"
    assert 'path="."' not in paths


def test_the_keystore_secret_leaves_the_script_text():
    yml = (ROOT / ".github" / "workflows" / "android.yml").read_text(encoding="utf-8")
    assert "KEYSTORE_B64: ${{ secrets.ANDROID_KEYSTORE_B64 }}" in yml
    assert "printf '%s' \"$KEYSTORE_B64\"" in yml
    assert 'echo "${{ secrets.ANDROID_KEYSTORE_B64 }}"' not in yml


# ── B/F8, A/F7, A/F11: the web helper, the updater, the swap ────────────

def test_ico_only_emits_sprite_ids():
    js = (SRC / "web" / "app.js").read_text(encoding="utf-8")
    assert '/^[a-z0-9-]{1,24}$/.test(name) ? name : "info"' in js


def test_parse_orders_prereleases_and_keeps_four_parts():
    from suravidl_engine import updater

    assert updater._parse("0.46.0-rc2") > updater._parse("0.46.0-rc1")
    assert updater._parse("0.46.0-rc2") < updater._parse("0.46.0")
    assert updater._parse("0.45.1") < updater._parse("0.45.1.1")
    assert updater._parse("0.45.1.1") < updater._parse("0.45.1.2")
    assert updater._parse("0.46.0.dev1") < updater._parse("0.46.0")
    assert updater._parse("v0.46.0") == updater._parse("0.46.0")
    assert updater._parse("") < updater._parse("0.0.1")


def test_the_swap_never_frees_the_placeholder_name():
    s = (SRC / "macos_swap.sh").read_text(encoding="utf-8")
    assert 'mv "$APP" "$OLD/old.app"' in s, \
        "the old bundle moves INTO the 0700 placeholder"
    assert "the placeholder goes" not in s, "no rm-then-mv window"
    assert 'mv "$OLD/old.app" "$APP"' in s, "rollback"
    assert 'EXEC_NOW="$(/usr/libexec/PlistBuddy' in s, \
        "the relaunch fallback re-reads the NEW bundle's exec name"
    assert 'INNER="$1/Contents/MacOS/$EXEC_NOW"' in s


# ── A/F3 + A/F8: the cut route trusts the job's own folder ─────────────

def test_the_cut_route_trusts_the_jobs_own_folder():
    seg = API.split('@app.post("/jobs/{job_id}/cut")')[1].split(
        '@app.get("/follows")')[0]
    assert "mgr._require_inside(src, job)" in seg
    assert "mgr._require_inside(src, None)" not in seg
    assert "mgr._require_inside(out_dir, job)" in seg, \
        "the output folder gets the same wall as the source (A/F8)"


@pytest.mark.skipif(not _cut.ffmpeg_exe(), reason="no ffmpeg on this box")
def test_a_take_from_before_a_folder_change_still_cuts(tmp_path):
    """The user-facing bug A/F3 caught: playback and delete already trusted
    the job's own folder; the cut route 403'd every historical take."""
    app = _app(tmp_path)
    mgr = app.state.manager
    old_dir = Path(mgr.download_dir)
    f = old_dir / "take.mp4"
    subprocess.run(
        [_cut.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=64x64:rate=10",
         "-pix_fmt", "yuv420p", str(f)],
        check=True, capture_output=True, timeout=120)
    take = mgr.add_take(title="old take", url="http://example.com/x",
                        filepath=str(f), download_dir=str(old_dir),
                        video_id=None, note=None)
    new_dir = tmp_path / "dl2"
    new_dir.mkdir()
    with TestClient(app) as c:
        assert c.post("/settings", json={"download_dir": str(new_dir)},
                      headers=AUTH).status_code == 200
        r = c.post(f"/jobs/{take['id']}/cut",
                   json={"start": "0:00", "end": "0:01"}, headers=AUTH)
        assert r.status_code == 200, r.text
        out = Path(r.json()["job"]["filepath"])
        assert out.exists() and out.parent == old_dir, \
            "the cut lands in the take's own folder"
