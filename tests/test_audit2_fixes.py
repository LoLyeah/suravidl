"""Regressions from the Antigravity (agy) audit — each one independently
reproduced here before it was fixed.

Findings came from an `agy` audit run over the v0.21.1 tree; every test in
this file failed against that tree (RED), most of them with the exact
behaviour the report described. Where the report overstated a finding, the
test records the narrower truth (see the comments).
"""

import functools
import http.server
import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yt_dlp
from fastapi.testclient import TestClient
from suravidl_engine.jobs import JobManager

AUTH = {"Authorization": "Bearer testtoken"}
ROOT = Path(__file__).resolve().parent.parent


def _app(tmp_path, **kw):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir(parents=True, exist_ok=True)
    kw.setdefault("auth_token", "testtoken")
    etc = {k: kw.pop(k) for k in ("settings_path",) if k in kw}
    return api.create_app(download_dir=d, db_path=tmp_path / "jobs.db",
                          **etc, **kw)


class _Throttled(http.server.SimpleHTTPRequestHandler):
    """Serves tiny.mp4 slowly so a job stays mid-download on purpose."""

    def do_GET(self):  # noqa: N802
        f = Path(self.directory) / self.path.lstrip("/").split("?")[0]
        if f.name == "tiny.mp4" and f.exists():
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "video/mp4")
            self.end_headers()
            for i in range(0, len(data), 4096):
                try:
                    self.wfile.write(data[i:i + 4096])
                    self.wfile.flush()
                except Exception:  # noqa: BLE001
                    return
                time.sleep(0.05)
            return
        super().do_GET()

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture()
def slow_fixture_server():
    handler = functools.partial(_Throttled, directory=str(ROOT / "tests" / "fixtures"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _wait(client, jid, statuses=("completed", "error", "cancelled"), tries=100):
    j = {}
    for _ in range(tries):
        j = client.get(f"/jobs/{jid}", headers=AUTH).json()
        if j["status"] in statuses:
            return j
        time.sleep(0.1)
    return j


# -- DEF-01: deleting a job must never remove the download folder -----------

def test_deleting_a_job_never_removes_the_download_folder(tmp_path, monkeypatch):
    """A relative download dir made the "clean up empty folders" comparison
    fail, so `rmdir()` ran on the download folder itself."""
    monkeypatch.chdir(tmp_path)
    mgr = JobManager(download_dir="my_dl", db_path=str(tmp_path / "jobs.db"))
    f = Path("my_dl") / "test.mp4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"video")
    job = mgr.create("http://example.com/test")
    with mgr._lock:
        j = mgr._jobs[job["id"]]
        j["status"] = "completed"
        j["filepath"] = str(f)
        j["files"] = [str(f)]
        mgr._save(j)
    mgr.delete_job(job["id"])
    assert Path("my_dl").is_dir(), "the download folder was removed"


# -- DEF-03: changing download_dir must not block deleting older jobs -------

def test_old_downloads_are_still_deletable_after_changing_the_folder(tmp_path):
    """`_require_inside` compared against the CURRENT download dir, so every
    earlier download became "outside the download folder" (409) forever."""
    app = _app(tmp_path)
    mgr = app.state.manager
    old_dir = Path(mgr.download_dir)
    f = old_dir / "old.mp4"
    f.write_bytes(b"video")
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x"},
                     headers=AUTH).json()["id"]
        with mgr._lock:
            j = mgr._jobs[jid]
            j["status"] = "completed"
            j["filepath"] = str(f)
            j["files"] = [str(f)]
            mgr._save(j)
        new_dir = tmp_path / "dl2"
        new_dir.mkdir()
        assert c.post("/settings", json={"download_dir": str(new_dir)},
                      headers=AUTH).status_code == 200
        r = c.post(f"/jobs/{jid}/delete", headers=AUTH)
        assert r.status_code == 200, r.text
        assert not f.exists()


# -- DEF-04: the bulk wipe must refuse while a download is running ----------

def test_files_clear_refuses_while_a_download_is_running(tmp_path, monkeypatch, slow_fixture_server):
    """The wipe unlinked a live `.part`; yt-dlp then died on the rename."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": f"{slow_fixture_server}/tiny.mp4"},
                     headers=AUTH).json()["id"]
        time.sleep(0.4)
        r = c.post("/files/clear", json={"confirm": "delete"}, headers=AUTH)
        assert r.status_code == 409, r.text
        assert "cancel" in r.json()["detail"].lower()
        c.post(f"/jobs/{jid}/cancel", headers=AUTH)
        _wait(c, jid)
        assert c.post("/files/clear", json={"confirm": "delete"},
                      headers=AUTH).status_code == 200


# -- DEF-05 / DEF-10: cancelled downloads keep what they left on disk -------

def test_a_cancelled_downloads_part_file_is_deleted_with_the_job(tmp_path, slow_fixture_server):
    """`filepath` stayed None, so the targets list was empty: the row was
    removed and the `.part` stayed on disk forever."""
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=str(tmp_path / "jobs.db"))
    job = mgr.create(f"{slow_fixture_server}/tiny.mp4")
    time.sleep(0.4)
    mgr.cancel(job["id"])
    for _ in range(50):
        if mgr.get(job["id"])["status"] not in ("queued", "downloading", "merging"):
            break
        time.sleep(0.1)
    dl = Path(mgr.download_dir)
    parts = [p for p in dl.iterdir() if p.name.endswith((".part", ".ytdl"))]
    assert parts, "the test needs a partial file to be meaningful"
    mgr.delete_job(job["id"])
    assert not [p for p in dl.iterdir() if p.name.endswith((".part", ".ytdl"))]


def test_a_finished_download_still_records_its_files(tmp_path):
    """The incremental recorder must not lose the normal path."""
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=str(tmp_path / "jobs.db"))
    f = tmp_path / "dl" / "ok.mp4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x")
    job = mgr.create("http://example.com/ok")
    with mgr._lock:
        j = mgr._jobs[job["id"]]
        j["status"] = "completed"
        j["filepath"] = str(f)
        j["files"] = [str(f)]
        mgr._save(j)
    mgr.delete_job(job["id"])
    assert not f.exists()


def test_a_cancelled_playlist_deletes_what_it_had_written(tmp_path, slow_fixture_server):
    """A playlist's `files` was only set on a clean finish, so a cancelled or
    errored playlist row deleted nothing and left every video behind."""
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=str(tmp_path / "jobs.db"))
    job = mgr.create(f"{slow_fixture_server}/playlist.html", playlist_items="")
    dl = Path(mgr.download_dir)
    for _ in range(80):
        time.sleep(0.1)
        if list(dl.glob("*.mp4")) or list(dl.glob("*.part")):
            break
    mgr.cancel(job["id"])
    for _ in range(50):
        if mgr.get(job["id"])["status"] not in ("queued", "downloading", "merging"):
            break
        time.sleep(0.1)
    made = [p.name for p in dl.iterdir()]
    assert made, "the test needs at least one file from the playlist"
    mgr.delete_job(job["id"])
    assert not [p for p in dl.iterdir() if p.is_file()], \
        f"playlist leftovers survived the delete: {made}"


# -- DEF-06 / DEF-12: the CORS policy must cover both extension families ----

def test_firefox_extension_preflight_is_allowed(tmp_path):
    """The regex only matched `chrome-extension://`, so every request from the
    Firefox build (origin `moz-extension://<uuid>`) got a 400 preflight."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        r = c.options("/jobs", headers={
            "Origin": "moz-extension://f1e3d4c5-b6a7-8901-cdef-1234567890ab",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"})
        assert r.status_code == 200, r.text
        assert r.headers["access-control-allow-origin"].startswith("moz-extension://")


def test_preset_delete_preflight_is_allowed(tmp_path):
    """`DELETE /presets/{name}` existed but DELETE was not an allowed CORS
    method, so a browser client could never call it."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        r = c.options("/presets/x", headers={
            "Origin": "chrome-extension://habomdhpjdcddccplapkncnfokpknfle",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization,content-type"})
        assert r.status_code == 200, r.text
        assert "DELETE" in r.headers["access-control-allow-methods"]


# -- DEF-07: a settings file must never brick the engine --------------------

def test_a_settings_file_pointing_into_nowhere_cannot_brick_startup(tmp_path):
    """settings.json was loaded without validation, and a later startup died
    on mkdir — every launch, forever."""
    import suravidl_engine.api as api

    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file")
    sp = tmp_path / "settings.json"
    sp.write_text(json.dumps({"download_dir": str(blocker / "sub")}))
    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db", settings_path=sp)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/settings", headers=AUTH).json()["download_dir"] != str(blocker / "sub")


def test_junk_in_a_saved_setting_falls_back_to_the_default(tmp_path):
    sp = tmp_path / "settings.json"
    sp.write_text(json.dumps({"max_concurrent": "nan", "retries": "ten"}))
    from suravidl_engine.settings import Settings

    s = Settings(path=sp)
    assert s.get()["max_concurrent"] == 2       # the default, not "nan"
    assert s.get()["retries"] == 10


def test_settings_refuse_a_download_dir_that_cannot_be_created(tmp_path):
    app = _app(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file")
    with TestClient(app) as c:
        r = c.post("/settings", json={"download_dir": str(blocker / "sub")},
                   headers=AUTH)
        assert r.status_code == 400, r.text
        assert c.get("/settings", headers=AUTH).json()["download_dir"] != str(blocker / "sub")


# -- DEF-08: a cancel at the finish line must not report success -----------

def test_cancelling_at_the_finish_line_does_not_report_completed(tmp_path, slow_fixture_server):
    """`_execute` wrote `completed` unconditionally, so a cancel during the
    last moments was lost — and the completion hook still fired."""
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=str(tmp_path / "jobs.db"))
    fired = []
    mgr.on_complete = lambda job: fired.append(job["id"])
    jid_holder = {}
    orig = yt_dlp.YoutubeDL.extract_info

    def cancel_after_extract(self, *a, **kw):
        res = orig(self, *a, **kw)
        mgr.cancel(jid_holder["id"])
        return res

    with patch.object(yt_dlp.YoutubeDL, "extract_info", cancel_after_extract):
        jid_holder["id"] = mgr.create(f"{slow_fixture_server}/tiny.mp4")["id"]
        for _ in range(60):
            time.sleep(0.1)
            if mgr.get(jid_holder["id"])["status"] in ("completed", "cancelled", "error"):
                break
    final = mgr.get(jid_holder["id"])
    assert final["status"] == "cancelled", final
    assert not fired, "a cancelled job fired the completion action"


# -- DEF-09: per-job overrides may not smuggle engine-owned options ----------

def test_a_job_override_cannot_enable_raw_args(tmp_path):
    """`raw_args`/`raw_args_enabled` were missing from the per-job deny list,
    so a client could turn raw arguments on for a job even with the switch
    off in Settings."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        r = c.post("/jobs", headers=AUTH, json={
            "url": "http://example.com/x",
            "overrides": {"raw_args_enabled": True, "raw_args": "--write-info-json"}})
        assert r.status_code == 400, r.text
        assert "cannot be set per download" in r.json()["detail"].lower()


def test_raw_args_cannot_redirect_the_output_path():
    """`denied_raw_flags` banned `--exec` but not `-o/-P`, so raw arguments
    could write anywhere on disk."""
    from suravidl_engine.download_opts import parse_raw_args

    for bad in ("-o /tmp/evil/%(title)s.%(ext)s", "--output /tmp/evil/x",
                "-P /tmp/evil", "--paths /tmp/evil"):
        with pytest.raises(ValueError):
            parse_raw_args(bad)


# -- DEF-13: the per-job block needs an explicit "off" ----------------------

def test_the_per_job_block_has_an_explicit_off_for_embeds():
    html = (ROOT / "src/suravidl_engine/web/index.html").read_text()
    js = (ROOT / "src/suravidl_engine/web/app.js").read_text()
    for ident in ("ovMeta", "ovThumb"):
        assert f'id="{ident}"' in html
    # a three-state control is the only way "leave as my settings" and "off"
    # can both be expressed
    assert html.count('<select id="ovMeta"') == 1
    assert html.count('<select id="ovThumb"') == 1
    assert '"off"' in js and "use my settings" in html


# -- DEF-11: Android playlist rows must clean up / open the real files ------

def test_playlist_rows_target_their_real_files_on_android():
    js = (ROOT / "src/suravidl_engine/web/app.js").read_text()
    assert "j.files" in js, "the row data has to use the recorded file list"
    # the gallery copy is per file, not the folder name
    assert "deleteMediaNamed" in js
    idx = js.index("deleteMediaNamed")
    window = js[max(0, idx - 600):idx + 200]
    assert "files" in window or "filepath.split" not in window


# -- DEF-14 / DEF-15 / DEF-16: small but real ------------------------------

def test_android_gallery_matching_only_accepts_numbers():
    """DEF-02: MediaStore appends " (N)" — a loose "stem (" match also caught
    the user's own files ("clip (Official Music Video).mp4"), so deleting one
    download took an unrelated video with it. Mirrors MediaLibrary.matchesName
    (Kotlin compiles only in CI, so the rule is pinned here)."""
    src = (ROOT / "android/app/src/main/java/com/suravidl/app/"
           "MediaLibrary.kt").read_text(encoding="utf-8")
    body = src.split("private fun matchesName")[1]
    assert r"\d+" in body, "matchesName must require MediaStore's numbering"
    assert 'startsWith("$stem ("' not in body, "the loose prefix match is back"


def test_a_rejected_settings_patch_applies_none_of_itself(tmp_path):
    """Same fix, second half: a patch with one good and one bad key used to
    leave the good half applied in memory while the file kept the old value."""
    from suravidl_engine.settings import Settings

    sp = tmp_path / "settings.json"
    s = Settings(path=sp)
    before = s.get()["retries"]
    blocker = tmp_path / "afile"
    blocker.write_text("x")
    with pytest.raises(ValueError):
        s.update({"retries": 7, "download_dir": str(blocker / "nope")})
    assert s.get()["retries"] == before
    assert Settings(path=sp).get()["retries"] == before


def test_smoke_uses_the_running_interpreter():
    src = (ROOT / "scripts/smoke.py").read_text()
    assert "sys.executable" in src, "smoke.py must not hardcode .venv/bin/python"


def test_the_desktop_entry_calls_freeze_support():
    src = (ROOT / "scripts/entry.py").read_text()
    assert "freeze_support()" in src, "PyInstaller on Windows re-executes main()"


def test_the_extension_only_keeps_media_request_headers():
    src = (ROOT / "extension/background.js").read_text()
    assert "resourceType" in src or "MEDIA_RE" in src, \
        "header capture must be limited to media requests"
