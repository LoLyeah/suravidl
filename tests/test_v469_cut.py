"""v0.46.9 "the cut" — the marks keep their promise, locally.

Critique round 3's batch:
P0 — a section re-download of an existing file fetched NOTHING and was
reported as success (yt-dlp skips the existing output, exits 0). The
skip is now detected (requested_downloads[0].__real_download is False,
verified live) and answered honestly: ranged skips fail with a sentence
that names the fix; plain skips carry a caveat note.
P1 — markClip's `const t` shadowed the i18n helper: every mark threw
after the write (dead toast). The player's head now shows the marks
("clip 0:12–0:48"), the seconds truncate for the in and ceil for the
out, and the option chip refreshes.
P1 — the better flow: "Cut this take" trims the file you are watching
with ffmpeg (local, -c copy, no network) and files the result as its
own completed take.
P2 — the bins card's second line is now size · filed-time (the queue
row's own pattern); the filename was the title's echo, cut at 34% by
the 236px rail. The full path stays in the tooltip.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(
    encoding="utf-8")
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")
JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text(
    encoding="utf-8")
API = (ROOT / "src" / "suravidl_engine" / "api.py").read_text(
    encoding="utf-8")

import sys
sys.path.insert(0, str(ROOT / "src"))
from suravidl_engine import cut  # noqa: E402


# ── the engine: parsing, naming, the cut itself ──

def test_time_readings_parse():
    assert cut.parse_time("1:23") == 83.0
    assert cut.parse_time("0:12:34") == 754.0
    assert cut.parse_time("95") == 95.0
    assert cut.parse_time(" 2:05 ") == 125.0
    assert cut.parse_time("") is None
    assert cut.parse_time("abc") is None
    assert cut.parse_time("1:2:3:4") is None


def test_the_label_and_the_filename_speak_the_same_range():
    assert cut.clock(83) == "1:23"
    assert cut.clock(3723) == "1:02:03"
    assert cut.clip_label(12, 48) == "0:12\u20130:48"
    assert cut.clip_name(Path("/x/trailer.mp4"), 12, 48) == (
        "trailer \u2014 clip 0.12\u20130.48.mp4")


@pytest.mark.skipif(not cut.ffmpeg_exe(), reason="no ffmpeg on this box")
def test_the_cut_trims_for_real(tmp_path):
    src = tmp_path / "probe.mp4"
    subprocess.run(
        [cut.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=4:size=128x72:rate=10",
         "-pix_fmt", "yuv420p", str(src)],
        check=True, capture_output=True, timeout=120)
    out = cut.cut_file(src, 1.0, 3.0, tmp_path)
    assert out.exists() and out.stat().st_size > 0
    assert out.name == "probe \u2014 clip 0.01\u20130.03.mp4"
    probe = subprocess.run(
        [cut.ffmpeg_exe(), "-hide_banner", "-i", str(out)],
        capture_output=True, text=True, timeout=60)
    assert "Duration" in probe.stderr, "the cut must be a real file"
    # a second identical cut counts up instead of overwriting
    out2 = cut.cut_file(src, 1.0, 3.0, tmp_path)
    assert out2.name == "probe \u2014 clip 0.01\u20130.03 (2).mp4"


def test_the_skip_is_detected_and_answered_honestly():
    # the P0: the skip signal, verified live against yt-dlp
    # (v0.46.17: the namesake escape reads the same signal inside
    # _escape_namesake — scope the pin to the _execute body, or it lands
    # on the helper's text instead of the check it means)
    exe = JOBS.split("def _execute(")[1]
    assert 'req.get("__real_download") is False' in exe
    assert 'if opts.get("download_ranges"):' in exe.split(
        '__real_download") is False')[1][:400]
    assert "nothing was fetched" in JOBS
    assert "already on disk — nothing was fetched" in JOBS


def test_a_local_take_files_like_any_other():
    assert "def add_take(self, *, title: str, url: str, filepath: str," in JOBS
    assert '"status": "completed",' in JOBS.split("def add_take")[1][:900]


def test_the_route_cuts_inside_the_folder_only():
    seg = API.split('@app.post("/jobs/{job_id}/cut")')[1]
    seg = seg.split("@app.get(\"/follows\")")[0]
    assert "mgr._require_inside(src, job)" in seg, \
        "the job's own folder — a take from before a folder change still " \
        "cuts (v0.46.10 audit A/F3)"
    assert "parse_time(body.start)" in seg and "parse_time(body.end)" in seg
    assert "the out must come after the in" in seg
    assert "mgr.add_take(" in seg


# ── the player: the shadow fix, the reading, the cut button ──

def test_the_marks_no_longer_shadow_the_helper():
    seg = APP[APP.index("function markClip("):]
    seg = seg[:seg.index("function renderMarkSay")]
    assert "const t = node.currentTime" not in seg, "the shadow is retired"
    assert "const at = node.currentTime" in seg
    assert "Math.floor(at)" in seg and "Math.ceil(at)" in seg, (
        "in truncates, out ceils — a mark never takes a frame")
    assert "renderOvCount()" in seg and "renderMarkSay()" in seg
    assert 't("clip starts at {v}", { v: v })' in seg


def test_the_player_shows_its_marks():
    assert 'id="markSay"' in HTML
    seg = APP[APP.index("function renderMarkSay()"):]
    seg = seg[:seg.index("async function cutTake")]
    assert 't("clip {a}–{b}", { a: a, b: b })' in seg
    assert 't("in {a} — mark the out", { a: a })' in seg
    assert ".marksay:empty { display: none; }" in CSS


def test_the_cut_button_cuts_the_take_on_screen():
    assert 'id="cutTake"' in HTML
    assert "$(\"cutTake\").onclick = cutTake;" in APP
    assert "let PLAY_JOB = null;" in APP
    seg = APP[APP.index("async function cutTake()"):]
    seg = seg[:seg.index("function initPlayer")]
    assert "`/jobs/${encodeURIComponent(job.id)}/cut`" in seg
    assert 't("mark both ends first — in and out")' in seg
    assert "refreshJobs()" in seg
    # the whole openPlayerSrc body (a bounded window; it ends well inside)
    seg2 = APP[APP.index("function openPlayerSrc("):][:3200]
    assert 'PLAY_JOB && PLAY_JOB.filepath' in seg2, (
        "the cut shows only for a playable take with a file")
    assert "if (node.focus) node.focus();" in seg2, (
        "focus the take, not Mark in (Enter used to write 0:00)")
    assert "PLAY_JOB = null;" in APP, "closePlayer releases the take"


def test_the_bins_card_carries_what_differs():
    seg = APP[APP.index("function renderBins("):]
    seg = seg[:seg.index("async function refreshJobs")]
    assert "humanBytes(j.size_bytes)" in seg
    assert "humanSince(Date.parse(j.completed_at))" in seg
    assert 'bits.join(" · ")' in seg
    assert "baseName(j.filepath)" not in seg, (
        "the filename was the title's echo — it lives in the tooltip now")
    assert "font-size: 12.5px;" in CSS[CSS.index(".bin-meta {"):
                                      CSS.index(".bin-meta {") + 220]


def test_the_cut_speaks_indonesian_too():
    for pair in ('"Cut this take": "Potong take ini"',
                 '"cut filed — {name}": "potongan tersimpan — {name}"'):
        assert pair in APP, pair
