"""v0.45.6 "the cover" — thumbnail files get the extension their bytes claim.

The Android report (2026-10-05): "Error opening output files: Invalid
argument" while embedding the cover of a TikTok download. The cover URL
ends `~~~~tplv-tiktokx-origin.image`, so the file landed as `<title>.image`
with plain JPEG bytes; the embedder converts anything that is not
jpg/jpeg/png before attaching, and the conversion handed ffmpeg `-f image2`
with a name no build can map to a codec.
"""
import yt_dlp  # noqa: F401 - the fixer's base class comes from here

from suravidl_engine import extract

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4
GIF = b"GIF89a" + b"\x00" * 10
AVIF = b"\x00\x00\x00\x20ftypavif" + b"\x00" * 4


def test_sniffing_speaks_magic():
    assert extract._sniff_image_ext(JPEG) == "jpg"
    assert extract._sniff_image_ext(PNG) == "png"
    assert extract._sniff_image_ext(WEBP) == "webp"
    assert extract._sniff_image_ext(GIF) == "gif"
    assert extract._sniff_image_ext(AVIF) == "avif"
    assert extract._sniff_image_ext(b"not an image at all") is None


def test_an_image_ext_fixes_the_name(tmp_path):
    f = tmp_path / "cover.image"
    f.write_bytes(JPEG)
    info = {"thumbnails": [{"filepath": str(f)}],
            "__files_to_move": {str(f): "/dl/cover.image"}}
    _, out = extract.ThumbnailExtFixPP(None).run(info)
    fixed = tmp_path / "cover.jpg"
    assert fixed.exists() and not f.exists()
    assert out["thumbnails"][0]["filepath"] == str(fixed)
    assert out["__files_to_move"] == {str(fixed): "/dl/cover.jpg"}


def test_a_name_without_any_extension_is_fixed_too(tmp_path):
    f = tmp_path / "cover"
    f.write_bytes(PNG)
    info = {"thumbnails": [{"filepath": str(f)}]}
    _, out = extract.ThumbnailExtFixPP(None).run(info)
    assert out["thumbnails"][0]["filepath"].endswith("cover.png")


def test_a_known_extension_is_left_alone(tmp_path):
    for name in ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp"):
        f = tmp_path / name
        f.write_bytes(JPEG)
        extract.ThumbnailExtFixPP(None).run({"thumbnails": [{"filepath": str(f)}]})
        assert f.exists(), name


def test_unknown_bytes_stay_put(tmp_path):
    f = tmp_path / "cover.image"
    f.write_bytes(b"<html>not an image</html>")
    extract.ThumbnailExtFixPP(None).run({"thumbnails": [{"filepath": str(f)}]})
    assert f.exists()


def test_missing_file_and_no_thumbnails_are_fine(tmp_path):
    extract.ThumbnailExtFixPP(None).run(
        {"thumbnails": [{"filepath": str(tmp_path / "gone.image")}]})
    extract.ThumbnailExtFixPP(None).run({})


def test_attach_puts_the_fixer_first():
    class _YDL:
        def __init__(self):
            self.added = []
            self._pps = {"post_process": [object()]}

        def add_post_processor(self, pp, when=None):
            self.added.append((pp, when))
            self._pps.setdefault(when or "post_process", []).append(pp)

    ydl = _YDL()
    other = ydl._pps["post_process"][0]
    extract._attach_thumbnail_ext_fix(ydl)
    assert len(ydl.added) == 1 and ydl.added[0][1] == "post_process"
    chain = ydl._pps["post_process"]
    assert chain[0] is ydl.added[0][0] and other in chain


def test_attach_never_breaks_a_job():
    class _Bare:
        pass
    extract._attach_thumbnail_ext_fix(_Bare())  # no raise
