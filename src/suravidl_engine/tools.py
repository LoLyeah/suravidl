"""Tools the engine can fetch for itself (v0.47.13 "the tool").

ffmpeg is not bundled with the desktop builds: the installers stay small,
and a user may already have one. But the core path — best video + best
audio — cannot finish without it, so Settings offers a one-click download
of a static build into `~/.suravidl/tools`.

The binaries come from the `ffmpeg-static` GitHub release, pinned by
sha256 in two places: the archive that is downloaded AND the binary that
comes out of it. Nothing is ever executed before both match.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import platform as _platform
import stat
import sys
import threading
import time
import urllib.request
from pathlib import Path

VERSION = "b6.1.1"
BASE = ("https://github.com/eugeneware/ffmpeg-static/releases/download/"
        f"{VERSION}")

# (sys.platform, machine) -> (asset stem, sha256 of the .gz, sha256 of the binary)
TOOLS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("darwin", "arm64"): (
        "ffmpeg-darwin-arm64",
        "8923876afa8db5585022d7860ec7e589af192f441c56793971276d450ed3bbfa",
        "a90e3db6a3fd35f6074b013f948b1aa45b31c6375489d39e572bea3f18336584"),
    ("darwin", "x64"): (
        "ffmpeg-darwin-x64",
        "929b375c1182d956c51f7ac25e0b2b0411fb01f6f407aa15c9758efeb4242106",
        "ebdddc936f61e14049a2d4b549a412b8a40deeff6540e58a9f2a2da9e6b18894"),
    ("linux", "x64"): (
        "ffmpeg-linux-x64",
        "bfe8a8fc511530457b528c48d77b5737527b504a3797a9bc4866aeca69c2dffa",
        "e7e7fb30477f717e6f55f9180a70386c62677ef8a4d4d1a5d948f4098aa3eb99"),
    ("linux", "arm64"): (
        "ffmpeg-linux-arm64",
        "754a678672298bc68156adff58aa7385a592c2b30b1d0ae8750c45c915c4bac0",
        "6bb182d0d75d23028db82e9e4f723ca69b853d055698486e6984ddb2c06fb8ce"),
    ("win32", "x64"): (
        "ffmpeg-win32-x64",
        "8883a3dffbd0a16cf4ef95206ea05283f78908dbfb118f73c83f4951dcc06d77",
        "04e1307997530f9cf2fe35cba2ca7e8875ca91da02f89d6c7243df819c94ad00"),
}

_LOCK = threading.Lock()
_STATE: dict = {"state": "idle", "pct": 0, "error": None}


def tools_dir() -> Path:
    """Where the app keeps what it fetched for itself (Settings can remove)."""
    override = os.environ.get("SURAVIDL_TOOLS_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".suravidl" / "tools"


def platform_key() -> str:
    """`darwin-arm64`, `linux-x64`, `win32-x64` … — the manifest's key."""
    plat = sys.platform
    if plat == "win32":
        plat = "win32"
    machine = (_platform.machine() or "").lower()
    arch = {"arm64": "arm64", "aarch64": "arm64",
            "x86_64": "x64", "amd64": "x64"}.get(machine, machine or "x64")
    return f"{plat}-{arch}"


def entry() -> tuple[str, str, str] | None:
    return TOOLS.get((platform_key().split("-")[0], platform_key().split("-")[1]))


def ffmpeg_path() -> Path:
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return tools_dir() / name


def status() -> dict:
    """What Settings shows: installed or not, where, and any live download."""
    path = ffmpeg_path()
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    ver = ""
    if exists:
        try:
            ver = (tools_dir() / "ffmpeg.version").read_text(encoding="utf-8").strip()
        except OSError:
            ver = VERSION
    with _LOCK:
        live = dict(_STATE)
    return {
        "platform": platform_key(),
        "supported": entry() is not None,
        "installed": exists,
        "path": str(path),
        "size": size,
        "version": ver,
        "download": live,
    }


def _set(state: str, pct: int = 0, error: str | None = None) -> None:
    with _LOCK:
        _STATE.update({"state": state, "pct": pct, "error": error})


def _download() -> None:
    """Fetch, verify twice, decompress, install. Runs off the request thread."""
    try:
        want = entry()
        if want is None:
            _set("error", 0, f"no ffmpeg build for {platform_key()}")
            return
        stem, gz_sha, bin_sha = want
        target = ffmpeg_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{BASE}/{stem}.gz"
        _set("downloading", 0)
        digest = hashlib.sha256()
        tmp_gz = target.with_name(target.name + ".downloading")
        req = urllib.request.Request(url, headers={"User-Agent": "suravidl"})
        with urllib.request.urlopen(req, timeout=60) as resp, \
                open(tmp_gz, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                got += len(chunk)
                if total:
                    _set("downloading", min(99, int(got * 100 / total)))
        if digest.hexdigest() != gz_sha:
            tmp_gz.unlink(missing_ok=True)
            _set("error", 0, "the download did not match its checksum")
            return
        _set("unpacking", 99)
        plain = hashlib.sha256()
        tmp_bin = target.with_name(target.name + ".unpacking")
        with gzip.open(tmp_gz, "rb") as src, open(tmp_bin, "wb") as out:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                plain.update(chunk)
                out.write(chunk)
        tmp_gz.unlink(missing_ok=True)
        if plain.hexdigest() != bin_sha:
            tmp_bin.unlink(missing_ok=True)
            _set("error", 0, "the unpacked binary did not match its checksum")
            return
        os.chmod(tmp_bin, stat.S_IRWXU)
        os.replace(tmp_bin, target)
        (tools_dir() / "ffmpeg.version").write_text(VERSION + "\n", encoding="utf-8")
        _set("done", 100)
    except Exception as e:  # noqa: BLE001 - the UI shows the reason
        _set("error", 0, f"{type(e).__name__}: {e}")


def start_download() -> dict:
    """Kick a download; the UI polls status() for progress."""
    with _LOCK:
        if _STATE["state"] in ("downloading", "unpacking"):
            return dict(_STATE)
    _set("downloading", 0)
    threading.Thread(target=_download, daemon=True, name="ffmpeg-fetch").start()
    time.sleep(0.05)
    with _LOCK:
        return dict(_STATE)


def remove() -> dict:
    """Delete the app's own copy (a system ffmpeg is never touched)."""
    path = ffmpeg_path()
    removed = False
    for p in (path, tools_dir() / "ffmpeg.version",
              path.with_name(path.name + ".downloading"),
              path.with_name(path.name + ".unpacking")):
        try:
            if p.is_file():
                p.unlink()
                removed = True
        except OSError:
            pass
    _set("idle", 0)
    return {"removed": removed, **status()}
