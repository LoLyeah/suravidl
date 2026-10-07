"""v0.45.16 "the proof" — the mux is the judge; the dump's warnings are not.

Field report (2026-10-07, the same Android session, on v0.45.15): "Still
broken" — the file came out 62.8 MB again, i.e. audio-only, again. The
stream was downloaded fully; the video track vanished silently.

Root cause, reproduced on the desktop with the app's own conditions
(`analyzeduration 0`, small probesize — the exact hint the phone's log
printed): under those values ffmpeg's INPUT DUMP reports `Could not
find codec parameters` on perfectly copyable streams — a healthy video,
even healthy audio. The v0.45.14/.15 fixer treated those warnings as
proof and dropped whatever they named: one false alarm on the video
line = the whole picture gone (1 GB in, 62 MB out). The mux, asked
directly, copies the very same streams fine — proven by experiment.

So the fix no longer trusts any warning as a removal. It climbs an
attempt ladder, each rung judged by the actual mux:

  1. keep everything real (drop only data streams);
  2. drop the flagged AUDIO streams (the genuine killer class);
  3. only if the mux still refuses, also drop the flagged non-audio
     streams — the named, honest last resort for a truly dead video.

Failed attempts die at mux-header time (fast); only the winner copies.
"""

import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from suravidl_engine.extract import StreamCopyFixPP  # noqa: E402

SRC = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(encoding="utf-8")
FFMPEG = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/usr/bin/ffprobe"


def test_the_ladder_keeps_the_video_until_the_mux_refuses_it():
    streams = {0: ("Video", "h264"), 1: ("Audio", "mp3"),
               2: ("Audio", "aac"), 3: ("Data", "bin_data")}
    ladder = StreamCopyFixPP._attempt_ladder(streams, {0, 1})
    assert ladder[0] == ([3], set()), "rung 1: keep every real stream"
    assert ladder[1] == ([1, 3], {1}), "rung 2: the flagged audio only"
    assert ladder[2] == ([0, 1, 3], {0, 1}), "rung 3: the named last resort"


def test_audio_only_flags_need_no_video_rung():
    streams = {0: ("Video", "h264"), 1: ("Audio", "mp3")}
    ladder = StreamCopyFixPP._attempt_ladder(streams, {1})
    assert [drop for drop, _ in ladder] == [[], [1]]
    assert all(0 not in drop for drop, _ in ladder), "video never a rung here"


def _corrupt_mp3_pid(raw: bytes, pid: int) -> bytes:
    """Zero the payload of every mp3-pid packet — no decodable frames left
    (the v4512 field-failure recipe, ported)."""
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


def _broken_fixture(tmp_path):
    """video + healthy aac + headerless mp3 — the field shape."""
    base = tmp_path / "base.ts"
    subprocess.run([
        FFMPEG, "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
        "-map", "0:v", "-map", "1:a", "-map", "2:a",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a:0", "mp3", "-c:a:1", "aac",
        "-f", "mpegts", str(base)], check=True, capture_output=True)
    streams = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", str(base)],
        capture_output=True, text=True, check=True).stdout
    import json as _json
    info = _json.loads(streams)["streams"]
    mp3 = [s for s in info if s.get("codec_name") == "mp3"][0]
    broken = tmp_path / "master.mp4"
    broken.write_bytes(_corrupt_mp3_pid(base.read_bytes(), _pid_of(mp3)))
    return broken


@pytest.mark.skipif(not Path(FFMPEG).exists(), reason="needs ffmpeg")
def test_a_false_alarm_on_the_video_does_not_cost_the_video(tmp_path):
    """The field case end-to-end: dump flags video AND mp3, the mux keeps
    the video anyway — rung 1 fails on the mp3, rung 2 drops only it."""
    import json as _json
    broken = _broken_fixture(tmp_path)

    said = []
    pp = StreamCopyFixPP.__new__(StreamCopyFixPP)
    pp.PP_NAME = "StreamCopyFix"      # __init__ normally sets this
    pp._downloader = types.SimpleNamespace(
        report_warning=lambda m, **k: said.append(str(m)),
        to_screen=lambda m, **k: said.append(str(m)), params={})
    pp._paths = {"ffmpeg": str(FFMPEG)}
    pp._streams_by_ffmpeg = lambda path: (
        {0: ("Video", "h264"), 1: ("Audio", "mp3"), 2: ("Audio", "aac")},
        {0, 1})                       # the false alarm on 0 + the real mp3
    ok = pp.fix_file(str(broken))
    assert ok is True, said
    got = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", str(broken)],
        capture_output=True, text=True, check=True).stdout
    kinds = [(s.get("codec_type"), s.get("codec_name")) for s in _json.loads(got)["streams"]]
    assert ("video", "h264") in kinds, "the video survived the false alarm"
    assert ("audio", "aac") in kinds
    assert not any(c == "mp3" for _, c in kinds)
    assert any("Dropped 1" in s for s in said), said


def test_the_ladder_dedupe_stays_ordered():
    streams = {0: ("Video", "h264"), 1: ("Audio", "mp3")}
    ladder = StreamCopyFixPP._attempt_ladder(streams, {1})
    drops = [tuple(d) for d, _ in ladder]
    assert drops == sorted(drops, key=len), "gentlest first"
