"""v0.45.28 "the captions" — subtitle embedding respects the phone's ffmpeg.

Field report (2026-10-10, Android): a reddit job died with
`ERROR: Postprocessing: Error opening output files: Encoder not found`
while retrying. The shipped Android ffmpeg ACCEPTS
`--enable-encoder=mov_text` in its configure line yet never materializes
it (probed on the build's replica: aac/flac/srt/webvtt are real,
mov_text is not) — and mov_text is exactly what embedding text subs
into an MP4 needs. With Subtitles = embed, the whole post-process pass
died; the raw text also misled (the "404 — check it was copied whole"
arm swallowed it first on the card). Now:
- the embed PP is skipped when the binary cannot encode it AND the
  container is not mkv (matroska carries text subs by copy), leaving the
  sidecar files writesubtitles already wrote;
- the UI says both truths it was hiding: the Reddit /s/ share-link trap
  and the phone's encoder hole.
"""
from pathlib import Path

from suravidl_engine.download_opts import build_download_opts
from suravidl_engine.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(encoding="utf-8")


def _settings(tmp_path, **kv):
    s = Settings(path=tmp_path / "settings.json")
    d = s.get()
    d.update({"subtitles_mode": "embed", "subtitles_langs": "en", **kv})
    return d


def test_embed_is_skipped_when_the_ffmpeg_cannot_encode(tmp_path, monkeypatch):
    from suravidl_engine import download_opts as do

    monkeypatch.setattr(do, "ffmpeg_can_encode", lambda name: False)
    opts = build_download_opts(_settings(tmp_path), str(tmp_path / "dl"))
    keys = [p.get("key") for p in (opts.get("postprocessors") or [])]
    assert "FFmpegEmbedSubtitle" not in keys, \
        "the phone cannot embed into an mp4 — the pass must not die"
    assert opts.get("writesubtitles") is True, "subs still land as sidecars"


def test_embed_survives_with_mkv_or_a_capable_ffmpeg(tmp_path, monkeypatch):
    from suravidl_engine import download_opts as do

    monkeypatch.setattr(do, "ffmpeg_can_encode", lambda name: False)
    opts = build_download_opts(_settings(tmp_path, video_container="mkv"),
                               str(tmp_path / "dl"))
    keys = [p.get("key") for p in (opts.get("postprocessors") or [])]
    assert "FFmpegEmbedSubtitle" in keys, "mkv carries text subs by copy"

    monkeypatch.setattr(do, "ffmpeg_can_encode", lambda name: True)
    opts = build_download_opts(_settings(tmp_path), str(tmp_path / "dl"))
    keys = [p.get("key") for p in (opts.get("postprocessors") or [])]
    assert "FFmpegEmbedSubtitle" in keys, "a full ffmpeg embeds anywhere"


def test_the_honest_lines_exist():
    assert "Reddit share links" in APP and "only open in a browser" in APP
    assert "encoder not found" in APP and "sidecar" in APP
    assert 'humanErr(j.error || "", undefined, j.url)' in APP, \
        "the job row must pass its url into the mapper"
