"""v0.45.26 "the column" — a database that predates a column gets it.

Field report (2026-10-08, Android): "the downloader is broken... it can
be downloaded normally on v0.45.1 but now it's broken" — jobs refused
("the engine refused it"), stuck at QUEUED forever, and cancel/delete
answered 500s. The v0.45.25 error-naming net surfaced the truth in one
line: `OperationalError: table jobs has no column named replaced_by`.

The column arrived at v0.45.17 behind `if version < SCHEMA_VERSION`,
but SCHEMA_VERSION had been stamped 1 since v0.40.0 and never raised —
so EXISTING databases skipped the ALTER while fresh ones got the column
from the CREATE TABLE. Every job save on an upgraded install died from
then on. Column alignment now runs on every boot (one PRAGMA deep,
per-column guarded), and SCHEMA_VERSION is 2 so stuck stamps are
carried forward.
"""
import sqlite3
from pathlib import Path

from suravidl_engine import jobs as jobs_mod
from suravidl_engine.jobs import JobManager

# v0.45.1's table, verbatim: the shape of a database that has known the
# app since before the replaced_by column existed
OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    fmt TEXT,
    preset TEXT,
    playlist_items TEXT,
    raw_args TEXT,
    overrides TEXT,
    headers TEXT,
    status TEXT NOT NULL,
    title TEXT,
    filepath TEXT,
    error TEXT,
    downloaded_bytes INTEGER DEFAULT 0,
    total_bytes INTEGER,
    speed REAL,
    eta INTEGER,
    created_at TEXT,
    completed_at TEXT,
    files TEXT,
    partials TEXT,
    download_dir TEXT
)
"""


def test_an_old_database_heals_on_boot(tmp_path, monkeypatch):
    monkeypatch.setattr(JobManager, "_run",
                        lambda self, job, fmt, hdr: None)  # offline

    db = tmp_path / "jobs.db"
    con = sqlite3.connect(db)
    con.executescript(OLD_SCHEMA)
    con.execute("PRAGMA user_version = 1")
    con.execute(
        "INSERT INTO jobs (id, url, status, created_at) VALUES "
        "('old-1', 'https://example.invalid/old', 'completed', '2026-01-01')")
    con.commit()
    con.close()

    mgr = JobManager(download_dir=tmp_path / "dl", db_path=db, auto_resume=True)
    cols = {r[1] for r in mgr._con.execute("PRAGMA table_info(jobs)")}
    assert "replaced_by" in cols, "the ALTER must run on existing databases"
    assert mgr._con.execute("PRAGMA user_version").fetchone()[0] == 2

    # the operation that was dying on the phone: a job's save
    job = mgr.create("https://example.invalid/new")
    con = sqlite3.connect(db)
    row = con.execute("SELECT status FROM jobs WHERE id = ?",
                      (job["id"],)).fetchone()
    con.close()
    assert row and row[0] in ("queued", "downloading"), \
        "the save must persist to the old database"
    assert mgr.get("old-1")["url"].endswith("/old"), "old rows survive"


def test_the_alignment_can_never_be_gated_away_again():
    src = (Path(jobs_mod.__file__)).read_text(encoding="utf-8")
    assert "SCHEMA_VERSION = 2" in src
    # the replaced_by guard exists and sits OUTSIDE the version gate:
    # everything after the first `if version < SCHEMA_VERSION:` is only the
    # stamp, so the ALTERs must appear BEFORE it in the file
    assert 'if "replaced_by" not in cols:' in src
    assert src.index('if "replaced_by" not in cols:') < \
        src.index("if version < SCHEMA_VERSION:")
