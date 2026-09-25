"""Clearing downloads: on Android the folder is app-private, so the app has
to offer the cleanup itself (Settings → Device → Delete downloaded files)."""
import time

from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer testtoken"}


def _client(tmp_path):
    import suravidl_engine.api as api

    return TestClient(api.create_app(download_dir=tmp_path / "dl",
                                     auth_token="testtoken"))


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


def test_clear_prunes_completed_jobs_only(tmp_path):
    """After a wipe, finished rows should be gone; retryable ones must stay."""
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
        with mgr._lock:                                     # noqa: SLF001
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


def test_delete_refuses_while_the_download_is_running(tmp_path):
    """No silent data loss: cancel first, then delete."""
    with _client(tmp_path) as c:
        job = c.post("/jobs", json={"url": "http://example.invalid/slow.mp4"},
                     headers=AUTH).json()
        c.post(f"/jobs/{job['id']}/cancel", headers=AUTH)
        for _ in range(200):                              # let the worker stop
            cur = next((j for j in c.get("/jobs", headers=AUTH).json()["jobs"]
                        if j["id"] == job["id"]), None)
            if cur and cur["status"] in ("cancelled", "error", "completed"):
                break
            time.sleep(0.05)
        mgr = c.app.state.manager
        with mgr._lock:                                   # noqa: SLF001
            mgr._jobs[job["id"]]["status"] = "downloading"  # noqa: SLF001
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
