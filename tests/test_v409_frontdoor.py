"""v0.40.9 "the front door" — one flag puts suravidl in the menu.

The AppImage and the Windows exe run from wherever the user put them, so
they show up in no menu at all. --install-desktop writes a launcher entry
(Linux, XDG dirs) or a Start Menu shortcut (Windows, via the PowerShell
every install of Windows has) that points back at them; --uninstall-desktop
takes it back out. Nothing outside the user's own folders, no sudo — and
installing must never boot the engine.
"""
import sys
from pathlib import Path

from suravidl_engine import __main__ as shell

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()


def test_the_desktop_entry_points_home():
    text = shell.desktop_entry_text("/opt/Apps/suravidl.AppImage")
    assert "[Desktop Entry]" in text
    assert "Name=suravidl" in text
    assert 'Exec="/opt/Apps/suravidl.AppImage"' in text
    assert "Icon=suravidl" in text
    assert "Terminal=false" in text
    assert text.endswith("\n"), "a desktop file ends with its own newline"


def test_a_source_run_gets_the_module_spelling():
    text = shell.desktop_entry_text("/usr/bin/python3", "-m suravidl_engine")
    assert 'Exec="/usr/bin/python3" -m suravidl_engine' in text


def test_the_appimage_reports_its_own_path(monkeypatch):
    monkeypatch.setenv("APPIMAGE", "/home/u/Apps/suravidl.AppImage")
    target, args = shell.app_launch_paths()
    assert target == "/home/u/Apps/suravidl.AppImage" and args == ""

    monkeypatch.delenv("APPIMAGE")
    target, args = shell.app_launch_paths()
    assert target == sys.executable
    assert args == ("-m suravidl_engine" if not getattr(sys, "frozen", False) else "")


def test_install_and_uninstall_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPIMAGE", "/home/u/Apps/suravidl.AppImage")
    written = shell.install_desktop_entry(home=tmp_path)
    entry = tmp_path / ".local/share/applications/suravidl.desktop"
    assert entry.exists() and entry in written
    assert "suravidl.AppImage" in entry.read_text()
    icon = tmp_path / ".local/share/icons/hicolor/128x128/apps/suravidl.png"
    assert icon.exists() and icon in written, "the tile rides along"

    removed = shell.remove_desktop_entry(home=tmp_path)
    assert entry in removed and icon in removed
    assert not entry.exists() and not icon.exists()
    assert shell.remove_desktop_entry(home=tmp_path) == [], "removing twice is fine"


def test_the_windows_shortcut_command_quotes_relentlessly():
    cmd = shell.windows_shortcut_command(
        Path(r"X:\Users\o'brien\Start Menu\suravidl.lnk"),
        r"C:\Apps\suravidl.exe")
    assert cmd[0] == "powershell" and "-Command" in cmd
    ps = cmd[-1]
    assert "CreateShortcut('X:\\Users\\o''brien\\Start Menu\\suravidl.lnk')" in ps
    assert "$s.TargetPath = 'C:\\Apps\\suravidl.exe'" in ps
    assert "$s.IconLocation = 'C:\\Apps\\suravidl.exe,0'" in ps
    assert ps.endswith("$s.Save()")


def test_the_start_menu_sits_where_windows_says(tmp_path):
    d = shell.start_menu_programs_dir(tmp_path)
    assert d == tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def test_the_cli_never_boots_the_engine(monkeypatch, capsys, tmp_path):
    calls = []
    monkeypatch.setattr(shell, "install_desktop_entry",
                        lambda *a, **k: calls.append("i") or [tmp_path / "x.desktop"])
    monkeypatch.setattr(shell, "remove_desktop_entry",
                        lambda *a, **k: calls.append("r") or [])
    monkeypatch.setattr(shell, "_refresh_desktop_db", lambda *a, **k: None)

    assert shell._desktop_install_cli(uninstall=False) == 0
    assert calls == ["i"]
    assert "applications menu" in capsys.readouterr().out

    assert shell._desktop_install_cli(uninstall=True) == 0
    assert calls == ["i", "r"]


def test_macos_says_where_the_menu_comes_from(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert shell._desktop_install_cli(uninstall=False) == 0
    assert "Applications" in capsys.readouterr().out


def test_the_flags_are_wired_and_early():
    assert 'p.add_argument("--install-desktop"' in MAIN
    assert 'p.add_argument("--uninstall-desktop"' in MAIN
    assert "def _refresh_desktop_db(" in MAIN
    i_main = MAIN.index("def main() -> None:")   # self_test tokenizes too
    i_flag = MAIN.index("_desktop_install_cli(uninstall=args.uninstall_desktop)", i_main)
    i_boot = MAIN.index("token = load_or_create_token()", i_main)
    assert i_flag < i_boot, "installing a launcher must not boot the engine"
