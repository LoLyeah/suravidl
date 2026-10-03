"""v0.40.0 — the workbench: the job engine runs on a bounded worker pool,
SQLite opens in WAL with a schema version, and no error text keeps URL
credentials.

RED first: every pin below must fail on 0.39.13 (thread-per-job, no WAL,
no version stamp, error text as-is).
"""
import sqlite3
import threading
import time
from pathlib import Path

from suravidl_engine import jobs as jobs_mod
from suravidl_engine.jobs import JobManager


def _wait(pred, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def _fake_manager(tmp_path, db_name="jobs.db", **kw):
    """A manager whose _execute never touches the network: it records the
    job and blocks on an event, so thread counts can be observed mid-flight."""
    mgr = JobManager(download_dir=tmp_path,
                     db_path=str(tmp_path / db_name), **kw)
    ran: list[str] = []
    release = threading.Event()

    def fake_execute(job, fmt, extra_headers):
        ran.append(job["id"])
        release.wait(timeout=10)
        with mgr._lock:
            job["status"] = "completed"
        mgr._save(job)

    mgr._execute = fake_execute
    return mgr, ran, release


# -- 1. the pool ------------------------------------------------------------

def test_a_batch_of_jobs_does_not_own_a_thread_each(tmp_path):
    mgr, ran, release = _fake_manager(tmp_path, max_concurrent=2)
    before = threading.active_count()
    ids = [mgr.create(f"https://example.tld/v/{i}")["id"] for i in range(8)]
    assert _wait(lambda: len(ran) >= 1), "the queue started working"
    grew = threading.active_count() - before
    release.set()
    assert _wait(lambda: all(mgr.get(i)["status"] == "completed"
                             for i in ids)), "every queued job still runs"
    assert grew <= jobs_mod.POOL_SIZE, \
        f"8 queued jobs grew the process by {grew} threads " \
        f"(the pool is {jobs_mod.POOL_SIZE})"


def test_the_pool_is_a_fixed_named_daemon_set(tmp_path):
    mgr, ran, release = _fake_manager(tmp_path)
    try:
        mgr.create("https://example.tld/v/one")
        workers = list(mgr._workers)
        assert len(workers) == jobs_mod.POOL_SIZE
        assert all(isinstance(t, threading.Thread) for t in workers)
        assert all(t.daemon for t in workers)
        assert all(t.name.startswith("suravidl-job-") for t in workers)
        # a second enqueue reuses the same pool instead of growing it
        mgr.create("https://example.tld/v/two")
        assert len(mgr._workers) == jobs_mod.POOL_SIZE
    finally:
        release.set()


def test_resume_interrupted_feeds_the_pool_too(tmp_path):
    seed = JobManager(download_dir=tmp_path, db_path=str(tmp_path / "jobs.db"))
    done: list[str] = []

    def quick(job, fmt, eh):
        with seed._lock:
            job["status"] = "completed"
        seed._save(job)
        done.append(job["id"])

    seed._execute = quick
    ids = [seed.create(f"https://example.tld/i/{i}")["id"] for i in range(6)]
    assert _wait(lambda: len(done) == 6), "seed jobs completed"

    # what a killed process leaves behind: rows stuck mid-flight
    with seed._db_lock, seed._con:
        seed._con.execute(
            f"UPDATE jobs SET status='interrupted' WHERE id IN "
            f"({','.join('?' * len(ids))})", ids)

    fresh = JobManager(download_dir=tmp_path, db_path=str(tmp_path / "jobs.db"))
    ran: list[str] = []
    release = threading.Event()

    def blocked(job, fmt, extra_headers):
        ran.append(job["id"])
        release.wait(timeout=10)

    fresh._execute = blocked
    with fresh._lock:
        for job in fresh._jobs.values():
            job["status"] = "interrupted"
    before = threading.active_count()
    resumed = fresh.resume_interrupted()
    assert sorted(resumed) == sorted(ids), "all six rows are re-queued"
    assert _wait(lambda: len(ran) >= 1), "the resumed jobs started"
    grew = threading.active_count() - before
    release.set()
    assert _wait(lambda: len(ran) == 6), "all six ran"
    assert grew <= jobs_mod.POOL_SIZE, \
        f"resuming six jobs grew the process by {grew} threads"


# -- 2. the database --------------------------------------------------------

def test_file_dbs_open_in_wal_and_carry_a_schema_version(tmp_path):
    db = tmp_path / "jobs.db"
    mgr = JobManager(download_dir=tmp_path, db_path=str(db))
    mode = mgr._con.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    version = mgr._con.execute("PRAGMA user_version").fetchone()[0]
    assert version == jobs_mod.SCHEMA_VERSION
    assert mgr._con.execute("PRAGMA secure_delete").fetchone()[0] == 1
    # the schema write in init already made the sidecars; they hold the same
    # private rows as the db, so they are private too
    assert (tmp_path / "jobs.db-wal").exists(), "WAL sidecar is missing"
    for suffix in ("", "-wal", "-shm"):
        side = Path(str(db) + suffix)
        if side.exists():
            assert (side.stat().st_mode & 0o777) == 0o600, \
                f"{side.name} is not owner-only"


def test_a_legacy_db_is_migrated_and_stamped(tmp_path):
    db = tmp_path / "legacy.db"
    # the pre-v0.21 shape: the columns the app has always had, before
    # headers/preset/playlist_items/raw_args/overrides/files/partials/
    # download_dir arrived one release at a time
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, url TEXT NOT NULL,"
        " fmt TEXT, status TEXT NOT NULL, title TEXT, filepath TEXT,"
        " error TEXT, downloaded_bytes INTEGER DEFAULT 0, total_bytes INTEGER,"
        " speed REAL, eta INTEGER, created_at TEXT, completed_at TEXT)")
    con.execute("INSERT INTO jobs (id, url, status) VALUES"
                " ('old1', 'https://example.tld/old', 'completed')")
    con.commit()
    con.close()

    mgr = JobManager(download_dir=tmp_path, db_path=str(db))
    assert mgr._con.execute("PRAGMA user_version").fetchone()[0] \
        == jobs_mod.SCHEMA_VERSION
    cols = {r[1] for r in mgr._con.execute("PRAGMA table_info(jobs)")}
    assert {"headers", "preset", "playlist_items", "raw_args", "overrides",
            "files", "partials", "download_dir"} <= cols
    assert mgr.get("old1")["url"] == "https://example.tld/old"


# -- 3. error text ----------------------------------------------------------

def test_error_text_loses_url_credentials_before_it_is_shown_or_stored():
    from suravidl_engine.auth import explain_download_error

    msg = explain_download_error(
        "HTTP Error 403: Forbidden for "
        "https://cdn.example.tld/hls/master.m3u8?token=SUPERSECRET123"
        "&sig=abc9def&user=me")
    assert "SUPERSECRET123" not in msg
    assert "abc9def" not in msg
    assert "token=[redacted]" in msg
    assert "user=me" in msg, "only credentials go, the rest of the URL stays"


def test_the_scrubber_keeps_ordinary_failures_untouched():
    from suravidl_engine.auth import explain_download_error

    assert explain_download_error("plain failure") == "plain failure"
    assert "video=42" in explain_download_error(
        "boom at https://example.tld/watch?video=42")
