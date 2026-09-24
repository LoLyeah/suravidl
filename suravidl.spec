# PyInstaller spec for suravidl desktop binaries.
# Usage: pyinstaller suravidl.spec  (run from repo root)
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
SEP = ";" if sys.platform == "win32" else ":"

a = Analysis(
    ["scripts/entry.py"],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "src" / "suravidl_engine" / "web"),
            "suravidl_engine/web")],
    hiddenimports=["suravidl_engine.__main__"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="suravidl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=str(ROOT / ("assets/icon.ico" if sys.platform == "win32"
                     else "assets/logo.png")),
)
