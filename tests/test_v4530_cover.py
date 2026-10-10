"""v0.45.30 "the cover" — a thumbnail embed cannot kill a finished job.

Field report (2026-10-10, Android, reddit): the job died with
`Unable to embed using ffprobe & ffmpeg; Conversion failed!` — after the
video itself had already downloaded. The chain: neither mutagen nor
AtomicParsley ships in this app, so yt-dlp's thumbnail embed falls back
to ffmpeg; that fallback must READ the thumbnail's bytes, and the phone
build has NO webp decoder (probed: absent from the release replica)
while reddit serves webp covers. The engine now swaps yt-dlp's embedder
for a subclass whose failure warns, leaves the video alone, and lands on
the card as a caveat through the v0.45.29 channel. The old raw text also
gets its own honest UI line instead of the misleading generic ffmpeg arm.
"""
import yt_dlp
from yt_dlp.postprocessor.embedthumbnail import EmbedThumbnailPP
from yt_dlp.utils import PostProcessingError

from suravidl_engine import extract as ex


def test_a_failing_thumbnail_embed_does_not_kill_the_job(monkeypatch):
    ydl = yt_dlp.YoutubeDL({"quiet": True})
    ydl.add_post_processor(EmbedThumbnailPP(ydl), when="post_process")

    ex._install_safe_thumbnail_embed(ydl)
    chain = ydl._pps.get("post_process") or []
    assert chain, "the embed must remain in the chain"
    safe = chain[-1]
    assert type(safe).__name__ == "SafeThumbnailEmbedPP", \
        "the chain entry must be the guarded subclass"

    def boom(self, info):
        raise PostProcessingError("Conversion failed!")

    monkeypatch.setattr(EmbedThumbnailPP, "run", boom)
    info = {}
    files, out = safe.run(info)          # must NOT raise
    assert files == [] and out is info
    notices = info.get("__sv_notices") or []
    assert any("thumbnail could not be embedded" in n for n in notices), notices


def test_the_old_raw_text_maps_honestly(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "src" / "suravidl_engine" / "web" / "app.js").read_text(
        encoding="utf-8")
    assert "unable to embed using" in app.lower()
    assert "the video itself is fine" in app
    src = (root / "src" / "suravidl_engine" / "extract.py").read_text(
        encoding="utf-8")
    assert "_install_safe_thumbnail_embed(ydl)" in src, "the swap must be wired"
