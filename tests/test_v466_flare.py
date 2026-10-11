"""v0.46.6 "the flare" — failure speaks everywhere (queue critique round 1).

From the dual-agent critique of the Queue tab (2026-10-11), top 3:
P1 — a failed job is announced nowhere outside the Queue tab (completion
had a toast; failure settled in silence), and the badge counts only
in-flight work; P1 — on unclassified failures the raw yt-dlp line printed
twice in red (the fallback echoed into the "human" slot); P2 — settled
rows carried no record (no size, no finish time, no site; the collapsed
path showed only /home/...). This file pins all three.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(
    encoding="utf-8")
JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text(
    encoding="utf-8")
NLBRACE = "\n}"


def test_network_failures_get_their_own_sentence():
    seg = APP[APP.index("function humanErr("):]
    seg = seg[:seg.index(NLBRACE)]
    assert "failed to resolve|name or service not known" in seg, \
        "DNS failures need a named arm, not the raw-line fallback"
    assert "connection refused|errno 111" in seg, \
        "connection-refused is the most common local failure"
    assert "could not find that address" in seg
    assert "could not reach that address" in seg


def test_the_fallback_never_prints_twice():
    """When humanErr has no arm it returns the raw first line; the error
    branch used to print that in the .jerrsay slot AND again in .jerr —
    the same red sentence twice, the promise visibly failing."""
    seg = APP[APP.index('} else if (j.status === "error" || j.status === "interrupted") {'):]
    seg = seg[:seg.index("const errText")]
    assert "fallbackEcho" in seg
    assert "say === rawLine" in seg
    assert "if (!fallbackEcho) row.append(" in seg, \
        "the sentence is suppressed exactly when it would echo the raw line"


def test_failure_fires_one_toast_with_the_two_actions():
    assert "function onFailed(j)" in APP
    seg = APP[APP.index("function onFailed(j)"):]
    seg = seg[:seg.index("function renderBins") if "function renderBins" in seg else len(seg)]
    assert 'toast(' in seg and '"bad"' in seg
    assert 't("Retry")' in seg, "the toast's first action retries the job"
    assert 'showTab("queue")' in seg, "the second lands on the queue"
    assert "/retry" in seg


def test_the_transition_fires_once_and_never_refires():
    seg = APP[APP.index("const prev = JOB_STATE.get(j.id);"):]
    seg = seg[:seg.index("JOB_STATE.set")]
    assert "onFiled(j)" in seg and "onFailed(j)" in seg
    assert 'prev !== "error" && prev !== "interrupted"' in seg, \
        "error <-> interrupted must not re-toast; a fresh page load (prev null) must not either"


def test_the_badge_carries_failures_when_nothing_is_in_flight():
    seg = APP[APP.index("function renderQueueBadge("):]
    seg = seg[:seg.index(NLBRACE)]
    assert "const failed = active ? 0" in seg
    assert 'badge.classList.toggle("bad", !active && !!failed)' in seg
    assert '.badge.bad { background: var(--err)' in CSS, \
        "rose, per the critique's fix"


def test_settled_rows_carry_their_record():
    seg = APP[APP.index("if (j.status === \"completed\") {"):]
    seg = seg[:seg.index("let trashHost")]
    assert '"jmeta settled"' in seg
    assert "humanBytes(j.size_bytes)" in seg
    assert "j.completed_at || j.created_at" in seg, \
        "the real finish time (the DB has carried completed_at all along), \
created_at only as fallback"
    assert "row.dataset.livery" in APP, "the livery promise reaches the rows"
    assert '.job .jmeta.settled' in CSS


def test_the_path_shows_its_tail():
    seg = CSS[CSS.index(".job .path {"):]
    seg = seg[:seg.index("}")]
    assert "direction: rtl" in seg and "text-align: left" in seg, \
        "elide the start; the filename is the point"


def test_the_engine_stamps_a_finish_time():
    """completed_at has been written at completion all along — the UI just
    never showed it. No new column: use the one the ledger already keeps."""
    assert 'job["completed_at"] = datetime.now(timezone.utc).isoformat()' in JOBS
    assert "finished_at" not in JOBS, \
        "a second timestamp for one fact is how a schema rots"


def test_the_flare_speaks_indonesian_too():
    assert '"Show queue": "Lihat antrean"' in APP
    BS = chr(92)   # the app.js source keeps the escapes literal
    needle = ('"Couldn' + chr(39) + 't download ' + BS + 'u201c{name}' + BS +
              'u201d ' + BS + 'u2014 {why}": "Gagal mengunduh')
    assert needle in APP


def test_completed_at_round_trips(tmp_path):
    """The ledger's finish time survives a reopen — the settled meta strip
    reads it. (The WRITE happens at completion: pinned above. This proves
    the read path with no worker racing the row.)"""
    import sqlite3, sys
    sys.path.insert(0, str(ROOT / "src"))
    from suravidl_engine.jobs import JobManager
    out = tmp_path / "dl"; out.mkdir()
    db = tmp_path / "j.db"
    JobManager(download_dir=out, db_path=db)          # schema only
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO jobs (id, url, status, created_at, completed_at)"
                " VALUES (?,?,?,?,?)",
                ("t1", "https://example.invalid/v", "completed",
                 "2026-10-11T00:00:00+00:00", "2026-10-11T00:05:00+00:00"))
    con.commit(); con.close()
    reopened = JobManager(download_dir=out, db_path=db, auto_resume=False)
    assert reopened.get("t1").get("completed_at") == "2026-10-11T00:05:00+00:00"


