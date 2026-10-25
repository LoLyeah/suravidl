"""the cut — trim a filed take locally (v0.46.9).

The player's marks used to point at a re-download that could not work:
the output name already existed, yt-dlp skipped it, exited 0, and the
job claimed a success it never delivered (critique round 3's P0). The
honest completion is local — the file is already here; ffmpeg copies
the range out; the result files as its own take.

Laws:
- the cut is LOCAL — no network, ever;
- keyframes are the truth — a stream copy snaps to the nearest ones,
  and the take's note says so;
- a cut never overwrites: the name carries the range, collisions count.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# A macOS app started from Finder never inherits the shell's PATH, so a
# Homebrew ffmpeg is invisible to shutil.which() even though the user has it
# (owner's report, 2026-10-24: "the last step needs ffmpeg" on a Mac with
# ffmpeg installed). These are the places a package manager puts it.
_MAC_FFMPEG = ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
               "/opt/local/bin/ffmpeg")

# "1:23", "0:12", "1:02:03", or a bare "95" (seconds). A bare number is
# seconds, never minutes — the fields' placeholders say "start 1:30".
_TIME_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2}(?:\.\d+)?)$")


def ffmpeg_exe() -> str:
    """The ffmpeg the engine itself uses.

    Android passes its jniLib path in via SURAVIDL_FFMPEG; desktop builds
    take the system one — from PATH, then (on macOS) from the package
    managers' own prefixes, because a Finder-launched app has no PATH.
    """
    env = os.environ.get("SURAVIDL_FFMPEG", "").strip()
    if env:
        return env
    # the copy Settings downloaded (v0.47.13): small installers, one click
    try:
        from . import tools

        own = tools.ffmpeg_path()
        if own.is_file() and os.access(own, os.X_OK):
            return str(own)
    except Exception:  # noqa: BLE001 - a missing tools module is not fatal
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    if sys.platform == "darwin":
        for candidate in _MAC_FFMPEG:
            try:
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    return candidate
            except OSError:
                continue
    return ""


def parse_time(s) -> float | None:
    """A clock reading to seconds; None when it is not one."""
    s = str(s or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    m = _TIME_RE.match(s)
    if not m:
        return None
    h, mm, ss = m.groups()
    return int(h or 0) * 3600 + int(mm) * 60 + float(ss)


def clock(sec: float) -> str:
    s = int(sec)
    h, r = divmod(s, 3600)
    m, s2 = divmod(r, 60)
    return f"{h}:{m:02d}:{s2:02d}" if h else f"{m}:{s2:02d}"


def clip_label(start: float, end: float) -> str:
    """The range as one reading: '0:12–0:48' (en dash, house style)."""
    return f"{clock(start)}\u2013{clock(end)}"


def clip_name(src: Path, start: float, end: float) -> str:
    """'trailer — clip 0.12–0.48.mp4' — colons are illegal on Windows,
    so the filename's clock dots where the label colons."""
    a = clock(start).replace(":", ".")
    b = clock(end).replace(":", ".")
    return f"{src.stem} \u2014 clip {a}\u2013{b}{src.suffix}"


def cut_file(src: Path, start: float, end: float, out_dir: Path) -> Path:
    """Copy [start, end] out of src into out_dir. Returns the new file.

    Raises RuntimeError with a user-readable sentence on any failure —
    the route turns it into a 400 the toast can show."""
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg is not available — the cut needs it")
    out = out_dir / clip_name(src, start, end)
    n = 2
    while out.exists():
        out = out_dir / f"{Path(clip_name(src, start, end)).stem} ({n}){src.suffix}"
        n += 1
    argv = [exe, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start), "-to", str(end), "-i", str(src),
            "-c", "copy", "-map_metadata", "0",
            "-avoid_negative_ts", "make_zero", str(out)]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        out.unlink(missing_ok=True)
        raise RuntimeError("the cut took too long and was stopped") from None
    if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        why = (p.stderr or "").strip().splitlines()
        raise RuntimeError("the cut failed: "
                           + (why[-1] if why else "ffmpeg said no"))
    return out
