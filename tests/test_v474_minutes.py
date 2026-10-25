"""v0.47.4 "the minutes" — a failed finish keeps its own trail.

The 2026-10-18 Windows report — "Postprocessing: Error opening output
files: Invalid argument" — cost a round-trip because yt-dlp's ffmpeg
command and stderr were only kept when the user had found a verbose
toggle. Jobs now always log through the bounded, scrubbed buffer behind
the Log card, and the output-open failure explains itself in plain words.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_job_keeps_ytdlps_trail():
    """The Log card must be able to explain a postprocessing death without
    the user having to find a toggle first (2026-10-18 field report)."""
    jobs = (ROOT / "src/suravidl_engine/jobs.py").read_text()
    assert "from . import logcap" in jobs
    assert 'opts["verbose"] = True' in jobs
    assert 'opts["logger"] = logcap.logger()' in jobs


def test_the_output_open_failure_speaks_plainly():
    from suravidl_engine.auth import explain_download_error

    out = explain_download_error(
        "ERROR: Postprocessing: Error opening output files: Invalid argument")
    assert "download itself finished" in out
    assert "View log" in out
    assert "antivirus" in out


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__, whatsnew

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # retired by v0.47.14 "the seal": ten releases later, the card is
    # rolling — the behaviour it pinned is covered by its own tests above
    assert "0.47.4" not in [e["version"] for e in whatsnew.ENTRIES]
    assert "the minutes" not in [e["title"].lower() for e in whatsnew.ENTRIES]
