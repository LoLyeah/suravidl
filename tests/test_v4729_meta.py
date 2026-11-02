"""v0.47.29 "the hand" — per-download title/artist, and chapter splitting.

Feature #3 and #4 from docs/FEATURES-NEXT.md. Both are "this download only":
they ride the job's overrides, run after the bytes land, and must never leave a
broken row behind — a refused rename or a missing ffmpeg is a note, not a
failure.
"""
import functools
import http.server
import json
import pathlib
import shutil
import subprocess
import threading
import time

import pytest

from suravidl_engine import __version__
from suravidl_engine.cut import ffmpeg_exe
from suravidl_engine.jobs import JobManager
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _wait(mgr, job_id, timeout=90):
    for _ in range(timeout * 10):
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


def _probe(path: pathlib.Path) -> dict:
    exe = ffmpeg_exe().replace("ffmpeg", "ffprobe")
    out = subprocess.run([exe, "-v", "error", "-show_entries",
                          "format=duration:format_tags=title,artist",
                          "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout or "{}")


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_the_notes_name_this_release():
    assert __version__ == "0.47.29"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the hand"
    assert len(ENTRIES) == 10
    for item in ENTRIES[0]["items"]:
        assert 0 < len(item) <= 220


def test_a_title_and_artist_rename_the_file_and_tag_it(tmp_path, server):
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    job = mgr.create(f"{server}/tiny.mp4", overrides={
        "meta_title": "Night Bus", "meta_artist": "The Owner"})
    j = _wait(mgr, job["id"])
    assert j["status"] == "completed", j.get("error")
    files = [pathlib.Path(p) for p in j["files"]]
    assert len(files) == 1
    assert files[0].stem.startswith("Night Bus"), files[0].name

    tags = _probe(files[0]).get("format", {}).get("tags", {})
    assert tags.get("title") == "Night Bus"
    assert tags.get("artist") == "The Owner"


def test_split_by_chapters_makes_one_file_per_section(tmp_path, server):
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    job = mgr.create(f"{server}/tiny.mp4", overrides={
        "split_chapters": True,
        "chapters": [[0.0, 0.5, "Opening"], [0.5, 1.0, "Middle"]],
        "meta_artist": "Split Tester",
    })
    j = _wait(mgr, job["id"])
    assert j["status"] == "completed", j.get("error")
    files = [pathlib.Path(p) for p in j["files"]]
    assert len(files) == 2, [f.name for f in files]
    assert any("01" in f.name and "Opening" in f.name for f in files)
    assert any("02" in f.name and "Middle" in f.name for f in files)
    for f in files:
        assert f.stat().st_size > 0
        assert _probe(f)["format"]["tags"].get("artist") == "Split Tester"
    assert "split into 2" in (j.get("note") or "")


def test_a_bad_chapter_list_is_a_note_not_a_failure(tmp_path, server):
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    job = mgr.create(f"{server}/tiny.mp4", overrides={
        "split_chapters": True, "chapters": [[5.0, 9.0, "past the end"]]})
    j = _wait(mgr, job["id"])
    assert j["status"] == "completed"
    assert "could not split" in (j.get("note") or "")
    assert pathlib.Path(j["filepath"]).exists()


def test_the_form_sends_them_as_this_download_only():
    web = ROOT / "src" / "suravidl_engine" / "web"
    html = (web / "index.html").read_text()
    app = (web / "app.js").read_text()
    assert 'id="ovTitle"' in html and 'id="ovArtist"' in html
    assert 'id="ovSplit"' in html and 'id="ovSplitField"' in html
    body = app[app.index("function readOv()"):]
    body = body[:body.index("\n}\n") + 3]
    assert "meta_title" in body and "meta_artist" in body
    assert "split_chapters" in body and "chapters = CHAPTERS" in body
    # the split switch only exists when the probe found chapters
    chips = app[app.index("function renderChapterChips"):]
    chips = chips[:chips.index("\n}\n") + 3]
    assert "CHAPTERS =" in chips and "ovSplitField" in chips


def test_rename_moves_the_sidecar_too_and_keeps_it_in_files(tmp_path):
    """The bug this pins: the files list was rebuilt with the OLD path for
    anything that did not move, so a sidecar kept a name that no longer
    existed and a later delete would leave it on disk."""
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    (tmp_path / "dl").mkdir(parents=True, exist_ok=True)
    video = tmp_path / "dl" / "Old Title [abc123].mp4"
    subs = tmp_path / "dl" / "Old Title [abc123].en.srt"
    video.write_bytes(b"x")
    subs.write_text("1\n")
    job = {"id": "j1", "url": "http://example.invalid/x", "status": "completed",
           "progress": {"downloaded_bytes": 1, "total_bytes": 1, "speed": 0,
                        "eta": 0},
           "filepath": str(video), "files": [str(video), str(subs)],
           "video_id": "abc123", "title": "Old Title", "overrides": {},
           "headers": None}
    mgr._jobs["j1"] = job
    mgr._retitle(job, "New Title")

    files = [pathlib.Path(p) for p in job["files"]]
    assert len(files) == 2
    assert all(p.exists() for p in files), [p.name for p in files]
    assert {p.suffix for p in files} == {".mp4", ".srt"}
    assert all("New Title" in p.name for p in files)
    assert all("[abc123]" in p.name for p in files)
    assert pathlib.Path(job["filepath"]).exists()


def test_the_uncut_source_is_gone_after_a_split(tmp_path, server):
    """Blocker from the audit: the source stayed on disk while the row owned
    only the sections — delete missed it and the next download saw it as
    "already on disk"."""
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "jobs.db")
    job = mgr.create(f"{server}/tiny.mp4", overrides={
        "split_chapters": True,
        "chapters": [[0.0, 0.4, "A"], [0.4, 0.9, "B"]]})
    j = _wait(mgr, job["id"])
    assert j["status"] == "completed"
    on_disk = sorted(p.name for p in (tmp_path / "dl").iterdir() if p.is_file())
    assert len(on_disk) == 2, on_disk          # the two sections, nothing else
    assert all(pathlib.Path(p).exists() for p in j["files"])


def test_tags_keep_every_stream(tmp_path):
    """Blocker from the audit: a bare `-c copy` takes one stream per type, so
    a second audio track or subtitle track was dropped by a tag rewrite."""
    from suravidl_engine.jobs import JobManager
    exe = ffmpeg_exe()
    src = tmp_path / "multi.mkv"
    subprocess.run([exe, "-y", "-v", "error",
                    "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
                    "-map", "0:v", "-map", "1:a", "-map", "2:a",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
                   check=True, timeout=120)
    mgr = JobManager(download_dir=tmp_path, db_path=tmp_path / "jobs.db")
    mgr._write_tags(src, "T", "A")
    probe = subprocess.run([exe.replace("ffmpeg", "ffprobe"), "-v", "error",
                            "-show_entries", "stream=codec_type", "-of", "json",
                            str(src)], capture_output=True, text=True, timeout=60)
    types = [s["codec_type"] for s in json.loads(probe.stdout)["streams"]]
    assert types.count("audio") == 2, types


def test_the_queue_row_shows_every_chapter_file():
    app = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
    assert "j.split ||" in app, "a split row must list its files, not only the first"
    from suravidl_engine.jobs import redact_job
    assert redact_job({"overrides": {"split_chapters": True}})["split"] is True
    assert redact_job({"overrides": {}})["split"] is False


def test_the_chapter_state_cannot_leak_to_another_link():
    app = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
    body = app[app.index("function clearOv()"):]
    body = body[:body.index("\n}\n") + 3]
    assert "CHAPTERS = []" in body
    assert "ovSplitField" in body
    # every chapter the probe returned, not only the twenty chips
    chips = app[app.index("function renderChapterChips"):]
    chips = chips[:chips.index("\n}\n") + 3]
    assert "CHAPTERS = (info.chapters || [])" in chips


def test_retry_keeps_the_title_and_the_cut():
    app = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
    body = app[app.index("function editAndRetry"):]
    body = body[:body.index("\n}\n") + 3]
    assert "ov.meta_title" in body and "ov.meta_artist" in body
    assert "ov.split_chapters" in body
