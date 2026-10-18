"""v0.47.8 "the path" — the applier spawns PowerShell absolutely.

Field report (2026-10-18): Restart & Install failed three times with
`[WinError 2] The system cannot find the file specified` while the update
was reported "downloaded and verified". The applier spawned a bare
"powershell.exe", which Windows resolves through PATH — and the windowed
build's PATH is not always the shell's. The system's own path cannot be
missing; the bare name stays only as a last resort, and a failed spawn now
records the path it tried and the PATH it had.
"""
import base64
from pathlib import Path

from suravidl_engine import __main__ as shell

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()


def test_an_existing_system_powershell_wins(monkeypatch, tmp_path):
    fake = (tmp_path / "System32" / "WindowsPowerShell" / "v1.0"
            / "powershell.exe")
    fake.parent.mkdir(parents=True)
    fake.write_bytes(b"MZ")
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert shell._powershell_exe() == str(fake)
    cmd = shell._windows_apply_command("C:/tmp/setup.exe",
                                       "C:/app/suravidl.exe", 123)
    assert cmd[0] == str(fake)
    assert cmd[1:4] == ["-NoProfile", "-NonInteractive", "-EncodedCommand"]


def test_a_missing_system_path_falls_back_to_the_bare_name(monkeypatch, tmp_path):
    monkeypatch.setenv("SystemRoot", str(tmp_path / "nothing-here"))
    assert shell._powershell_exe() == "powershell.exe"


def test_the_encoded_script_survives_hostile_paths():
    """One opaque ASCII argument: an `&` or a quote cannot re-open the line."""
    cmd = shell._windows_apply_command("C:/Users/a&b/it's here/setup.exe",
                                       None, None)
    script = base64.b64decode(cmd[-1]).decode("utf-16-le")
    assert "it''s here" in script, "PowerShell single-quote escaping"
    assert "$ErrorActionPreference" in script
    assert "/SUPPRESSMSGBOXES" in script


def test_a_failed_spawn_records_what_it_tried():
    assert "PATH:" in SRC
    assert "powershell: {cmd[0]!r}" in SRC
    assert "(exists={Path(cmd[0]).is_file()})" in SRC
