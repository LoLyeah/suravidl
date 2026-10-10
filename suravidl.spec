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

try:  # TLS trust: the frozen app carries certifi's CA bundle (its absence on
    # macOS is why the packaged app's update check failed with
    # CERTIFICATE_VERIFY_FAILED — see suravidl_engine/net.py)
    from PyInstaller.utils.hooks import collect_data_files

    _certifi_datas = collect_data_files("certifi")
except Exception:  # noqa: BLE001 - the engine works without it (system store)
    _certifi_datas = []

try:  # yt-dlp's metadata must travel: the v0.43.0 boot compares a staged
    # in-app update against the bundled copy by version, and without the
    # dist-info that comparison falls back to the app-stamp heuristic
    # (see suravidl_engine/ytdlp_update.py)
    from PyInstaller.utils.hooks import copy_metadata

    _ytdlp_meta = copy_metadata("yt-dlp")
except Exception:  # noqa: BLE001 - the fallback still works without it
    _ytdlp_meta = []

a = Analysis(
    ["scripts/entry.py"],
    pathex=[str(ROOT / "src")],
    binaries=_cffi_binaries,
    datas=[(str(ROOT / "src" / "suravidl_engine" / "web"),
            "suravidl_engine/web"),
           (str(ROOT / "src" / "suravidl_engine" / "macos_swap.sh"),
            "suravidl_engine")] + _cffi_datas + _certifi_datas + _ytdlp_meta,
    hiddenimports=["suravidl_engine.__main__", "certifi"] + _webview_hidden + _cffi_hidden,
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
    # A console is for CI logs and terminal launches (kept on
    # mac/linux); the Windows user double-clicking the app gets a GUI
    # process instead — and every child it spawns is flat quiet.
    console=(sys.platform != "win32"),
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
            "CFBundleShortVersionString": "0.45.32",
            "CFBundleName": "suravidl",
            "NSHighResolutionCapable": True,
        },
    )
