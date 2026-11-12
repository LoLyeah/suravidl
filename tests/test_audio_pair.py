"""A feed's picture and sound are two files; one job must still land one file.

The owner's macOS report (2026-11-12): a reel downloaded from the extension's
card had no audio. Facebook serves the soundtrack as its own track, the card
sent only the picture, and the engine had no way to pair them.
"""
from pathlib import Path

import pytest

from suravidl_engine import jobs as jobs_mod


def _manager(tmp_path):
    return jobs_mod.JobManager(download_dir=tmp_path / "dl",
                               db_path=str(tmp_path / "jobs.db"))


def _fake_ffmpeg(tmp_path):
    """A stand-in that writes the file it was told to, and nothing else."""
    exe = tmp_path / "ffmpeg"
    exe.write_text("#!/bin/sh\n"
                   'for a in "$@"; do out="$a"; done\n'
                   'printf joined > "$out"\n')
    exe.chmod(0o755)
    return exe


def test_a_job_carries_the_paired_audio_track(tmp_path):
    mgr = _manager(tmp_path)
    job = mgr.create("https://cdn.example/v.mp4",
                     audio_url="https://cdn.example/a.m4a")
    assert job["audio_url"] == "https://cdn.example/a.m4a"


def test_the_audio_url_is_checked_at_the_door(tmp_path):
    mgr = _manager(tmp_path)
    with pytest.raises(ValueError):
        mgr.create("https://cdn.example/v.mp4",
                   audio_url="http://169.254.169.254/latest/meta-data")


def test_the_track_is_joined_into_the_video(tmp_path, monkeypatch):
    mgr = _manager(tmp_path)
    target = tmp_path / "dl"
    target.mkdir(parents=True, exist_ok=True)
    video = target / "reel.mp4"
    video.write_bytes(b"picture" * 100)
    audio = target / "reel-audio.m4a"
    audio.write_bytes(b"sound" * 10)

    def fake_extract(opts, url, *, download, **kwargs):
        assert url == "https://cdn.example/a.m4a"
        assert opts["format"] == "bestaudio/b"
        assert "postprocessors" not in opts          # the picture's, not the track's
        return {"requested_downloads": [{"filepath": str(audio)}]}

    monkeypatch.setattr(jobs_mod, "extract_info", fake_extract)
    monkeypatch.setattr("suravidl_engine.cut.ffmpeg_exe",
                        lambda: str(_fake_ffmpeg(tmp_path)))

    job = {"id": "abc123", "filepath": str(video), "files": [str(video)],
           "audio_url": "https://cdn.example/a.m4a"}
    mgr._join_audio(job, {"format": "best", "postprocessors": [{"x": 1}]}, target)

    assert job["filepath"] == str(video)
    assert Path(job["filepath"]).read_bytes() == b"joined"
    assert job["files"] == [str(video)]
    assert not audio.exists()                        # the track is not left behind
    assert not (target / ".sv-join-abc123.mp4").exists()


def test_a_join_that_fails_leaves_the_picture_and_says_so(tmp_path, monkeypatch):
    mgr = _manager(tmp_path)
    target = tmp_path / "dl"
    target.mkdir(parents=True, exist_ok=True)
    video = target / "reel.mp4"
    video.write_bytes(b"picture")

    def broken(opts, url, *, download, **kwargs):
        raise RuntimeError("the track expired")

    monkeypatch.setattr(jobs_mod, "extract_info", broken)
    monkeypatch.setattr("suravidl_engine.cut.ffmpeg_exe",
                        lambda: str(_fake_ffmpeg(tmp_path)))

    job = {"id": "def456", "filepath": str(video), "files": [str(video)],
           "audio_url": "https://cdn.example/a.m4a"}
    mgr._join_audio(job, {}, target)

    assert job["filepath"] == str(video)
    assert video.read_bytes() == b"picture"
    assert "downloaded without sound" in (job.get("note") or "")


def test_without_ffmpeg_the_picture_still_completes(tmp_path, monkeypatch):
    mgr = _manager(tmp_path)
    target = tmp_path / "dl"
    target.mkdir(parents=True, exist_ok=True)
    video = target / "reel.mp4"
    video.write_bytes(b"picture")
    monkeypatch.setattr("suravidl_engine.cut.ffmpeg_exe", lambda: "")

    job = {"id": "ghi789", "filepath": str(video), "files": [str(video)],
           "audio_url": "https://cdn.example/a.m4a"}
    mgr._join_audio(job, {}, target)

    assert job["filepath"] == str(video)
    assert "ffmpeg is not installed" in (job.get("note") or "")
