# PyInstaller spec for suravidl desktop binaries.
# Usage: pyinstaller suravidl.spec  (run from repo root)
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
SEP = ";" if sys.platform == "win32" else ":"

try:  # bundle pywebview's platform backends when the package is installed
    from PyInstaller.utils.hooks import collect_submodules

    _webview_hidden = collect_submodules("webview")
except Exception:  # noqa: BLE001 - pywebview is optional
    _webview_hidden = []

a = Analysis(
    ["scripts/entry.py"],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "src" / "suravidl_engine" / "web"),
            "suravidl_engine/web")],
    hiddenimports=["suravidl_engine.__main__"] + _webview_hidden,
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

# macOS: wrap the one-file binary in a real .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="suravidl.app",
        icon=str(ROOT / "assets/icon.icns"),
        bundle_identifier="com.suravidl.app",
        info_plist={
            "CFBundleShortVersionString": "0.8.0",
            "CFBundleName": "suravidl",
            "NSHighResolutionCapable": True,
        },
    )
