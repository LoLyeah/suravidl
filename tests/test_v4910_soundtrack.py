"""v0.49.10 "the soundtrack" — a feed's picture gets its sound.

The owner downloaded a reel from the extension's card and the file had no
audio: Facebook serves the picture and the soundtrack as two files. The
extension now sends the pair and the engine joins them with ffmpeg, so one
job still lands one playable file.
"""
import inspect
import pathlib

from suravidl_engine import __version__, jobs
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "suravidl_engine" / "api.py").read_text()
POPUP = (ROOT / "extension" / "popup.js").read_text()
BACKGROUND = (ROOT / "extension" / "background.js").read_text()


def test_the_notes_name_this_release():
    # v0.49.11 took the newest slot; this release's entry stays in the card
    assert __version__ == "0.49.12"
    assert ENTRIES[0]["version"] == __version__
    entry = next(e for e in ENTRIES if e["version"] == "0.49.10")
    assert entry["title"].lower() == "the soundtrack"
    assert len(ENTRIES) == 10


def test_the_job_door_carries_the_paired_track():
    assert "audio_url: str | None = None" in API
    assert "audio_url=body.audio_url" in API
    params = list(inspect.signature(jobs.JobManager.create).parameters)
    assert params[-1] == "audio_url"


def test_the_join_says_what_it_could_not_do():
    src = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text()
    assert "downloaded without sound" in src
    # the app can fetch ffmpeg itself, so the note points there
    assert "Settings can fetch it" in src


def test_both_doors_remain_on_a_card():
    # the card is a div with two actions: best-quality download, and the
    # app's own chooser for the same video
    assert 'dl.textContent = t("Download");' in POPUP
    assert 'q.textContent = t("Quality");' in POPUP
    assert 'q.onclick = () => send(best.url, "quality");' in POPUP
    assert "audioUrl: (audio || \"\")" in POPUP
    assert "audio_url: audioUrl || undefined" in BACKGROUND
