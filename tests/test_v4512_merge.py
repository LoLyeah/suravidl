"""v0.45.12 "the merge" — the 953 MB merge that died at the metadata pass.

Report (Android, 2026-10-07): an HLS stream ("master.m3u8") downloaded
fully — 952.88 MiB — then failed: "Postprocessing: Conversion failed!".
The log told the story: the download is mpegts wearing an .mp4 name and
carries TWO audio tracks, one of them headerless (ffprobe: "mp3, 0
channels"; the decoder spams "Header missing"). yt-dlp's metadata pass
copies EVERY stream (-map 0 -c copy), the mp4 muxer refuses the
headerless one ("sample rate not set" -> "Could not write header ...
Invalid argument") and the job dies after the whole download.
StreamCopyFixPP drops only the unusable streams, once, before the
metadata pass — healthy files pay one ffprobe and nothing else.
Reproduced on Linux with the same ffmpeg build class before fixing; the
exact failing command exits non-zero pre-fix and 0 post-fix.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from suravidl_engine.extract import StreamCopyFixPP  # noqa: E402


def _usable(**fields):
    pp = StreamCopyFixPP.__new__(StreamCopyFixPP)   # no downloader needed
    return pp._usable(fields)


def test_the_stream_picker_drops_only_the_unusable():
    # the field shape: a headerless mp3 beside a healthy aac
    assert _usable(codec_type="audio", codec_name="mp3", channels=0, sample_rate="0") is False
    assert _usable(codec_type="audio", codec_name="aac", channels=1, sample_rate="44100") is True
    assert _usable(codec_type="audio", codec_name="mp3", channels=2, sample_rate="44100") is True
    assert _usable(codec_type="video", codec_name="h264", width=320) is True
    assert _usable(codec_type="video", codec_name="none", width=0) is False
    assert _usable(codec_type="subtitle", codec_name="webvtt") is True
    assert _usable(codec_type="data", codec_name="bin_data") is False


def test_the_fixer_rides_the_download_path():
    src = (SRC / "suravidl_engine" / "extract.py").read_text(encoding="utf-8")
    assert "class StreamCopyFixPP(FFmpegPostProcessor):" in src
    i = src.index("def _attach_stream_copy_fix")
    seg = src[i:i + 900]
    assert 'when="post_process"' in seg
    assert "chain.insert(0, pp)" in seg, "the metadata pass must meet it first"
    assert "_attach_stream_copy_fix(ydl)" in src.split("def extract_info")[1], \
        "attached on the download path"


# --- the real thing: craft the field state, prove the failure, prove the fix ---

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def _corrupt_mp3_pid(raw: bytes, pid: int) -> bytes:
    out = bytearray(raw)
    for off in range(0, len(raw) - 187, 188):
        if raw[off] != 0x47:
            continue
        p = ((raw[off + 1] & 0x1F) << 8) | raw[off + 2]
        if p == pid:
            out[off + 4:off + 188] = b"\x00" * 184
    return bytes(out)


def _pid_of(stream: dict) -> int:
    raw = str(stream.get("id", "0"))
    return int(raw, 16) if raw.lower().startswith("0x") else int(raw)


@pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe not on PATH")
def test_the_field_failure_is_reproduced_and_cured(tmp_path):
    # 1) the field shape: mpegts (named .mp4) with a broken mp3 + a healthy aac
    base = tmp_path / "base.ts"
    subprocess.run([FFMPEG, "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=15:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
                    "-map", "0:v", "-map", "1:a", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a:0", "mp3", "-c:a:1", "aac",
                    "-f", "mpegts", str(base)], check=True, capture_output=True)
    streams = json.loads(subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", str(base)],
        capture_output=True, text=True, check=True).stdout)["streams"]
    mp3_pid = _pid_of([s for s in streams if s.get("codec_name") == "mp3"][0])
    broken = tmp_path / "master.mp4"
    broken.write_bytes(_corrupt_mp3_pid(base.read_bytes(), mp3_pid))

    meta = [FFMPEG, "-y", "-loglevel", "repeat+info", "-i", str(broken), "-map", "0",
            "-dn", "-ignore_unknown", "-c", "copy", "-write_id3v1", "1",
            "-metadata", "title=master"]
    # 2) the exact failing command (pre-fix)
    r = subprocess.run(meta + [str(tmp_path / "pre.mp4")], capture_output=True, text=True)
    assert r.returncode != 0 and "Conversion failed" in r.stderr

    # 3) the fixer, as it rides the pipeline
    from suravidl_engine.extract import _attach_stream_copy_fix
    import yt_dlp
    ydl = yt_dlp.YoutubeDL({"quiet": True, "ffmpeg_location": FFMPEG})
    _attach_stream_copy_fix(ydl)
    pp = [c for c in ydl._pps["post_process"] if isinstance(c, StreamCopyFixPP)][-1]
    pp.run({"filepath": str(broken)})

    kept = [(s.get("codec_type"), s.get("codec_name")) for s in json.loads(subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", str(broken)],
        capture_output=True, text=True, check=True).stdout)["streams"]]
    assert ("audio", "mp3") not in kept and ("audio", "aac") in kept

    # 4) and the command that died now succeeds
    r = subprocess.run(meta + [str(tmp_path / "post.mp4")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    assert (tmp_path / "post.mp4").stat().st_size > 0


# --- the two UI asks of the same round ---

CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(encoding="utf-8")


def test_the_ytdlp_save_floats_like_settings():
    blk = CSS.split("#panel-ytdlp .foot-row {")[1].split("}")[0]
    assert "position: sticky" in blk and "bottom: 12px" in blk
    assert "backdrop-filter: var(--glass-blur);" in blk
    assert "-webkit-backdrop-filter: var(--glass-blur);" in blk
    assert CSS.count("#panel-ytdlp .foot-row {") >= 2, "the phone block twins it"
