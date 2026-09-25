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

        r = c.post("/files/clear", headers=AUTH).json()
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

        r = c.post("/files/clear", headers=AUTH).json()
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
        r = c.post("/files/clear", headers=AUTH).json()
        assert r["deleted"] == 0
        assert r["freed_bytes"] == 0
