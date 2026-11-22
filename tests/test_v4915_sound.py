"""A silent download is a failure the app must notice, not inherit.

Field report (2026-11-22): the same kind of friends-only reel sometimes lands
with sound and sometimes does not. Gemini 4 Neon's diagnosis: the card door
downloads one sniffed address, that address is often a picture-only stream,
and a mux failure was swallowed. The engine now asks the finished file whether
it has a sound track, retries once through the page it came from, and says so
when even that cannot find one.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from suravidl_engine import jobs as jobs_mod

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg is not installed")


def _manager(tmp_path):
    return jobs_mod.JobManager(download_dir=tmp_path / "dl",
                               db_path=str(tmp_path / "jobs.db"))


def _video(target: Path, *, sound: bool) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1"]
    if sound:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-shortest", "-c:v", "libx264", "-c:a", "aac"]
    else:
        cmd += ["-an", "-c:v", "libx264"]
    subprocess.run(cmd + [str(target)], check=True, capture_output=True)
    return target


def test_a_job_carries_the_page_it_came_from(tmp_path):
    mgr = _manager(tmp_path)
    job = mgr.create("https://cdn.example/v.mp4",
                     page_url="https://www.facebook.com/reel/123")
    assert job["page_url"] == "https://www.facebook.com/reel/123"


def test_a_page_url_is_checked_at_the_door(tmp_path):
    mgr = _manager(tmp_path)
    with pytest.raises(ValueError):
        mgr.create("https://cdn.example/v.mp4",
                   page_url="http://169.254.169.254/latest/meta-data")


@needs_ffmpeg
def test_ffprobe_sees_a_sound_track_and_its_absence(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr._ffprobe_audio(_video(tmp_path / "silent.mp4", sound=False)) is False
    assert mgr._ffprobe_audio(_video(tmp_path / "sound.mp4", sound=True)) is True


def test_a_file_that_is_not_there_answers_nothing(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr._ffprobe_audio(tmp_path / "missing.mp4") is None


def test_the_retry_is_refused_without_a_page(tmp_path):
    mgr = _manager(tmp_path)
    job = {"id": "j1", "url": "https://cdn.example/v.mp4", "page_url": None}
    assert mgr._retry_with_page(job, {}, tmp_path) is False


def test_the_retry_is_refused_when_the_page_is_the_url(tmp_path):
    mgr = _manager(tmp_path)
    job = {"id": "j1", "url": "https://site/reel/1",
           "page_url": "https://site/reel/1"}
    assert mgr._retry_with_page(job, {}, tmp_path) is False


def test_the_retry_happens_once(tmp_path):
    mgr = _manager(tmp_path)
    job = {"id": "j1", "url": "https://cdn.example/v.mp4",
           "page_url": "https://site/reel/1", "_page_retry": True}
    assert mgr._retry_with_page(job, {}, tmp_path) is False


@needs_ffmpeg
def test_the_page_retry_replaces_a_silent_file(tmp_path, monkeypatch):
    mgr = _manager(tmp_path)
    silent = _video(tmp_path / "dl" / "reel.mp4", sound=False)
    with_sound = _video(tmp_path / "dl" / "page-copy.mp4", sound=True)

    monkeypatch.setattr(jobs_mod, "extract_info", lambda *a, **k: {
        "requested_downloads": [{"filepath": str(with_sound)}],
        "filepath": str(with_sound),
    })
    job = {"id": "j1", "url": "https://cdn.example/v.mp4",
           "page_url": "https://site/reel/1", "filepath": str(silent)}

    assert mgr._retry_with_page(job, {}, silent.parent) is True
    assert mgr._ffprobe_audio(job["filepath"]) is True
    assert "the sniffed address had no sound" in (job.get("note") or "")


@needs_ffmpeg
def test_a_page_copy_that_is_also_silent_is_not_taken(tmp_path, monkeypatch):
    mgr = _manager(tmp_path)
    silent = _video(tmp_path / "dl" / "reel.mp4", sound=False)
    also_silent = _video(tmp_path / "dl" / "page-copy.mp4", sound=False)

    monkeypatch.setattr(jobs_mod, "extract_info", lambda *a, **k: {
        "requested_downloads": [{"filepath": str(also_silent)}],
        "filepath": str(also_silent),
    })
    job = {"id": "j1", "url": "https://cdn.example/v.mp4",
           "page_url": "https://site/reel/1", "filepath": str(silent)}

    assert mgr._retry_with_page(job, {}, silent.parent) is False
    assert job["filepath"] == str(silent)      # the picture is still the file
    assert not also_silent.exists()            # the rejected copy is cleaned up
