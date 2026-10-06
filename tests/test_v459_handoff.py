"""v0.45.9 "the handoff" — the Windows chain waits for the app to die first.

The report (2026-10-06, setup version): "Restart & Install" quit the app
and installed nothing. The chain blind-waited two seconds, then started
the installer; a still-exiting app has no window for the Restart Manager
to close, Setup's close attempt then "fails", and its Abort/Retry/Ignore
box — which silent mode still shows — waited forever with nobody there.
The chain now waits for the app's pid to vanish (bounded at 90 s),
suppresses any such box, and records each step to a log file.
"""
import base64
from pathlib import Path

from suravidl_engine.__main__ import _windows_apply_command

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()


def _script(argv):
    return base64.b64decode(argv[-1]).decode("utf-16-le")


def test_the_chain_waits_for_the_pid_before_the_installer():
    s = _script(_windows_apply_command(r"C:\Temp\setup.exe", None, pid=4321,
                                       log_path=r"C:\Temp\up.log"))
    assert "Get-Process -Id 4321" in s
    assert "$deadline" in s and "AddSeconds(90)" in s
    assert (s.index("Get-Process -Id 4321")
            < s.index("Start-Process -FilePath 'C:\\Temp\\setup.exe'"))


def test_no_prompt_can_hang_unattended():
    s = _script(_windows_apply_command(r"C:\Temp\setup.exe", None, pid=1,
                                       log_path=r"C:\Temp\up.log"))
    assert "/SUPPRESSMSGBOXES" in s
    assert "/SILENT" in s


def test_the_trail_records_each_step_in_order():
    s = _script(_windows_apply_command(r"C:\Temp\setup.exe", r"C:\Temp\app.exe",
                                       pid=1, log_path=r"C:\Temp\up.log"))
    assert "Out-File -Append" in s
    assert "app gone at" in s
    assert "installer exit: $($p.ExitCode)" in s
    assert "relaunched" in s
    assert (s.index("app gone at")
            < s.index("installer exit:")
            < s.index("Start-Process -FilePath 'C:\\Temp\\app.exe'"))
    # the exit code comes from -PassThru — a wait that cannot read it is blind
    assert "-Wait -PassThru" in s


def test_the_fallback_wait_when_no_pid_was_handed_over():
    s = _script(_windows_apply_command(r"C:\Temp\setup.exe", None,
                                       log_path=r"C:\Temp\up.log"))
    assert "Start-Sleep -Seconds 2" in s
    assert "Get-Process" not in s


def test_the_applier_hands_over_its_own_pid():
    assert "_windows_apply_command(staged, _installed_exe()," in MAIN
    assert "os.getpid()" in MAIN


def test_the_chain_spawn_is_not_detached():
    """Probed on a real Windows machine (2026-10-06, six spawn modes side
    by side): DETACHED_PROCESS PowerShell starts, exits 0, and executes
    NOTHING — that was the genuine "Restart & Install only quits" bug.
    CREATE_NO_WINDOW alone runs the chain and still outlives the app."""
    src = (ROOT / "src/suravidl_engine/__main__.py").read_text(encoding="utf-8")
    i = src.index("cmd = _windows_apply_command(staged")
    seg = src[i:i + 1200]
    assert "creationflags=_CREATE_NO_WINDOW" in seg
    assert "0x00000008" not in seg and "0x08000000" not in seg
    smoke = (ROOT / "scripts/smoke_windows_update.py").read_text(encoding="utf-8")
    assert "creationflags=_CREATE_NO_WINDOW" in smoke
    assert "0x00000008" not in smoke
    # the chain's Out-File writes UTF-16LE; the reader must sniff it
    assert 'decode("utf-16"' in smoke
