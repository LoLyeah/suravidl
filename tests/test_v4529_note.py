"""v0.45.29 "the note" — a finished job with a caveat says so, visibly.

Owner's request (2026-10-10): "You tell the user if the intended feature
isn't possible but the file is still coming after the file is done" —
with an info mark in the queue tab. Both recent silent degradations earn
it: the subtitle embed skipped because the phone's ffmpeg cannot encode
mov_text, and the stream fixer dropping an unusable track. The job still
SUCCEEDS; the card now carries an ⓘ and the reason.

Channel: build_download_opts collects `__sv_notices` (popped by
_execute, never shown to yt-dlp); the stream fixer's drops reach the
info dict via the finished hook (`__sv_notices` too). Both merge into
the job's `note`, which every card renders next to the ⓘ.
"""
from pathlib import Path

from suravidl_engine.download_opts import build_download_opts
from suravidl_engine.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(encoding="utf-8")


def test_the_skipped_embed_leaves_a_notice(tmp_path, monkeypatch):
    from suravidl_engine import download_opts as do

    monkeypatch.setattr(do, "ffmpeg_can_encode", lambda name: False)
    s = Settings(path=tmp_path / "settings.json").get()
    s.update({"subtitles_mode": "embed", "subtitles_langs": "en"})
    opts = build_download_opts(s, str(tmp_path / "dl"))
    got = opts.get("__sv_notices") or []
    assert any("subtitles are kept as files" in n for n in got), got

    # no skip -> no notice
    monkeypatch.setattr(do, "ffmpeg_can_encode", lambda name: True)
    opts = build_download_opts(s, str(tmp_path / "dl"))
    assert not opts.get("__sv_notices")


def test_a_completed_job_carries_the_notice(tmp_path, monkeypatch):
    from suravidl_engine import jobs as jobs_mod
    from suravidl_engine.jobs import JobManager

    out = tmp_path / "dl"
    out.mkdir()
    made = out / "T.mp4"
    made.write_bytes(b"video")

    captured = {}

    def fake_extract(opts, url, **kw):
        captured["opts"] = dict(opts)
        return {
            "title": "T",
            "requested_downloads": [{"filepath": str(made)}],
            "__sv_notices": ["one unusable stream was removed (1:Audio/mp3)"],
        }

    monkeypatch.setattr(jobs_mod, "extract_info", fake_extract)

    def opts_with_notice(dl_dir, raw_args=None, overrides=None):
        return {"__sv_notices": ["subtitles are kept as files beside the video"]}

    mgr = JobManager(download_dir=out, db_path=tmp_path / "j.db",
                     auto_resume=True, download_opts=opts_with_notice)
    job = mgr.create("https://example.invalid/v")

    import time
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if mgr.get(job["id"])["status"] == "completed":
            break
        time.sleep(0.05)
    s = mgr.get(job["id"])
    assert s["status"] == "completed"
    note = s.get("note") or ""
    assert "subtitles are kept as files" in note, note
    assert "one unusable stream was removed" in note, note
    # the marker never reaches yt-dlp: it was popped before opts.update
    assert "__sv_notices" not in captured["opts"], \
        "the marker must be popped before the downloader sees it"


def test_the_info_mark_is_real():
    assert 'id="i-info"' in INDEX, "the ⓘ symbol must exist in the sprite"
    assert 'hint.append(ico("info"))' in APP, "the note line must wear the ⓘ"
    assert ".jobhint .ico" in CSS, "the icon needs its inline sizing"
