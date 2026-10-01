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

try:  # impersonation: curl_cffi and its libcurl-impersonate travel along when
    # installed at build time (the release workflow installs it, and its smoke
    # test asserts --selftest can still construct an impersonating session)
    from PyInstaller.utils.hooks import collect_all

    _cffi_datas, _cffi_binaries, _cffi_hidden = collect_all("curl_cffi")
except Exception:  # noqa: BLE001 - the engine works without it; Android too
    _cffi_datas, _cffi_binaries, _cffi_hidden = [], [], []

a = Analysis(
    ["scripts/entry.py"],
    pathex=[str(ROOT / "src")],
    binaries=_cffi_binaries,
    datas=[(str(ROOT / "src" / "suravidl_engine" / "web"),
            "suravidl_engine/web")] + _cffi_datas,
    hiddenimports=["suravidl_engine.__main__"] + _webview_hidden + _cffi_hidden,
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
            "CFBundleShortVersionString": "0.38.5",
            "CFBundleName": "suravidl",
            "NSHighResolutionCapable": True,
        },
    )
