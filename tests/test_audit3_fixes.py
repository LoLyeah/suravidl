"""Regressions from the third `agy` audit pass (v0.43.2) — engine + surfaces.

Two parallel audits ran over the v0.43.1 tree (engine core, and the
surfaces/automation). Every test here reproduced a real defect against that
tree (RED) before it was fixed, with two kinds of entries:

- behaviour tests for the engine (SSRF entry points, the active-shadow
  removal, stage concurrency, body/queue ceilings, file modes, the sidecar
  language regex, the Windows apply chain);
- source pins for things a Linux test box cannot execute — the workflow
  files, shell/batch-ish scripts, and Kotlin sources — following the
  house's existing pin style.

Where the report overstated a finding, the test records the narrower
truth and says so in its comment.
"""

import base64
import functools
import http.server
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app
from suravidl_engine.jobs import JobManager

AUTH = {"Authorization": "Bearer testtoken"}
ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D102 - silence test output
        pass


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(_Quiet, directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _client(tmp_path):
    app = create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                     db_path=tmp_path / "jobs.db")
    return TestClient(app)


# -- [E5] the SSRF gate lives at every door, not just classify --------------

def test_probe_refuses_a_link_local_address(tmp_path):
    """`blocked_reason` was enforced only in classify; /probe went straight
    to yt-dlp with whatever URL it was handed."""
    with _client(tmp_path) as c:
        r = c.post("/probe", json={"url": "http://169.254.169.254/latest/meta-data/"},
                   headers=AUTH)
        assert r.status_code == 400, r.text
        assert "link-local" in r.json()["detail"]
        r = c.post("/probe", json={"url": "http://metadata.google.internal/x"},
                   headers=AUTH)
        assert r.status_code == 400
        assert "metadata" in r.json()["detail"]


def test_jobs_refuse_a_link_local_address(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/jobs", json={"url": "http://169.254.169.254/x.mp4"},
                   headers=AUTH)
        assert r.status_code == 400, r.text
        assert "link-local" in r.json()["detail"]


def test_batch_reports_blocked_links_as_skipped(tmp_path, server):
    """A blocked link is a per-link problem: it must land in `skipped`
    (with the reason), never kill the good links beside it."""
    with _client(tmp_path) as c:
        r = c.post("/jobs/batch", headers=AUTH, json={"urls": [
            f"{server}/tiny.mp4", "http://169.254.169.254/x.mp4"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["jobs"]) == 1
        assert len(body["skipped"]) == 1
        assert "link-local" in body["skipped"][0]["error"]


def test_handoff_refuses_a_link_local_address(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/handoff", json={"url": "http://169.254.169.254/x.mp4"},
                   headers=AUTH)
        assert r.status_code == 400, r.text
        assert "link-local" in r.json()["detail"]


# -- [E1] the Windows apply chain: one opaque, unquotable argument ----------

def test_windows_apply_rides_as_one_encoded_argument():
    """The v0.41 chain handed cmd.exe a multi-command string; subprocess
    re-quotes such strings for CreateProcess (embedded quotes become `\\"`,
    which cmd does not parse as quoting), so any path metacharacter was a
    parsing edge. The fix: a PowerShell script as a single base64 token —
    there is nothing left for the quoting layer to touch."""
    from suravidl_engine.__main__ import _windows_apply_command

    installer = r"C:\Users\Bob & O'Brien\AppData\Local\suravidl-setup.exe"
    relaunch = r"C:\Users\Bob & O'Brien\AppData\Local\Programs\suravidl\suravidl.exe"
    argv = _windows_apply_command(
        installer, relaunch, pid=1234,
        log_path=r"C:\Users\Bob & O'Brien\.suravidl\update.log")
    assert argv[0] == "powershell.exe"
    assert "-EncodedCommand" in argv
    encoded = argv[-1]
    assert encoded and " " not in encoded and '"' not in encoded
    script = base64.b64decode(encoded).decode("utf-16-le")
    # the chain's promises, preserved
    assert "Start-Sleep" in script                     # the wait still rides
    assert "/CLOSEAPPLICATIONS" in script              # stragglers let go (RM)
    assert "/SUPPRESSMSGBOXES" in script               # and no box can hang it
    assert "Get-Process -Id 1234" in script            # v0.45.9: waits for the app
    assert script.index("Remove-Item") > script.index("/CLOSEAPPLICATIONS")
    assert "Bob & O''Brien" in script                  # PS quoting survives
    assert "Start-Process -FilePath" in script         # the app comes back

    lone = _windows_apply_command(r"C:\Temp\setup.exe", None, pid=7,
                                  log_path=r"C:\Temp\up.log")
    lone_script = base64.b64decode(lone[-1]).decode("utf-16-le")
    assert "suravidl.exe" not in lone_script           # nothing to relaunch


# -- [E2] removing the ACTIVE copy must not unlink it mid-run ---------------

def _plant_shadow(tmp_path):
    from suravidl_engine import __version__
    from suravidl_engine import ytdlp_update as yu

    sh = yu._shadow_dir(tmp_path / "jobs.db")
    pkg = sh / "yt_dlp"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("from .version import __version__\n")
    (pkg / "version.py").write_text('__version__ = "2026.9.9"\n')
    di = sh / "yt_dlp-2026.9.9.dist-info"
    di.mkdir()
    (di / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: yt-dlp\nVersion: 2026.9.9\n")
    (sh / "staged.json").write_text(json.dumps({
        "version": "2026.9.9", "baseline": "2026.1.1", "app": __version__}))
    return sh


def test_removing_an_active_copy_schedules_instead_of_deleting(tmp_path, monkeypatch):
    """yt-dlp imports its extractors lazily from the shadow's directory;
    deleting an active copy made the next unseen site die with
    ModuleNotFoundError. An active copy gets a marker instead."""
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path)
    monkeypatch.setattr(sys, "path", [str(sh)] + sys.path)
    r = yu.remove_shadow(db_path=tmp_path / "jobs.db")
    assert r["ok"] is True
    assert r.get("pending") is True
    assert r["removed"] is False
    assert sh.is_dir()                                  # still serving this run
    assert (sh / "remove-pending").exists()             # ...until the next one
    assert str(sh) in sys.path                          # loaded modules need it


def test_removing_a_staged_copy_still_deletes_at_once(tmp_path):
    """Nothing has imported from a staged copy — the marker dance would
    only be theater there."""
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path)
    r = yu.remove_shadow(db_path=tmp_path / "jobs.db")
    assert r["ok"] is True and r["removed"] is True and not r.get("pending")
    assert not sh.exists()


def test_a_scheduled_removal_does_not_break_lazy_submodule_imports(tmp_path, monkeypatch):
    """The causal story, made mechanical: a package whose submodule loads
    on demand must keep loading after `remove_shadow` ran on its ACTIVE
    directory (against the old code this raises ModuleNotFoundError)."""
    import importlib

    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path)
    pkg = sh / "lazypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def load():\n    from .sub import VALUE\n    return VALUE\n")
    (pkg / "sub.py").write_text("VALUE = 42\n")
    monkeypatch.setattr(sys, "path", [str(sh)] + sys.path)
    monkeypatch.delitem(sys.modules, "lazypkg", raising=False)
    import lazypkg

    yu.remove_shadow(db_path=tmp_path / "jobs.db")
    assert lazypkg.load() == 42                         # the lazy import still works
    importlib.invalidate_caches()


def test_the_next_start_drops_a_scheduled_removal(tmp_path, monkeypatch):
    """`activate()` is where the marker pays off: a fresh process deletes
    the copy before anything can import from it."""
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path)
    monkeypatch.setattr(sys, "path", [str(sh)] + sys.path)
    yu.remove_shadow(db_path=tmp_path / "jobs.db")
    # next boot: a fresh import path, activate() runs before any import
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(sh)])
    out = yu.activate(db_path=tmp_path / "jobs.db")
    assert out is None                                    # bundle serves
    assert not sh.exists()


def test_version_reports_a_pending_removal(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path)
    with _client(tmp_path) as c:
        assert c.get("/version", headers=AUTH).json()["remove_pending"] is False
    monkeypatch.setattr(sys, "path", [str(sh)] + sys.path)
    yu.remove_shadow(db_path=tmp_path / "jobs.db")
    with _client(tmp_path) as c:
        v = c.get("/version", headers=AUTH).json()
        assert v["remove_pending"] is True


def test_the_ui_words_a_pending_removal():
    appjs = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
    assert "remove_pending" in appjs
    assert "next start" in appjs


# -- [E4] stage_update is single-flight -------------------------------------

def test_stage_update_refuses_to_run_twice_at_once(tmp_path):
    """Two POST /update calls share os.getpid() and therefore the same
    part/stage paths; a non-blocking gate makes the second one say so."""
    from suravidl_engine import ytdlp_update as yu

    assert yu._STAGE_LOCK.acquire(blocking=False)
    try:
        def _must_not_fetch():
            raise AssertionError("sync fetch ran while a stage was in flight")

        r = yu.stage_update(db_path=tmp_path / "jobs.db", fetch_json=_must_not_fetch)
        assert r["ok"] is False and "already running" in r["detail"]
    finally:
        yu._STAGE_LOCK.release()


# -- [E7] a request-body ceiling exists -------------------------------------

def test_an_oversized_request_body_is_refused(tmp_path):
    with _client(tmp_path) as c:
        big = b"x" * (17 * 1024 * 1024)
        r = c.post("/jobs", content=big, headers={
            **AUTH, "Content-Type": "application/json"})
        assert r.status_code == 413, r.status_code
        # a normal-sized body still passes the gate
        r = c.post("/jobs", json={"url": ""}, headers=AUTH)
        assert r.status_code == 400                       # the app's own gate


# -- [E10] the pending queue has a ceiling ----------------------------------

def test_the_queue_refuses_runaway_backlog(tmp_path, monkeypatch):
    from suravidl_engine import jobs as jobs_mod

    mgr = JobManager(download_dir=tmp_path, db_path=tmp_path / "j.db")
    monkeypatch.setattr(mgr, "_run", lambda *a, **k: None)
    mgr._pending.extend([("x", None, None)] * jobs_mod.MAX_QUEUE)
    with pytest.raises(ValueError, match="queue is full"):
        mgr.create("https://example.com/v.mp4")


# -- [F5] the batch door rides per-link captured headers --------------------

def test_batch_rides_per_link_headers(tmp_path, monkeypatch, server):
    """The single quick door sends the captured headers; the batch door
    sent none. Same contract now, keyed by URL, with the flat `headers`
    as the fallback for links that have no captured map entry."""
    seen = {}
    orig = JobManager.create

    def spy(self, url, fmt=None, extra_headers=None, **kw):
        seen[url] = extra_headers
        return orig(self, url, fmt=fmt, extra_headers=extra_headers, **kw)

    monkeypatch.setattr(JobManager, "create", spy)
    u1, u2 = f"{server}/tiny.mp4", f"{server}/tiny2.mp4"
    with _client(tmp_path) as c:
        r = c.post("/jobs/batch", headers=AUTH, json={
            "urls": [u1, u2],
            "headers": {"X-Flat": "fallback"},
            "headers_by_url": {u1: {"Referer": "https://site/"}},
        })
        assert r.status_code == 200, r.text
    assert seen[u1] == {"Referer": "https://site/"}
    assert seen[u2] == {"X-Flat": "fallback"}


# -- [E8] sensitive files are born 0600, not chmodded later -----------------

def test_the_token_is_born_owner_only(tmp_path, monkeypatch):
    from suravidl_engine import __main__ as m

    monkeypatch.setattr(m, "token_path", lambda: tmp_path / "token")
    monkeypatch.setattr(os, "chmod", lambda *a, **k: None)   # no second chance
    token = m.load_or_create_token()
    assert token
    mode = (tmp_path / "token").stat().st_mode & 0o777
    assert mode == 0o600, oct(mode)


def test_settings_are_born_owner_only(tmp_path, monkeypatch):
    from suravidl_engine.settings import Settings

    monkeypatch.setattr(os, "chmod", lambda *a, **k: None)
    s = Settings(path=tmp_path / "settings.json")
    s.update({"download_dir": str(tmp_path)})
    mode = (tmp_path / "settings.json").stat().st_mode & 0o777
    assert mode == 0o600, oct(mode)


def test_presets_are_born_owner_only(tmp_path, monkeypatch):
    from suravidl_engine.presets import PresetStore

    monkeypatch.setattr(os, "chmod", lambda *a, **k: None)
    ps = PresetStore(path=tmp_path / "presets.json")
    ps.save("mine", {"preset": "audio-mp3"})
    mode = (tmp_path / "presets.json").stat().st_mode & 0o777
    assert mode == 0o600, oct(mode)


# -- [E6] the sidecar matcher only matches language tags --------------------

def test_sidecar_matching_leaves_decorated_names_alone(tmp_path):
    """`movie.hd-trailer.srt` is not a subtitle of movie.mp4 — the old
    regex said it was, and the trash button deleted it."""
    mgr = JobManager(download_dir=tmp_path, db_path=tmp_path / "j.db")
    d = tmp_path / "dl"
    d.mkdir()
    (d / "movie.mp4").write_bytes(b"x")
    keep = ["movie.en.srt", "movie.en-US.srt", "movie.zh-Hans.srt",
            "movie.es-419.srt", "movie.en-orig.srt", "movie.pt-BR.vtt"]
    decoys = ["movie.hd-trailer.srt", "movie.tv-edit.srt",
              "movie.re-cut.vtt", "movie.2.srt"]
    for n in keep + decoys:
        (d / n).write_text("s")
    got = {p.name for p in mgr._sidecars_for(d / "movie.mp4")}
    assert got == set(keep), got


# -- surfaces/automation pins (source level) --------------------------------

def test_workflows_never_interpolate_ref_name_into_run_blocks():
    """`github.ref_name` is attacker-influenced on a dispatch from a
    branch; it must ride an env var, not sit inside shell source."""
    pat = re.compile(r"\s*(REF_NAME|TAG|VERSION):")
    for name in ("release.yml", "android.yml", "ci.yml", "amo.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if "${{ github.ref_name }}" in line:
                assert pat.match(line), f"{name}:{i}: {line.strip()}"


def test_fetch_ffmpeg_verifies_against_committed_checksums():
    """The action verified the binaries against SHA256SUMS.txt from the
    SAME release — regenerable by whoever can rewrite the binaries."""
    action = (ROOT / ".github" / "actions" / "fetch-ffmpeg" / "action.yml").read_text()
    assert "checksums.txt" in action and "sha256sum -c" in action
    assert "curl -fsSL -o SHA256SUMS.txt" not in action   # no self-referential fetch
    sums = (ROOT / ".github" / "actions" / "fetch-ffmpeg" / "checksums.txt").read_text()
    lines = [l for l in sums.strip().splitlines() if l.strip()]
    assert len(lines) == 4
    assert all(re.match(r"^[0-9a-f]{64}  \S+\.so$", l) for l in lines)
    assert "67d2e7210a5701a733ca4f77d387aa1655d7578a86b1ae0613e7b33e9abe1977" in sums


def test_appimagetool_is_pinned_to_a_version_and_digest():
    """`continuous` is a moving release asset; the digest is the guard."""
    s = (ROOT / "scripts" / "build_appimage.sh").read_text()
    assert "TOOL_VERSION=1.9.1" in s
    assert "releases/download/${TOOL_VERSION}/" in s
    assert "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0" in s
    assert "sha256sum -c" in s
    assert "AppImageKit" not in s


def test_amo_log_is_scrubbed_before_it_is_uploaded():
    t = (ROOT / ".github" / "workflows" / "amo.yml").read_text()
    scrub = t.find("Scrub the submission log")
    upload = t.find("upload-artifact")
    assert scrub > 0 and upload > scrub, "scrub step must run before upload"
    assert "AMO_JWT_SECRET" in t[scrub:upload]


def test_the_keystore_password_never_touches_the_job_environment():
    t = (ROOT / ".github" / "workflows" / "android.yml").read_text()
    assert "ANDROID_KEYSTORE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}" in t
    assert "ANDROID_KEYSTORE_PASSWORD=" not in t or "$GITHUB_ENV" not in t, \
        "the password must be step-scoped, never exported job-wide"


def test_navguard_resolves_backslashes_like_a_browser():
    src = (ROOT / "android" / "app" / "src" / "main" / "java" / "com"
           / "suravidl" / "app" / "NavGuard.kt").read_text()
    assert "it == '\\\\'" in src, "host() must cut at the backslash browsers read as a slash"
    assert '.replace("\\t", "")' in src


def test_cookie_vault_io_failure_keeps_the_encrypted_copy():
    src = (ROOT / "android" / "app" / "src" / "main" / "java" / "com"
           / "suravidl" / "app" / "CookieVault.kt").read_text()
    assert "are intact" in src            # the write-failure message
    assert "out.delete()" in src          # the partial file goes, not the vault
