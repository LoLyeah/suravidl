"""Clearing downloads: on Android the folder is app-private, so the app has
to offer the cleanup itself (Settings → Device → Delete downloaded files)."""
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer testtoken"}


def _client(tmp_path, cache_dir=None):
    """A client whose cache dir lives inside tmp_path.

    The engine's cache defaults to a real user directory (~/.cache/suravidl);
    a test must never clear that one just by exercising /files/clear.
    """
    import suravidl_engine.api as api

    return TestClient(api.create_app(download_dir=tmp_path / "dl",
                                     auth_token="testtoken",
                                     cache_dir=cache_dir or tmp_path / "cache"))


def test_summary_counts_files_and_bytes(tmp_path):
    with _client(tmp_path) as c:
        dl = tmp_path / "dl"
        dl.mkdir(parents=True, exist_ok=True)
        (dl / "one.mp4").write_bytes(b"x" * 100)
        (dl / "two.mp4").write_bytes(b"y" * 50)
        (dl / "one.info.json").write_bytes(b"{}")

        s = c.get("/files/summary", headers=AUTH).json()
        assert s["files"] == 3
        assert s["bytes"] == 152
        assert s["dir"].endswith("dl")


def test_clear_deletes_files_sidecars_and_nested_dirs(tmp_path):
    with _client(tmp_path) as c:
        dl = tmp_path / "dl"
        dl.mkdir(parents=True, exist_ok=True)
        (dl / "one.mp4").write_bytes(b"x" * 100)
        (dl / "sub").mkdir(exist_ok=True)
        (dl / "sub" / "side.srt").write_bytes(b"y" * 20)

        r = c.post("/files/clear", json={"confirm": "delete"}, headers=AUTH).json()
        assert r["deleted"] == 2
        assert r["freed_bytes"] == 120
        assert not any(p.is_file() for p in dl.rglob("*"))
        assert c.get("/files/summary", headers=AUTH).json()["files"] == 0


def test_clear_prunes_completed_jobs_only(tmp_path, monkeypatch):
    """After a wipe, finished rows should be gone; retryable ones must stay."""
    # Stub the worker: this test decides the rows' fate, and a real worker
    # racing its DNS failure past the hand-set status flipped "completed"
    # back to "error" on a slower interpreter (CI: Python 3.12) — the test
    # was racing the network for its own fixture (v0.21.2 audit).
    from suravidl_engine.jobs import JobManager

    monkeypatch.setattr(JobManager, "_run", lambda self, *a, **k: None)
    with _client(tmp_path) as c:
        done = c.post("/jobs", json={"url": "http://example.invalid/ok.mp4"},
                      headers=AUTH).json()
        bad = c.post("/jobs", json={"url": "http://example.invalid/bad.mp4"},
                     headers=AUTH).json()
        # stop the workers first: their rows' fate must be the test's to decide,
        # not the network's (a racing error write used to flip these statuses)
        for j in (done, bad):
            c.post(f"/jobs/{j['id']}/cancel", headers=AUTH)
        for _ in range(200):
            states = {j["id"]: j["status"]
                      for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
            if all(states.get(j["id"]) in ("cancelled", "error")
                   for j in (done, bad)):
                break
            time.sleep(0.05)

        mgr = c.app.state.manager
        # take the manager's DB lock too: `_save` serializes on it, and two
        # threads nesting transactions on one connection is the "cannot
        # commit - no transaction is active" traceback (v0.21.2 audit)
        with mgr._db_lock, mgr._lock:                       # noqa: SLF001
            with mgr._con:                                  # noqa: SLF001
                for jid, status in ((done["id"], "completed"),
                                    (bad["id"], "error")):
                    mgr._jobs[jid]["status"] = status       # noqa: SLF001
                    mgr._con.execute(                       # noqa: SLF001
                        "UPDATE jobs SET status=? WHERE id=?", (status, jid))

        r = c.post("/files/clear", json={"confirm": "delete"}, headers=AUTH).json()
        assert r["cleared_jobs"] == 1
        ids = {j["id"] for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
        assert done["id"] not in ids
        assert bad["id"] in ids

        # the prune is durable, not just in memory
        assert mgr._con.execute(                            # noqa: SLF001
            "SELECT COUNT(*) FROM jobs WHERE status = 'completed'"
        ).fetchone()[0] == 0


def test_clear_on_empty_dir_is_harmless(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/files/clear", json={"confirm": "delete"}, headers=AUTH).json()
        assert r["deleted"] == 0
        assert r["freed_bytes"] == 0


# --------------------------------------------------------------------------
# per-download delete: the trash button on a finished row
# --------------------------------------------------------------------------

def _settled_job(c, url, status="completed", name="one.mp4", sidecars=()):
    """A job whose worker has stopped, with a real file on disk."""
    job = c.post("/jobs", json={"url": url}, headers=AUTH).json()
    c.post(f"/jobs/{job['id']}/cancel", headers=AUTH)
    for _ in range(200):
        cur = next((j for j in c.get("/jobs", headers=AUTH).json()["jobs"]
                    if j["id"] == job["id"]), None)
        if cur and cur["status"] in ("cancelled", "error", "completed"):
            break
        time.sleep(0.05)
    dl = c.app.state.download_dir
    path = dl / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"v" * 2048)
    for extra in sidecars:
        (dl / f"{path.stem}{extra}").write_bytes(b"s" * 10)
    mgr = c.app.state.manager
    with mgr._lock:                                     # noqa: SLF001
        with mgr._con:                                  # noqa: SLF001
            mgr._jobs[job["id"]]["status"] = status     # noqa: SLF001
            mgr._jobs[job["id"]]["filepath"] = str(path)  # noqa: SLF001
            mgr._con.execute(                           # noqa: SLF001
                "UPDATE jobs SET status=?, filepath=? WHERE id=?",
                (status, str(path), job["id"]))
    return job, path


def test_delete_one_download_takes_its_file_and_sidecars(tmp_path):
    with _client(tmp_path) as c:
        job, path = _settled_job(c, "http://example.invalid/one.mp4",
                                 sidecars=(".info.json", ".jpg", ".vtt"))
        other = c.app.state.download_dir / "keep-me.mp4"
        other.write_bytes(b"k" * 10)

        r = c.post(f"/jobs/{job['id']}/delete", headers=AUTH).json()
        assert r["deleted"] == 4 and r["freed_bytes"] == 2048 + 30, r
        assert not path.exists() and not (tmp_path / "dl" / "one.info.json").exists()
        assert other.exists(), "an unrelated file must survive"

        ids = {j["id"] for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
        assert job["id"] not in ids
        mgr = c.app.state.manager
        assert mgr._con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_delete_refuses_while_the_download_is_running(tmp_path, monkeypatch):
    """No silent data loss: cancel first, then delete.

    The worker is stubbed to hold the job in `downloading` for good: a real
    failing URL finishes (and writes its final row) somewhere inside this
    test, which raced the hand-set status and made the test flaky.
    """
    from suravidl_engine.jobs import JobManager

    def stuck_run(self, job, fmt, extra_headers):
        job["status"] = "downloading"      # and it stays there

    monkeypatch.setattr(JobManager, "_run", stuck_run)
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": "http://example.invalid/slow.mp4"},
                     headers=AUTH).json()
        for _ in range(200):                              # let the worker start
            cur = next((j for j in c.get("/jobs", headers=AUTH).json()["jobs"]
                        if j["id"] == job["id"]), None)
            if cur and cur["status"] == "downloading":
                break
            time.sleep(0.05)
        r = c.post(f"/jobs/{job['id']}/delete", headers=AUTH)
        assert r.status_code == 409, r.text
        assert "cancel" in r.json()["detail"].lower()
        ids = {j["id"] for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
        assert job["id"] in ids


def test_delete_never_touches_files_outside_the_download_dir(tmp_path):
    outside = tmp_path / "precious.mp4"
    outside.write_bytes(b"p" * 32)
    with _client(tmp_path) as c:
        job, _ = _settled_job(c, "http://example.invalid/one.mp4")
        mgr = c.app.state.manager
        with mgr._lock:                                     # noqa: SLF001
            with mgr._con:                                  # noqa: SLF001
                mgr._jobs[job["id"]]["filepath"] = str(outside)  # noqa: SLF001
                mgr._con.execute(                           # noqa: SLF001
                    "UPDATE jobs SET filepath=? WHERE id=?",
                    (str(outside), job["id"]))
        r = c.post(f"/jobs/{job['id']}/delete", headers=AUTH)
        assert r.status_code == 409, r.text
        assert outside.exists(), "a path outside the download dir is not ours"
        # the row stays too: nothing was deleted, so there is nothing to forget
        ids = {j["id"] for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
        assert job["id"] in ids


def test_delete_unknown_job_is_404(tmp_path):
    with _client(tmp_path) as c:
        assert c.post("/jobs/nope/delete", headers=AUTH).status_code == 404


def test_delete_of_a_job_without_a_file_still_forgets_the_row(tmp_path):
    """An errored job has no file — the trash button should still clear it."""
    with _client(tmp_path) as c:
        job, _ = _settled_job(c, "http://example.invalid/one.mp4", status="error")
        mgr = c.app.state.manager
        with mgr._lock:                                     # noqa: SLF001
            with mgr._con:                                  # noqa: SLF001
                mgr._jobs[job["id"]]["filepath"] = None     # noqa: SLF001
                mgr._con.execute(                           # noqa: SLF001
                    "UPDATE jobs SET filepath=NULL WHERE id=?", (job["id"],))
        r = c.post(f"/jobs/{job['id']}/delete", headers=AUTH).json()
        assert r["deleted"] == 0
        ids = {j["id"] for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
        assert job["id"] not in ids


def test_a_late_worker_write_cannot_resurrect_a_deleted_download(tmp_path):
    """Deleting is final. A worker thread writing one last time (progress, or
    the completion it was racing) must not bring the row back to the queue."""
    with _client(tmp_path) as c:
        job, path = _settled_job(c, "http://example.invalid/one.mp4")
        mgr = c.app.state.manager
        c.post(f"/jobs/{job['id']}/delete", headers=AUTH)

        late = dict(job)                     # what a worker still holds
        late["status"] = "completed"
        late["progress"] = dict(job.get("progress") or {}, downloaded_bytes=1)
        mgr._save(late)                      # noqa: SLF001

        assert mgr._con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        ids = {j["id"] for j in c.get("/jobs", headers=AUTH).json()["jobs"]}
        assert job["id"] not in ids
        assert not path.exists()


# --------------------------------------------------------------------------
# the app cache: yt-dlp's player/signature data, which it can always re-fetch
# --------------------------------------------------------------------------

def test_summary_reports_the_app_cache(tmp_path):
    """The cache had no owner: nothing counted it and nothing cleared it, and
    on Android it lived in app *data*, out of reach of the system's own
    Clear-cache. It is counted apart from the downloads."""
    with _client(tmp_path, cache_dir=tmp_path / "cache") as c:
        cache = tmp_path / "cache"
        (cache / "youtube").mkdir(parents=True, exist_ok=True)
        (cache / "youtube" / "player.js").write_bytes(b"p" * 300)
        (cache / "sig.bin").write_bytes(b"s" * 40)

        s = c.get("/files/summary", headers=AUTH).json()
        assert s["files"] == 0, "cache is not a downloaded file"
        assert s["cache_bytes"] == 340
        assert s["cache_files"] == 2
        assert s["cache_dir"].endswith("cache")


# v0.24.9 folded the cache sweep into /files/clear; the 2026-09-28 ask
# ("why not make 'delete cache' as a different button?") split it again:
# /files/clear speaks files only, and /cache/clear is the endpoint with its
# own confirm, its own button, and the stand-down guard.

def test_the_cache_endpoint_frees_the_cache_and_nothing_else(tmp_path):
    with _client(tmp_path, cache_dir=tmp_path / "cache") as c:
        dl = tmp_path / "dl"
        dl.mkdir(parents=True, exist_ok=True)
        (dl / "one.mp4").write_bytes(b"x" * 100)
        cache = tmp_path / "cache"
        (cache / "youtube").mkdir(parents=True, exist_ok=True)
        (cache / "youtube" / "player.js").write_bytes(b"p" * 300)
        keep = tmp_path / "keep.txt"
        keep.write_bytes(b"k" * 5)          # outside every root

        r = c.post("/cache/clear", json={"confirm": "delete"},
                   headers=AUTH).json()
        assert r["deleted"] == 1 and r["freed_bytes"] == 300
        assert cache.exists(), "the cache root itself stays"
        assert not any(p.is_file() for p in cache.rglob("*"))
        assert (dl / "one.mp4").exists(), "a download is not cache"
        assert keep.exists(), "files outside both roots must survive"
        assert c.get("/files/summary", headers=AUTH).json()["cache_bytes"] == 0

        # …and the file delete leaves the cache alone (the reversal)
        (cache / "back").write_bytes(b"b" * 10)
        f = c.post("/files/clear", json={"confirm": "delete"},
                   headers=AUTH).json()
        assert f["deleted"] == 1
        assert "cache_freed_bytes" not in f, "the file delete no longer speaks cache"
        assert (cache / "back").exists()


def test_the_cache_endpoint_needs_the_word(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/cache/clear", json={}, headers=AUTH)
        assert r.status_code == 400
        assert "confirm" in r.json()["detail"]


def test_the_cache_endpoint_stands_down_when_it_owns_the_downloads(tmp_path):
    """A cache dir that contains the download folder is a config mistake and
    the dangerous direction of overlap: wiping it would treat the user's
    downloads as cache. The endpoint stands down — the folder sweep owns
    those files."""
    with _client(tmp_path, cache_dir=tmp_path) as c:
        dl = tmp_path / "dl"
        dl.mkdir(parents=True, exist_ok=True)
        (dl / "one.mp4").write_bytes(b"x" * 100)
        keep = tmp_path / "keep.txt"
        keep.write_bytes(b"k" * 5)

        r = c.post("/cache/clear", json={"confirm": "delete"},
                   headers=AUTH).json()
        assert r["freed_bytes"] == 0 and r["stood_down"] is True
        assert keep.exists(), "the cache sweep must not walk a dir that owns the downloads"
        assert (dl / "one.mp4").exists()


def test_jobs_point_yt_dlp_at_the_engine_cache(tmp_path):
    from suravidl_engine.download_opts import build_download_opts

    opts = build_download_opts({}, tmp_path / "dl", cache_dir=tmp_path / "cache")
    assert opts["cachedir"] == str(tmp_path / "cache")
    plain = build_download_opts({}, tmp_path / "dl")
    assert "cachedir" not in plain, "unset must leave yt-dlp's own default alone"


def test_default_cache_dir_follows_env_then_xdg(monkeypatch, tmp_path):
    from suravidl_engine.api import default_cache_dir

    monkeypatch.delenv("SURAVIDL_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    assert default_cache_dir() == Path.home() / ".cache" / "suravidl"

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert default_cache_dir() == tmp_path / "xdg" / "suravidl"

    monkeypatch.setenv("SURAVIDL_CACHE_DIR", str(tmp_path / "explicit"))
    assert default_cache_dir() == tmp_path / "explicit", \
        "the shell's explicit choice wins (Android points it at the cache bucket)"


# --------------------------------------------------------------------------
# the folder sheet: "open folder" has to show the folder's files (2026-09-27)
# --------------------------------------------------------------------------

def test_list_shows_downloads_newest_first_and_hides_work_files(tmp_path):
    """Android/data is closed to every file manager on Android 11+, so the
    app lists the folder itself. Work files, sidecars and thumbnails are not
    downloads and must not clutter it."""
    with _client(tmp_path) as c:
        dl = c.app.state.download_dir
        dl.mkdir(parents=True, exist_ok=True)
        (dl / "old.mp4").write_bytes(b"x" * 10)
        (dl / "new.srt").write_bytes(b"y" * 5)
        os.utime(dl / "old.mp4", (1000, 1000))
        os.utime(dl / "new.srt", (2000, 2000))
        (dl / "clip.info.json").write_bytes(b"{}")
        (dl / "clip.mp4.part").write_bytes(b"z")
        (dl / "frag.mp4.part-Frag1").write_bytes(b"z")
        (dl / "thumb.jpg").write_bytes(b"t")
        (dl / ".hidden.mp4").write_bytes(b"h")
        sub = dl / "sub"
        sub.mkdir()
        (sub / "e1.mp4").write_bytes(b"w" * 3)
        os.utime(sub / "e1.mp4", (1500, 1500))

        r = c.get("/files/list", headers=AUTH).json()
        assert [f["name"] for f in r["files"]] == \
            ["new.srt", "sub/e1.mp4", "old.mp4"]
        kinds = {f["name"]: f["kind"] for f in r["files"]}
        assert kinds["old.mp4"] == "video"
        assert kinds["new.srt"] == "subtitle"
        assert all(f["path"].startswith(str(dl)) for f in r["files"])
        assert r["dir"] == str(dl)


def test_files_stream_serves_ranges_and_refuses_escapes(tmp_path):
    with _client(tmp_path) as c:
        dl = c.app.state.download_dir
        dl.mkdir(parents=True, exist_ok=True)
        (dl / "clip.mp4").write_bytes(b"0123456789")
        (dl / "sub").mkdir()
        (dl / "sub" / "e1.mp4").write_bytes(b"sub")

        r = c.get("/files/stream", params={"path": "clip.mp4"}, headers=AUTH)
        assert r.status_code == 200 and r.content == b"0123456789"
        r = c.get("/files/stream", params={"path": "clip.mp4"},
                  headers={**AUTH, "Range": "bytes=2-4"})
        assert r.status_code == 206 and r.content == b"234"
        assert r.headers["content-range"] == "bytes 2-4/10"
        r = c.get("/files/stream", params={"path": "sub/e1.mp4"}, headers=AUTH)
        assert r.status_code == 200 and r.content == b"sub"

        outside = tmp_path / "secret.txt"
        outside.write_bytes(b"no")
        for bad in ("../secret.txt", "sub/../../secret.txt", "/etc/hostname", ""):
            rr = c.get("/files/stream", params={"path": bad}, headers=AUTH)
            assert rr.status_code in (403, 404), bad
        rr = c.get("/files/stream", params={"path": "missing.mp4"}, headers=AUTH)
        assert rr.status_code == 404
