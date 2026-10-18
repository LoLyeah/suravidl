"""v0.47.7 "the drawer" — rename a finished file and clear the history.

Two owner asks (2026-10-18): a pencil on a finished card that renames the
file AND its sidecars together (a renamed video must not orphan its
subtitles), and a "Clear history" button that forgets the rows while the
files stay where they are — desktop only, because on the phone the files
live in app storage and a cleared row would leave something unreachable.
"""
import pathlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine import api
from suravidl_engine.jobs import JobManager

AUTH = {"Authorization": "Bearer testtoken"}


def _mgr(tmp_path) -> JobManager:
    def dopts(dir_, raw_args=None, overrides=None):
        return {}
    return JobManager(download_dir=tmp_path, db_path=tmp_path / "jobs.db",
                      max_concurrent=1, download_opts=dopts)


def _completed(mgr, files, filepath=None, status="completed"):
    job = {
        "id": "j1", "url": "http://example.test/v", "status": status,
        "title": "master", "filepath": str(filepath or files[0]),
        "files": [str(p) for p in files], "download_dir": str(mgr.download_dir),
        "created_at": "2026-10-18T00:00:00+00:00",
        "progress": {"downloaded_bytes": 16, "total_bytes": 16,
                     "speed": None, "eta": None},
        "partials": [], "overrides": None, "headers": None,
    }
    with mgr._lock:
        mgr._jobs["j1"] = job
    mgr._save(job)
    return job


def _touch(tmp_path, *names):
    made = []
    for n in names:
        p = tmp_path / n
        p.write_bytes(b"x" * 16)
        made.append(p)
    return made


def test_rename_moves_the_file_and_every_sidecar(tmp_path):
    mgr = _mgr(tmp_path)
    files = _touch(tmp_path, "master.mp4", "master.en.srt", "master.jpg",
                   "other.mp4")
    _completed(mgr, files[:3])
    job = mgr.rename_job("j1", "Episode 1")
    assert (tmp_path / "Episode 1.mp4").exists()
    assert (tmp_path / "Episode 1.en.srt").exists(), "the language tag survives"
    assert (tmp_path / "Episode 1.jpg").exists(), "the thumbnail follows"
    assert (tmp_path / "other.mp4").exists(), "an unrelated file is untouched"
    assert not (tmp_path / "master.mp4").exists()
    assert job["filepath"].endswith("Episode 1.mp4")
    assert job["title"] == "Episode 1"
    assert all("Episode 1" in p for p in job["files"])


def test_a_collision_is_a_refusal_never_an_overwrite(tmp_path):
    mgr = _mgr(tmp_path)
    files = _touch(tmp_path, "master.mp4", "Taken.mp4")
    _completed(mgr, files)
    with pytest.raises(ValueError, match="already there"):
        mgr.rename_job("j1", "Taken")
    assert (tmp_path / "master.mp4").exists(), "nothing moved"


def test_names_windows_would_refuse_are_refused_here(tmp_path):
    mgr = _mgr(tmp_path)
    _completed(mgr, _touch(tmp_path, "master.mp4"))
    for bad in ("a/b", "a\\b", "a:b", "a?b", "a*b", 'a"b', "a<b", "a>b", "a|b",
                "trailing.", "  ", "x" * 151, "CON", "nul.mp4"):
        with pytest.raises(ValueError):
            mgr.rename_job("j1", bad)
    assert mgr.check_name("  spaced  ") == "spaced", "outer air is trimmed, not refused"
    assert (tmp_path / "master.mp4").exists()


def test_only_a_finished_download_may_be_renamed(tmp_path):
    mgr = _mgr(tmp_path)
    _completed(mgr, _touch(tmp_path, "master.mp4"), status="downloading")
    with pytest.raises(ValueError, match="only a finished download"):
        mgr.rename_job("j1", "later")


def test_clear_completed_keeps_the_files(tmp_path):
    mgr = _mgr(tmp_path)
    files = _touch(tmp_path, "master.mp4")
    _completed(mgr, files)
    gone = mgr.clear_completed()
    assert gone == 1
    with pytest.raises(KeyError):
        mgr.get("j1")
    assert (tmp_path / "master.mp4").exists(), "the file stays on disk"


def test_the_forget_endpoint_asks_for_the_word(tmp_path):
    d = pathlib.Path(tempfile.mkdtemp())
    app = api.create_app(download_dir=d / "dl", auth_token="testtoken",
                         db_path=d / "jobs.db")
    with TestClient(app) as c:
        r = c.post("/jobs/forget", headers=AUTH, json={})
        assert r.status_code == 400, "no confirm, no wipe"
        r = c.post("/jobs/forget", headers=AUTH, json={"confirm": "forget"})
        assert r.status_code == 200
        assert r.json()["cleared_jobs"] == 0


def test_the_ui_offers_rename_and_desktop_only_history(tmp_path):
    root = Path(__file__).resolve().parents[1]
    app_js = (root / "src" / "suravidl_engine" / "web" / "app.js").read_text()
    html = (root / "src" / "suravidl_engine" / "web" / "index.html").read_text()
    assert 'queueClearHistory' in html and "Clear history" in html
    assert "ANDROID()" in app_js                      # the desktop-only gate
    assert "/jobs/forget" in app_js and "/jobs/${j.id}/rename" in app_js
    assert "startRename" in app_js
