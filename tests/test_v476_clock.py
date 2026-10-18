"""v0.47.6 "the clock" — the finishing phase names its step and counts up.

Field screenshot (2026-10-18): a 570 MB episode sat under a dead "MERGING"
bar for minutes. The copy-mux was working the whole time — but nothing on
the card said so. Every postprocessor step now names itself (joining,
repacking, embedding…), carries a start time, and the card prints the step
with a ticking clock.
"""
import time
from pathlib import Path

from suravidl_engine import jobs

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()


def test_a_merge_names_itself_and_starts_a_clock():
    job: dict = {"status": "downloading"}
    before = time.time()
    assert jobs._pp_note(job, {"status": "started",
                               "postprocessor": "FFmpegMerger"}) is True
    assert job["status"] == "merging"
    assert job["phase"]["label"] == "joining video and audio"
    assert job["phase"]["started"] >= before


def test_every_known_step_has_a_human_name():
    for pp in ("FFmpegMerger", "FFmpegVideoRemuxer", "FFmpegEmbedSubtitle",
               "FFmpegMetadata", "EmbedThumbnail", "MoveFiles"):
        assert pp in jobs._PP_LABELS, f"{pp} would fall back to the generic line"


def test_an_unknown_step_still_speaks():
    job = {}
    jobs._pp_note(job, {"status": "started", "postprocessor": "SomeNewPP"})
    assert job["phase"]["label"] == "finishing the file"


def test_the_clock_clears_when_the_step_finishes():
    job = {}
    jobs._pp_note(job, {"status": "started", "postprocessor": "FFmpegMerger"})
    assert jobs._pp_note(job, {"status": "finished",
                               "postprocessor": "FFmpegMerger"}) is True
    assert job["phase"] is None


def test_a_download_event_is_never_read_as_a_postprocessor_event():
    """Both hook kinds say "finished" — the download branch must win."""
    job = {"status": "downloading"}
    assert jobs._pp_note(job, {"status": "finished", "filename": "x.mp4"}) is False
    assert "phase" not in job
    assert job["status"] == "downloading"


def test_the_card_prints_the_step_and_a_ticking_clock():
    assert "j.phase" in APP
    assert "mmss(" in APP
    assert ".jphase" in CSS
    # the labels reach the card, and the Indonesian dictionary carries them
    assert "joining video and audio" in APP
    assert "menggabungkan video dan audio" in APP
