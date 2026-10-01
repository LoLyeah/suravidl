"""v0.39.1 — a quiet window on Windows.

The desktop build opened a console (cmd) window beside the app, and once
the app itself is a GUI process any console child it spawns — ffmpeg
during a merge, pip during a yt-dlp update — flashes a black window. A
windowed app also gets ``sys.stdout = None``, which would silently swallow
the boot trail; the log file is the answer to that.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_windows_binary_is_a_gui_app_on_purpose():
    spec = (ROOT / "suravidl.spec").read_text()
    # A console is wanted in CI logs and terminal launches (mac/linux keep
    # it), but the Windows user double-clicking an app must not get cmd.
    assert "console=(sys.platform != \"win32\")" in spec


def test_every_spawned_child_gets_the_no_console_flag():
    from suravidl_engine import __main__ as entry

    seen = {}

    def fake_init(self, *args, **kwargs):
        seen.update(kwargs)

    wrapped = entry._hidden_popen_init(fake_init)
    wrapped(object(), ["whatever.exe"], creationflags=0x00000008)  # a pre-existing flag survives
    assert seen["creationflags"] & entry._CREATE_NO_WINDOW
    assert seen["creationflags"] & 0x00000008  # CREATE_NEW_PROCESS_GROUP kept


def test_the_console_hider_is_idempotent_and_windows_only(monkeypatch):
    from suravidl_engine import __main__ as entry

    before = subprocess.Popen.__init__
    entry._hide_child_consoles()
    if sys.platform == "win32":  # pragma: no cover - CI parity
        assert subprocess.Popen.__init__ is not before
    else:
        # off Windows there is no window to hide: the spawner is untouched
        assert subprocess.Popen.__init__ is before
        monkeypatch.setattr(entry, "_CONSOLES_HIDDEN", [True])
        entry._hide_child_consoles()  # a second call is a no-op, not a stack
    monkeypatch.setattr(entry, "_CONSOLES_HIDDEN", [])


def test_a_windowed_build_still_writes_a_log(tmp_path, monkeypatch):
    from suravidl_engine import __main__ as entry

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    log = tmp_path / "app.log"
    entry._ensure_log_targets(log)
    assert sys.stdout is not None and sys.stderr is not None
    sys.stdout.write("boot trail\n")
    sys.stdout.flush()
    assert "boot trail" in log.read_text()
    monkeypatch.undo()

    # a log that grows for years is a journal, not a boot trail
    log.write_text("x" * 1_100_000)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    entry._ensure_log_targets(log)
    sys.stdout.write("fresh boot\n")
    sys.stdout.flush()
    assert log.stat().st_size < 100_000
    monkeypatch.undo()
