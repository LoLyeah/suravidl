"""v0.45.15 "the keeper" — the fixer may only remove what it can name.

Field report (2026-10-07, the same Android session): "It works, but the
resulting file is broken — it's downloaded around 1GB but after merging
it's only 60mb." The v0.45.14 remux built a POSITIVE keep-list from the
parsed dump and mapped only what it listed: any stream line the regex
failed to read silently became "a stream that does not exist", and the
output lost it — a 90-minute video came out as its audio track alone
(~62 MB at the stream's 92 kb/s — matching the reported size exactly).

v0.45.15 inverts the burden of proof:

- the remux maps `-map 0` (EVERYTHING ffmpeg sees) minus only the
  explicitly named drops — a stream the parse never saw is KEPT, never
  silently lost; the parse can only decide what to REMOVE;
- a parse that comes up short of the dump's `Stream #0:N` mentions
  (language/pid tag forms the regex may not know) refuses to act and
  says so — no silent skips, no partial reads driving removals;
- the drop line names its victims ("1:Audio/mp3"), so the next log can
  never be ambiguous.
"""

import re
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(encoding="utf-8")
CLS = SRC[SRC.index("class StreamCopyFixPP"):SRC.index("def _attach_stream_copy_fix")]

sys.path.insert(0, str(ROOT / "src"))
from suravidl_engine.extract import StreamCopyFixPP  # noqa: E402


def test_a_language_tag_does_not_hide_a_stream():
    """`Stream #0:0[0x100](und): Video: ...` — the (lang) form must read."""
    dump = ("  Stream #0:0[0x100](und): Video: h264 (High), yuv420p, 1920x1080\n"
            "  Stream #0:1[0x101]: Audio: mp3, 0 channels, s16p\n")
    streams, bad = StreamCopyFixPP._parse_stream_dump(dump)
    assert streams == {0: ("Video", "h264"), 1: ("Audio", "mp3")}
    assert bad == {1}


def test_a_partial_read_is_detected():
    dump = ("  Stream #0:0[0x100]: Video: h264 (High), yuv420p, 1920x1080\n"
            "  Stream #0:3[0x103] Video: h264\n")   # the unreadable form
    streams, _ = StreamCopyFixPP._parse_stream_dump(dump)
    raw = len(re.findall(r"Stream #0:\d+", dump))
    assert raw == 2 and len(streams) == 1, "the shortfall must be visible"


def test_the_remux_removes_by_negative_mapping():
    """map-all-minus-drop: an unseen stream can never be silently lost."""
    assert '"-map", "0"' in CLS
    assert 'f"-0:{idx}"' in CLS
    assert '"-map", f"0:{' not in CLS, "the positive keep-list must be gone"


def test_an_unreadable_dump_refuses_to_act(tmp_path):
    pp = StreamCopyFixPP.__new__(StreamCopyFixPP)
    said = []
    pp._downloader = types.SimpleNamespace(
        report_warning=lambda m, **k: said.append(str(m)),
        to_screen=lambda *a, **k: None, params={})
    f = tmp_path / "x.mp4"
    f.write_bytes(b"x")
    pp._streams_by_ffmpeg = lambda path: None
    pp._remux = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not remux on an unreadable dump"))
    assert pp.fix_file(str(f)) is False
    assert any("could not read" in s for s in said), "the bail must be loud"


def test_the_fix_file_drops_by_name_not_by_keep():
    assert "drop = sorted(bad |" in CLS
    assert "(1:Audio/mp3)" not in CLS  # nothing hardcoded
    assert 'f"before the metadata pass ({names})"' in CLS
