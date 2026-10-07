"""v0.45.14 "the oracle" — the stream verdict comes from ffmpeg, never ffprobe.

Field report (2026-10-07, Android): the merge fix behaves differently on
the phone than on every desktop test — the v0.45.13 build carried the
fix, and the device log still showed no fix action at all. Root cause,
proven by rebuilding the app's exact minimal ffprobe from the same
configure flags: the probe-only binary ships with no decoders, and it
reports `channels: 0` / no sample rate for EVERY audio stream — the
junk headerless one and the healthy AAC alike. The desktop ffprobe is a
full build and reads them apart, which is why the lie hid locally.

The verdict now comes from the same ffmpeg that will do the copy: its
input dump names the broken stream outright ("Could not find codec
parameters for stream 0", "0 channels"), and it is the same binary
whose metadata pass dies, so it cannot disagree with itself.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(encoding="utf-8")
CLS = SRC[SRC.index("class StreamCopyFixPP"):SRC.index("def _attach_stream_copy_fix")]

sys.path.insert(0, str(ROOT / "src"))
from suravidl_engine.extract import StreamCopyFixPP  # noqa: E402


def test_the_class_never_asks_ffprobe():
    assert "probe_executable" not in CLS and "_usable" not in CLS
    assert "probe-only binary" in CLS, "the docstring records WHY"


def test_the_parser_reads_the_field_dump():
    dump = (
        "[mp3 @ 0xb400] Header missing\n"
        "[in#0/mpegts @ 0xb4] Could not find codec parameters for stream 0 "
        "(Audio: mp3, 0 channels, s16p): unspecified frame size\n"
        "  Stream #0:0[0x100]: Audio: mp3, 0 channels, s16p, start 0.167667\n"
        "  Stream #0:1[0x101]: Audio: aac (LC), 44100 Hz, stereo, fltp, 92 kb/s\n"
    )
    streams, bad = StreamCopyFixPP._parse_stream_dump(dump)
    assert streams == {0: "Audio", 1: "Audio"}
    assert bad == {0}, "the headerless mp3 is flagged; the healthy AAC is not"


def test_a_healthy_file_pays_nothing():
    streams, bad = StreamCopyFixPP._parse_stream_dump(
        "  Stream #0:0[0x100]: Video: h264 (High), yuv420p, 1920x1080, 30 fps\n"
        "  Stream #0:1[0x101]: Audio: aac (LC), 44100 Hz, stereo, fltp\n")
    assert streams == {0: "Video", 1: "Audio"} and bad == set()


def test_data_streams_stay_out_of_the_remux():
    dump = ("  Stream #0:0[0x100]: Video: h264 (High), yuv420p, 1920x1080\n"
            "  Stream #0:1[0x101]: Audio: mp3, 0 channels, s16p\n"
            "  Stream #0:2[0x102]: Data: bin_data\n")
    streams, bad = StreamCopyFixPP._parse_stream_dump(dump)
    keep = [i for i, kind in sorted(streams.items())
            if i not in bad and kind in ("Video", "Audio", "Subtitle")]
    assert keep == [0]


def test_a_remux_that_fails_says_so():
    assert "could not apply" in CLS, "the silent-skip hole is closed"
