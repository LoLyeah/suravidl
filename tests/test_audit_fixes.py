"""Regressions from the v0.21.1 audit.

Every test here failed against the running engine before its fix — they were
found by probing the live API with hostile input, not by reading code.
"""

import threading
from pathlib import Path

import pytest
from suravidl_engine.jobs import JobManager
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


# -- 7. a playlist row must not take the whole folder with it ---------------
# Found by the UI auditor: a playlist job's filepath is the download *folder*,
# so the trash button on that one row deleted every other job's files too.

def _playlist_job(mgr, names=("a.mp4", "b.mp4"), files_field=True):
    job = mgr.create("http://example.invalid/playlist")
    d = Path(mgr.download_dir)
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for n in names:
        p = d / n
        p.write_bytes(b"x" * 10)
        made.append(str(p))
    with mgr._lock:
        j = mgr._jobs[job["id"]]
        j.update(status="completed", filepath=str(d), title="Fixture playlist",
                 playlist_count=len(names))
        if files_field:
            j["files"] = made
        mgr._save(j)
    return job["id"], made


def _other_job(mgr):
    job = mgr.create("http://example.invalid/other")
    p = Path(mgr.download_dir) / "other.mp4"
    p.write_bytes(b"y" * 5)
    with mgr._lock:
        j = mgr._jobs[job["id"]]
        j.update(status="completed", filepath=str(p))
        mgr._save(j)
    return job["id"], p


def test_a_playlist_delete_takes_only_its_own_files(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        pid, made = _playlist_job(mgr)
        oid, other = _other_job(mgr)
        r = c.post(f"/jobs/{pid}/delete", headers=AUTH)
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] == 2
        assert not Path(made[0]).exists() and not Path(made[1]).exists()
        assert Path(mgr.download_dir).is_dir(), "the folder itself must survive"
        assert other.exists(), "an unrelated download was deleted with the playlist"
        assert c.get(f"/jobs/{oid}", headers=AUTH).status_code == 200


def test_an_old_playlist_row_keeps_files_it_cannot_name(tmp_path):
    """Rows from before per-file tracking delete the row, not the folder."""
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        pid, made = _playlist_job(mgr, files_field=False)
        oid, other = _other_job(mgr)
        r = c.post(f"/jobs/{pid}/delete", headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["deleted"] == 0
        assert "note" in body and "folder" in body["note"]
        assert Path(made[0]).exists() and other.exists()
        assert c.get(f"/jobs/{pid}", headers=AUTH).status_code == 404


# -- 7b. two locks, and the write paths that only took one ------------------
# CI found this on Python 3.10: a playlist delete raised
# `sqlite3.OperationalError: cannot commit - no transaction is active`.
# `_lock` guards the in-memory maps, `_db_lock` guards the shared connection,
# and `_save` — which the worker thread calls for every progress tick — uses
# the second. The delete path used only the first, so its DELETE could land in
# the middle of another thread's transaction, and a late write could also slip
# past the `_deleted` check and commit a removed row straight back.

def _hold_db_lock(mgr):
    """Take the database lock in another thread and hand back the release."""
    held, release = threading.Event(), threading.Event()

    def holder():
        with mgr._db_lock:
            held.set()
            release.wait(5)

    threading.Thread(target=holder, daemon=True).start()
    assert held.wait(2), "the helper thread never took the database lock"
    return release


def _runs_while(release, fn, why):
    """"fn must wait for the lock" — proved by watching it not finish."""
    done = threading.Event()

    def run():
        fn()
        done.set()

    threading.Thread(target=run, daemon=True).start()
    assert not done.wait(0.3), why
    release.set()
    assert done.wait(5), "it never finished once the lock was free"


def test_the_delete_path_waits_for_the_database_lock(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        pid, _ = _playlist_job(mgr)
        release = _hold_db_lock(mgr)
        _runs_while(release, lambda: mgr.delete_job(pid),
                    "the delete ran without the database lock")


def test_clearing_completed_waits_for_the_database_lock(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        _playlist_job(mgr)
        release = _hold_db_lock(mgr)
        _runs_while(release, mgr.clear_completed,
                    "the clear ran without the database lock")


def test_a_late_save_cannot_resurrect_a_cleared_row(tmp_path):
    """`clear_completed` removed the row but not the id from `_deleted`, so a
    worker write that was already in flight committed the row back."""
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        pid, _ = _playlist_job(mgr)
        stale = dict(mgr._jobs[pid])
        mgr.clear_completed()
        mgr._save(stale)
        assert mgr._con.execute("SELECT COUNT(*) FROM jobs WHERE id = ?",
                                (pid,)).fetchone()[0] == 0


def test_deleting_while_a_save_is_in_flight_stays_consistent(tmp_path):
    """The hammer: the row ends up gone and nothing raises on the way."""
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        pid, _ = _playlist_job(mgr)
        stale = dict(mgr._jobs[pid])
        errors, stop = [], threading.Event()

        def saver():
            while not stop.is_set():
                try:
                    mgr._save(stale)
                except Exception as e:      # this is the assertion, recorded
                    errors.append(repr(e))
                    return

        t = threading.Thread(target=saver, daemon=True)
        t.start()
        try:
            mgr.delete_job(pid)
        finally:
            stop.set()
            t.join(10)
        assert not errors, errors
        assert mgr._con.execute("SELECT COUNT(*) FROM jobs WHERE id = ?",
                                (pid,)).fetchone()[0] == 0


def test_playlist_files_survive_a_restart(tmp_path):
    """The file list is persisted, not just held in memory."""
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app):
        pid, made = _playlist_job(mgr)
    fresh = JobManager(Path(mgr.download_dir), tmp_path / "jobs.db")
    job = fresh.get(pid)
    assert job["files"] == made
    fresh.delete_job(pid)
    assert not Path(made[0]).exists()
    assert Path(mgr.download_dir).is_dir()


# -- 8. the UI config blob cannot close its own script tag ------------------

def test_a_download_folder_cannot_break_out_of_the_config_script(tmp_path):
    """json.dumps escapes quotes, not '<': a folder named '</script><script>'
    ended the element early and executed (the UI config was never parsed)."""
    app = _app(tmp_path)
    with TestClient(app) as c:
        nasty = str(tmp_path / "dl</script><script>window.__CFGXSS=1</script>")
        assert c.post("/settings", json={"download_dir": nasty},
                      headers=AUTH).status_code == 200
        page = c.get("/").text
        assert "</script><script>window.__CFGXSS" not in page
        assert "\\u003c/script" in page


# -- 9. the page that carries the token needs the shell's key ---------------

def test_the_api_token_page_is_gated_by_the_shells_key(tmp_path):
    """Loopback is shared: on Android every other installed app can open a
    socket to 127.0.0.1:8787. With a page key set, the token page is only
    served to a request carrying it — otherwise any app (or any page in a
    WebView) could read the token and drive the engine."""
    app = _app(tmp_path, page_key="s3cret-key")
    with TestClient(app) as c:
        assert c.get("/").status_code == 401
        assert c.get("/?k=wrong").status_code == 401
        ok = c.get("/?k=s3cret-key")
        assert ok.status_code == 200
        assert "testtoken" in ok.text          # it is the real page


def test_without_a_page_key_the_shell_behaves_as_before(tmp_path):
    """The desktop shells and the browser flow set no key: they must keep
    getting the page, or every existing entry point breaks."""
    with TestClient(_app(tmp_path)) as c:
        assert c.get("/").status_code == 200


def test_the_launcher_passes_the_page_key_through(tmp_path):
    """`python -m suravidl_engine` and the Android shell share start_server:
    a key the launcher dropped would be a silent 401 for the app."""
    import inspect

    from suravidl_engine import __main__ as launcher

    sig = inspect.signature(launcher.start_server)
    assert "page_key" in sig.parameters
    src = inspect.getsource(launcher.start_server)
    assert "page_key=page_key" in src
