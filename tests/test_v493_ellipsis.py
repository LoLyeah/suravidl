"""v0.49.3 "the ellipsis" — the path fields stop cutting a token in half.

The owner asked why the Download folder field looked different: it wears the
machine voice (mono) because it holds a machine string, a rule the design
system records and `test_audit4_fixes` enforces. The real defect beside that
question was the clipping — a long path was sliced mid-token with no ellipsis
and no way to read the whole value.

Face untouched; the three machine fields now ellipsise and carry their full
value in the title.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.49.3" and e["title"].lower() == "the ellipsis"
               for e in ENTRIES)


def test_the_machine_fields_ellipsise():
    assert "#setDir, #setRateLimit, #setProxy { text-overflow: ellipsis; }" in CSS


def test_the_whole_path_is_reachable():
    assert '$("setDir").title = s.download_dir || "";' in APP
    assert '$("setDir").title = path;' in APP


def test_the_face_rule_is_untouched():
    """The mono voice on machine inputs is a recorded system rule."""
    HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()
    for i in ("setDir", "setRateLimit", "setProxy"):
        assert f'id="{i}" class="mono"' in HTML, i
