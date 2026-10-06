"""Smoke the Windows update chain on a real Windows machine (release CI).

Runs the exact PowerShell the app spawns for "Restart & Install" —
_windows_apply_command() — with a stand-in "app" process that outlives
the spawn and dies on its own, then checks the trail: the wait observed
its exit, the installer ran and reported exit code 0, the staged setup
was deleted, and the log recorded all of it. This is the chain the
Windows report (2026-10-06) showed quitting without installing; a runner
is the only place it can be exercised whole.

Usage: python scripts/smoke_windows_update.py <path-to-setup.exe>
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The first CI run of this script (v0.45.9's release) proved the lesson:
# the runner's console encodes cp1252, and the box-drawing characters in
# the final print raised UnicodeEncodeError inside main() AFTER the wait
# loop — so the log we ached for was the one thing never shown. Print
# ASCII, force stdout to UTF-8 anyway (errors=replace never raises), and
# let the wait echo the log as it grows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_log(path: Path, *, sniffer_path=None) -> str:
    """The chain's Out-File on Windows PowerShell 5.1 writes UTF-16LE;
    a plain utf-8 read turns every character into noise and every
    substring check into a false FAIL (lived: 2026-10-06). Sniff by
    BOM/NUL bytes and decode accordingly."""
    if not path.exists():
        return ""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or (raw[:160].count(b"\x00") > 8):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def main() -> int:
    if os.name != "nt":
        print("windows-only smoke — skipped")
        return 0
    if len(sys.argv) < 2:
        print("usage: smoke_windows_update.py <setup.exe>")
        return 2
    src = Path(sys.argv[1])
    if not src.is_file():
        print(f"no setup at {src}")
        return 2

    from suravidl_engine.__main__ import _CREATE_NO_WINDOW, _windows_apply_command

    work = Path(tempfile.mkdtemp(prefix="suravidl-smoke-"))
    setup = work / "suravidl-windows-x64-setup.exe"
    shutil.copy2(src, setup)
    log = work / "update.log"

    # a stand-in app: alive past the spawn, gone a few seconds later —
    # exactly the exit the chain must wait out
    dummy = subprocess.Popen([sys.executable, "-c",
                              "import time; time.sleep(4)"])
    argv = _windows_apply_command(str(setup), None, dummy.pid, str(log))
    # CREATE_NO_WINDOW alone — DETACHED_PROCESS makes the console app a
    # no-op (start, exit 0, run nothing; probed 2026-10-06)
    subprocess.Popen(argv, close_fds=True,
                     creationflags=_CREATE_NO_WINDOW)
    dummy.wait(timeout=60)

    text = ""
    started = time.time()
    deadline = started + 540
    last_beat = started
    while time.time() < deadline:
        text = read_log(log)
        if "installer exit:" in text:
            break
        if time.time() - last_beat > 30:
            last_beat = time.time()
            print(f"[{int(time.time() - started)}s] still waiting; log so far:")
            print(text or "(no log yet)")
        time.sleep(2)
    # the exit line lands one statement before the deletion — give the
    # Remove-Item a short grace, then let the asserts below speak
    if "installer exit:" in text:
        gone_by = time.time() + 10
        while setup.exists() and time.time() < gone_by:
            time.sleep(0.5)

    print("--- update.log ---")
    print(text or "(no log written)")
    ok = True
    if "app gone at" not in text:
        ok = False; print("FAIL: the wait never observed the app's exit")
    if "installer exit: 0" not in text:
        ok = False; print("FAIL: installer exit code was not 0 (see log)")
    if setup.exists():
        ok = False; print("FAIL: the spent setup was not deleted")
    if ok and text.index("app gone at") > text.index("installer exit:"):
        ok = False; print("FAIL: the installer ran before the wait finished")
    print("windows update-chain smoke:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def _sniff_selftest() -> None:
    """One ASCII line, two encodings, same substrings — the reader must
    pass both (utf-16 is what the chain actually writes)."""
    import tempfile as _tf
    line = "app gone at 12:00:01\ninstaller exit: 0\n"
    for enc in ("utf-16", "utf-8"):
        f = Path(_tf.mkdtemp()) / "selftest.log"
        f.write_bytes(line.encode(enc))
        got = read_log(f)
        assert "app gone at" in got and "installer exit: 0" in got, enc
    print("reader selftest ok")


if __name__ == "__main__":
    _sniff_selftest()
    sys.exit(main())
