"""v0.46.2 "the follower" — the watch list.

Follow a playlist or channel; new entries arrive on their own. The laws
(see follows.py): following starts from NOW (the backlog is seeded as
seen), nothing is grabbed twice (seen is marked at queue time; an entry
already downloaded any other way is skipped for good), and checks are
polite and bounded (jitter, per-host gap, caps).

The check is tested with injected fetch/queue — no network, no queue —
plus endpoint shape tests that need neither.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine.api import create_app
from suravidl_engine.follows import (FollowChecker, FollowStore, check_one,
                                     due)
from suravidl_engine.jobs import JobManager

ROOT = Path(__file__).resolve().parents[1]
APPJS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
INDEX = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")

AUTH = {"Authorization": "Bearer t"}


def _entry(i):
    return {"id": "vid%d" % i, "url": "https://site/watch?v=vid%d" % i,
            "title": "clip %d" % i}


def _store(tmp_path):
    return FollowStore(tmp_path / "follows.db")


class Queue:
    """The queue stand-in: records calls, answers with an id (or None)."""

    def __init__(self, already=None):
        self.calls = []
        self.already = already or set()

    def __call__(self, entry, follow):
        self.calls.append(entry["id"])
        if entry["id"] in self.already:
            return None
        return "job-" + entry["id"]


def test_following_starts_from_now(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist", label="Show", seed=["vid1", "vid2"])
    assert f["label"] == "Show" and f["cadence_hours"] == 6.0
    assert s.seen(f["id"], "vid1") and s.seen(f["id"], "vid2")
    # a re-add of the same ids is idempotent
    s.add("https://site/other", seed=["vid1"])
    assert len(s.list()) == 2


def test_a_new_entry_is_queued_exactly_once(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist", seed=["vid1"])
    q = Queue()
    fetch = lambda url: ([_entry(1), _entry(2), _entry(3)], "Show")  # noqa: E731

    r1 = check_one(f, s, fetch=fetch, queue=q)
    assert r1 == {"checked": True, "new": 2, "queued": 2, "error": None}, r1
    assert sorted(q.calls) == ["vid2", "vid3"]

    r2 = check_one(f, s, fetch=fetch, queue=q)
    assert r2["new"] == 0 and r2["queued"] == 0, "the same entries came again"

    # one genuinely new entry: exactly one
    fetch2 = lambda url: ([_entry(1), _entry(2), _entry(3), _entry(9)], "Show")  # noqa: E731
    r3 = check_one(f, s, fetch=fetch2, queue=q)
    assert r3["new"] == 1 and r3["queued"] == 1 and q.calls[-1] == "vid9"


def test_an_entry_already_had_is_never_grabbed(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist")
    q = Queue(already={"vid5"})          # the manager says: already completed
    r = check_one(f, s, fetch=lambda url: ([_entry(5)], "Show"), queue=q)
    assert r["new"] == 1 and r["queued"] == 0
    assert q.calls == ["vid5"]
    # and it is seen: never asked again
    assert s.seen(f["id"], "vid5")
    r2 = check_one(f, s, fetch=lambda url: ([_entry(5)], "Show"), queue=q)
    assert r2["new"] == 0 and len(q.calls) == 1


def test_the_caps_hold_and_leftovers_wait_their_turn(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist")
    q = Queue()
    many = [_entry(i) for i in range(30)]
    r1 = check_one(f, s, fetch=lambda url: (many, "Show"), queue=q, cap_new=25)
    assert r1["queued"] == 25 and len(q.calls) == 25
    r2 = check_one(f, s, fetch=lambda url: (many, "Show"), queue=q, cap_new=25)
    assert r2["queued"] == 5, "the rest must come on the next check"


def test_auto_queue_off_only_counts(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist", auto_queue=False)
    q = Queue()
    r = check_one(f, s, fetch=lambda url: ([_entry(1)], "Show"), queue=q)
    assert r["new"] == 1 and r["queued"] == 0 and q.calls == []
    # not consumed: reported again until switched on
    r2 = check_one(f, s, fetch=lambda url: ([_entry(1)], "Show"), queue=q)
    assert r2["new"] == 1


def test_a_failing_check_records_its_reason(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist")

    def broken(url):
        raise RuntimeError("HTTP Error 403: Forbidden")

    r = check_one(f, s, fetch=broken, queue=Queue())
    assert r["checked"] is False and "403" in r["error"]
    again = s.get(f["id"])
    assert "403" in (again["last_error"] or "")
    # a later good check clears the error
    r2 = check_one(f, s, fetch=lambda url: ([_entry(1)], "Show"), queue=Queue())
    assert r2["checked"] is True
    assert s.get(f["id"])["last_error"] is None


def test_due_respects_the_cadence(tmp_path):
    s = _store(tmp_path)
    f = s.add("https://site/playlist", cadence_hours=6.0)   # just checked
    assert due(f) is False
    stale = dict(f)
    stale["last_checked"] = "2020-01-01T00:00:00+00:00"
    assert due(stale) is True


def test_the_checker_runs_only_due_follows(tmp_path):
    s = _store(tmp_path)
    fresh = s.add("https://a-site/playlist")                       # just checked
    stale = s.add("https://b-site/playlist")
    s.record(stale["id"], error=None)
    with s._lock, s._con:
        s._con.execute("UPDATE follows SET last_checked = ? WHERE id = ?",
                       ("2020-01-01T00:00:00+00:00", stale["id"]))
    seen = []
    ch = FollowChecker(s, fetch=lambda url: (seen.append(url) or [], ""),
                       queue=Queue())
    ran = ch.run_due()
    assert ran == 1 and seen == ["https://b-site/playlist"]


def test_jobs_carry_the_watch_list_keys(tmp_path):
    out = tmp_path / "dl"
    out.mkdir()
    db = tmp_path / "j.db"
    mgr = JobManager(download_dir=out, db_path=db)
    j = mgr.create("https://example.invalid/v", video_id="vid42",
                   follow_id="f123")
    got = mgr.get(j["id"])
    assert got["video_id"] == "vid42" and got["follow_id"] == "f123"
    reopened = JobManager(download_dir=out, db_path=db, auto_resume=False)
    back = reopened.get(j["id"])
    assert back["video_id"] == "vid42" and back["follow_id"] == "f123"
    assert reopened.has_video("vid42") is False      # not completed


def test_lazy_entries_with_no_id_still_get_a_stable_key(monkeypatch):
    """The bug that proved the design (real yt-dlp, YouTube-embed fixture):
    list extractors hand back {"_type": "url", "url": …} with NO id and NO
    title. Requiring an id dropped every entry such a page offered."""
    import yt_dlp

    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"title": "Embeds", "entries": [
                {"_type": "url", "url": "https://www.youtube.com/embed/jNQXAC9IVRw"},
                {"_type": "url", "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw&t=9"},
                {"_type": "url", "url": "https://youtu.be/jNQXAC9IVRw?si=x"},
                {"_type": "url", "url": "https://site/pages/clip-1?utm_source=news&x=1"},
                {"_type": "url", "url": "https://site/pages/clip-1?x=1&utm_campaign=nl"},
            ]}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    from suravidl_engine.follows import flat_entries

    entries, _ = flat_entries("https://site/list", {})
    ids = [e["id"] for e in entries]
    # the same video folds to one key across watch/embed/shorts surfaces
    assert ids[0] == ids[1] == ids[2] == "yt:jNQXAC9IVRw"
    # non-YouTube: host+path, tracking junk stripped so keys do not wobble
    assert ids[3] == ids[4] == "site/pages/clip-1?x=1"


def test_flat_entries_maps_sets_the_opts_and_drops_junk(monkeypatch):
    import yt_dlp

    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            assert download is False
            return {"title": "Show", "entries": [
                {"id": "a", "url": "https://site/a", "title": "A"},
                {"id": "", "url": "https://site/b"},  # no id: URL-derived key
                {"id": "c"},                          # no url: skipped
                None,                                 # junk: skipped
            ]}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    from suravidl_engine.follows import flat_entries

    entries, title = flat_entries("https://site/playlist", {
        "proxy": "http://proxy:1", "cookies_file": "/tmp/c.txt",
        "ip_version": "ipv4",
    })
    assert title == "Show"
    assert entries == [{"id": "a", "url": "https://site/a", "title": "A"},
                       {"id": "site/b", "url": "https://site/b",
                        "title": ""}]
    # the auth and routing the settings carry ride along
    assert captured["proxy"] == "http://proxy:1"
    assert captured["cookiefile"] == "/tmp/c.txt"
    assert captured["source_address"] == "0.0.0.0"
    assert captured["extract_flat"] == "in_playlist"


def test_the_endpoints_speak_without_a_network(tmp_path):
    app = create_app(download_dir=tmp_path / "dl", auth_token="t",
                     db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        assert c.get("/follows").status_code == 401
        got = c.get("/follows", headers=AUTH)
        assert got.status_code == 200 and got.json()["follows"] == []
        bad = c.post("/follows", headers=AUTH, json={"url": "not-a-url"})
        assert bad.status_code == 400
        assert "page URL" in bad.json()["detail"]
        miss = c.post("/follows/nope/check", headers=AUTH)
        assert miss.status_code == 404
        dele = c.post("/follows/nope/delete", headers=AUTH)
        assert dele.status_code == 404


def test_the_ui_has_the_follow_door_and_the_panel():
    assert 'id="followBtn"' in INDEX and 'id="followsCard"' in INDEX
    assert 'id="followsList"' in INDEX
    assert "function initFollows()" in APPJS
    assert 'api("/follows", {' in APPJS
    assert "j.follow_id" in APPJS
    assert "Daftar pantau" in APPJS
