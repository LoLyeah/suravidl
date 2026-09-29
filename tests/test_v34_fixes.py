"""v0.34.0 — subtitles are a sidecar; presets are editable.

Two field reports: an m4a job died on "Unable to download video subtitles
for 'en': HTTP Error 429" before the audio ever started (a refused caption
track must not cost the media), and the "This download only" preset row
could apply a bundle but never save one, show what it carries, or change
what it sets.
"""
import time
from pathlib import Path

import yt_dlp

ROOT = Path(__file__).parent.parent
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text(encoding="utf-8")

SUB_ERROR = ("ERROR: Unable to download video subtitles for 'en': "
             "HTTP Error 429: Too Many Requests")


def _manager(tmp_path, **kw):
    from suravidl_engine import jobs as jobs_mod

    return jobs_mod.JobManager(download_dir=tmp_path / "dl",
                               db_path=str(tmp_path / "jobs.db"), **kw)


def _wait_done(mgr, job_id, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        job = mgr.get(job_id)
        if job and job.get("status") in ("completed", "error", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError("job never settled: " + repr(mgr.get(job_id)))


def _fake_extract(calls, message="", fail_times=0, filepath=None):
    def fake(opts, url, download=False, retry_refresh=False):
        calls.append(dict(opts))
        if len(calls) <= fail_times:
            raise yt_dlp.utils.DownloadError(message)
        return {"id": "x", "title": "clip",
                "requested_downloads": [{"filepath": filepath}]}
    return fake


def _sub_opts(_dir, raw_args=None, overrides=None):
    return {"writesubtitles": True, "subtitleslangs": ["en"]}


# -- 1. a refused subtitle track must not cost the media ---------------------

def test_a_refused_subtitle_track_does_not_lose_the_download(tmp_path, monkeypatch):
    """The report: m4a preset + subtitles on in settings → the caption fetch
    429'd and the whole job failed before any audio downloaded."""
    from suravidl_engine import jobs as jobs_mod

    calls = []
    fp = str(tmp_path / "dl" / "clip.mp4")
    monkeypatch.setattr(jobs_mod, "extract_info",
                        _fake_extract(calls, SUB_ERROR, fail_times=1,
                                      filepath=fp))
    mgr = _manager(tmp_path, download_opts=_sub_opts)
    job = mgr.create("https://example.invalid/clip")
    done = _wait_done(mgr, job["id"])
    assert done["status"] == "completed"
    note = done.get("note") or ""
    assert "subtitles could not be fetched" in note
    assert "429" in note, "the row says why, not just that"
    assert len(calls) == 2, "one retry, this time without subtitles"
    assert calls[0].get("writesubtitles") is True
    assert "writesubtitles" not in calls[1]
    assert "subtitleslangs" not in calls[1]


def test_an_ordinary_failure_is_still_a_failure(tmp_path, monkeypatch):
    from suravidl_engine import jobs as jobs_mod

    calls = []
    monkeypatch.setattr(jobs_mod, "extract_info",
                        _fake_extract(calls, "ERROR: Unsupported URL: https://x",
                                      fail_times=99))
    mgr = _manager(tmp_path, download_opts=_sub_opts)
    job = mgr.create("https://example.invalid/x")
    done = _wait_done(mgr, job["id"])
    assert done["status"] == "error"
    assert len(calls) == 1, "only subtitle refusals get the retry"


def test_the_subtitle_retry_is_offered_once(tmp_path, monkeypatch):
    from suravidl_engine import jobs as jobs_mod

    calls = []
    monkeypatch.setattr(jobs_mod, "extract_info",
                        _fake_extract(calls, SUB_ERROR, fail_times=99))
    mgr = _manager(tmp_path, download_opts=_sub_opts)
    job = mgr.create("https://example.invalid/clip")
    done = _wait_done(mgr, job["id"])
    assert done["status"] == "error"
    assert "subtitle" in (done.get("error") or "").lower()
    assert len(calls) == 2, "one retry; no endless loop"


def test_drop_subtitles_cleans_every_related_option():
    from suravidl_engine.jobs import _drop_subtitles

    opts = {"writesubtitles": True, "writeautomaticsub": True,
            "subtitleslangs": ["en"], "subtitlesformat": "srt",
            "postprocessors": [
                {"key": "FFmpegSubtitlesConvertor", "format": "srt"},
                {"key": "FFmpegEmbedSubtitle"},
                {"key": "FFmpegMetadata", "add_metadata": True}],
            "format": "bestaudio"}
    _drop_subtitles(opts)
    for gone in ("writesubtitles", "writeautomaticsub", "subtitleslangs",
                 "subtitlesformat"):
        assert gone not in opts, gone
    assert opts["postprocessors"] == [{"key": "FFmpegMetadata",
                                       "add_metadata": True}]
    assert opts["format"] == "bestaudio", "nothing else is touched"


def test_subtitle_errors_are_told_apart_from_media_errors():
    from suravidl_engine.jobs import _is_subtitle_error, _subtitle_reason

    assert _is_subtitle_error(yt_dlp.utils.DownloadError(SUB_ERROR))
    assert not _is_subtitle_error(yt_dlp.utils.DownloadError(
        "ERROR: unable to download video data: HTTP Error 403: Forbidden"))
    assert not _is_subtitle_error(yt_dlp.utils.DownloadError(
        "ERROR: Unsupported URL: https://x"))
    assert _subtitle_reason(yt_dlp.utils.DownloadError(SUB_ERROR)) == \
        "HTTP Error 429: Too Many Requests"


# -- 2. the preset row: save, see, and change --------------------------------

def test_the_preset_block_can_save_show_and_change_a_preset():
    seg = HTML.split('id="ovBlock"')[1].split("</details>")[0]
    for eid in ("ovPresetInfo", "ovSaveLink", "ovUpdate", "ovSaveRow",
                "ovSaveName", "ovSaveGo", "ovSaveCancel", "ovSaveMsg"):
        assert f'id="{eid}"' in seg, eid
    for pin in ('$("ovSaveLink").onclick', '$("ovSaveGo").onclick',
                '$("ovUpdate").onclick', "function presetFromPanel",
                "function renderOvPresetInfo", "function renderOvPresetActions",
                "async function savePanelPreset", "async function updatePanelPreset"):
        assert pin in APP, pin


def test_the_applied_preset_shows_every_key_it_carries():
    """The block shows a few fields; a preset may carry more, and those used
    to ride invisibly. The info line spells them all out."""
    seg = APP.split("function renderOvPresetInfo")[1].split("\nfunction ")[0]
    assert 'k + "=" + patch[k]' in seg
    assert "OV.name" in seg


def test_update_only_exists_for_your_own_presets():
    """A built-in is code — it can be copied, never overwritten."""
    seg = APP.split("function renderOvPresetActions")[1].split("\nfunction ")[0]
    assert "entry.builtin" in seg


def test_the_save_flow_stores_the_panel_itself():
    seg = APP.split("function presetFromPanel")[1].split("\nfunction ")[0]
    assert "readOv()" in seg and "patch.preset = OV.preset" in seg
    seg2 = APP.split("async function savePanelPreset")[1].split("\nasync function ")[0]
    assert 'await api("/presets"' in seg2 and "OV.name = name" in seg2
    seg3 = APP.split("async function updatePanelPreset")[1].split("\nasync function ")[0]
    assert 'await api("/presets"' in seg3 and "entry.name" in seg3
