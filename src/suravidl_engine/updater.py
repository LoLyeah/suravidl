""""yt-dlp self-update, and the app's own updates: pip where pip exists, an
honest no where it does not; the release manifest where it can be read."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import yt_dlp

from .net import ssl_context

DEFAULT_REPO = "LoLyeah/suravidl"


def _fetch_latest_release(repo: str) -> dict:
    """Latest release JSON from the GitHub API (token optional for private repos).

    `urlopen` verifies through `ssl_context()`: a packaged macOS app gets no
    system store, and the raw call is exactly what failed there with
    CERTIFICATE_VERIFY_FAILED.
    """
    req = Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "suravidl-update-check"})
    token = os.environ.get("SURAVIDL_GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=5, context=ssl_context()) as r:
        return json.loads(r.read().decode())


def _parse(v: str):
    parts = []
    for chunk in (v or "").lstrip("v").split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    # a "-suffix" marks a prerelease: same numbers, sorted BELOW the
    # release it leads to, so an rc install gets offered the final build
    prerelease = 0 if "-" in (v or "") else 1
    return tuple(parts[:3]) + (prerelease,)


def check_update(current: str, repo: str = DEFAULT_REPO, fetch_fn=None,
                 manifest_fn=None) -> dict:
    """Compare the running version with the latest release.

    Primary source is the release manifest (version.json through
    releases/latest/download — a CDN redirect, no API rate limit); the GitHub
    REST release stays the fallback for releases that predate the manifest.
    Tests inject `fetch_fn` (or `manifest_fn`) and stay offline.
    """
    manifest_fn = manifest_fn or (_fetch_manifest if fetch_fn is None else None)
    if manifest_fn:
        try:
            m = manifest_fn(repo)
        except Exception:  # noqa: BLE001 - the release API gets its turn
            m = None
        if m and m.get("version"):
            latest = str(m["version"]).strip().lstrip("v")
            platform = running_platform()
            role = _ROLE_FOR.get(platform)
            name = (m.get("roles") or {}).get(role) if role else None
            asset = dict((m.get("assets") or {}).get(name) or {}) if name else {}
            asset = {"name": name, **asset} if (name and asset) else None
            can_apply = bool(asset) and platform in _APPLY_KINDS
            return {
                "current": current,
                "latest": latest or None,
                "update_available": bool(latest and _parse(latest) > _parse(current)),
                "url": f"https://github.com/{repo}/releases/tag/"
                       f"{m.get('tag') or 'v' + latest}",
                "asset": asset,
                "can_apply": can_apply,
                "apply_kind": _APPLY_KINDS.get(platform) if can_apply else None,
                "manifest": True,
            }
    fetch_fn = fetch_fn or _fetch_latest_release
    try:
        data = fetch_fn(repo)
    except Exception as e:  # noqa: BLE001 - reported, never raised
        return {"current": current, "latest": None,
                "update_available": False, "error": str(e),
                "asset": None, "can_apply": False, "apply_kind": None,
                "manifest": False}
    tag = (data.get("tag_name") or "").strip()
    latest = tag.lstrip("v") or None
    return {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and _parse(latest) > _parse(current)),
        "url": data.get("html_url"),
        "asset": None, "can_apply": False, "apply_kind": None,
        "manifest": False,
    }


def updates_possible() -> bool:
    """pip can update yt-dlp only where pip exists.

    A frozen build (PyInstaller one-file, Chaquopy on Android) bundles yt-dlp
    inside itself: there is nothing for pip to reach (v0.40.10 audit).
    """
    try:
        return importlib.util.find_spec("pip") is not None
    except (ImportError, ValueError):
        return False


def self_update(db_path=None) -> dict:
    """Upgrade yt-dlp — pip where it exists, the wheel path elsewhere.

    v0.43.0: a packaged build (no pip to run) fetches the official wheel
    from PyPI, verifies it, and stages it as the shadow copy that applies
    from the next start — see suravidl_engine/ytdlp_update.py.
    """
    before = yt_dlp.version.__version__
    if not updates_possible():
        from . import ytdlp_update

        return ytdlp_update.stage_update(db_path=db_path, before=before)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True, text=True, timeout=600,
        )
        ok = r.returncode == 0
        detail = (r.stdout + r.stderr)[-2000:]
    except Exception as e:  # noqa: BLE001 - surfaced to the client
        ok, detail = False, str(e)
    try:
        import importlib.metadata as md

        after = md.version("yt-dlp")
    except Exception:  # noqa: BLE001
        after = before
    return {"ok": ok, "updated": ok and after != before,
            "before": before, "after": after, "detail": detail}


# --- the app's own updates (v0.41.0 "the courier") --------------------------
#
# The feed is the release manifest, read through releases/latest/download:
# a CDN redirect instead of the REST API, so the 60-requests/hour anonymous
# rate limit cannot bite. The manifest's download URLs are pinned to its own
# tag, so the sha256 it carries always describes the bytes that URL serves.

MANIFEST_URL = "https://github.com/{repo}/releases/latest/download/version.json"

_APPLY_KINDS = {"windows": "windows_installer", "android": "android_apk",
                "macos": "macos_app_zip"}
_ROLE_FOR = {"windows": "windows_installer", "android": "android_apk",
             "macos": "macos_app_zip", "linux": "linux_appimage"}


def running_platform() -> str:
    """Which shell is asking. The Android shell exports SURAVIDL_ANDROID
    (EngineService) before Python starts."""
    if os.environ.get("SURAVIDL_ANDROID", "").strip() == "1":
        return "android"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _swap_script_path() -> Path:
    """The bundled swap script — shipped as package data on purpose, so
    the macOS CI job dry-runs the very file the app executes."""
    return Path(__file__).resolve().parent / "macos_swap.sh"


def app_bundle_from(exe) -> Path | None:
    """The .app bundle a frozen executable lives in, if any."""
    for parent in Path(exe).resolve().parents:
        if parent.suffix == ".app":
            return parent
    return None


def macos_apply_refusal(bundle: Path) -> str | None:
    """Why this bundle cannot replace itself, in the user's words — or None.

    A translocated copy (run straight from the mounted dmg; macOS runs it
    from a read-only random path) and a folder the user cannot write both
    get words up front, not a failed swap after the fact (v0.42.0).
    """
    p = str(bundle)
    if "/AppTranslocation/" in p or p.startswith("/Volumes/"):
        return ("this copy runs from the download image — drag suravidl "
                "into Applications, then update there")
    if not os.access(bundle.parent, os.W_OK):
        return ("suravidl cannot replace itself in this folder — move "
                "it somewhere you can write and try again")
    return None


def macos_apply_command(bundle, zip_path, pid: int) -> list[str]:
    """The detached swap the macOS courier rides (v0.42.0).

    /bin/bash runs the bundled script — it waits for THIS pid to exit,
    extracts the new bundle beside the old one, swaps by rename, rolls
    back on any failure, and reopens the app. Pure function — the tests
    pin the shape.
    """
    return ["/bin/bash", str(_swap_script_path()), "suravidl-apply",
            str(bundle), str(zip_path), str(int(pid))]


def _fetch_manifest(repo: str) -> dict:
    """The release manifest, via the rate-limit-free CDN redirect path."""
    req = Request(MANIFEST_URL.format(repo=repo),
                  headers={"User-Agent": "suravidl-update-check"})
    with urlopen(req, timeout=5, context=ssl_context()) as r:
        return json.loads(r.read().decode())


_DL_INIT = {"status": "idle", "name": None, "path": None, "bytes": 0,
            "total": 0, "sha256_ok": None, "error": None, "cancel": False}
_DL = dict(_DL_INIT)
_DL_LOCK = threading.Lock()


def reset_update_state(**fields) -> None:
    """Back to idle, plus any fields the caller presets."""
    with _DL_LOCK:
        _DL.clear()
        _DL.update(_DL_INIT)
        _DL.update(fields)


def update_status() -> dict:
    with _DL_LOCK:
        return dict(_DL)


def _set_state(**fields) -> dict:
    with _DL_LOCK:
        _DL.update(fields)
        return dict(_DL)


def _updates_dir() -> Path:
    from .api import default_cache_dir
    return default_cache_dir() / "updates"


def sweep_stale_downloads(dest_dir=None) -> int:
    """Delete staged update files that no live download owns (v0.42.1).

    A staged installer is only actionable inside the engine session that
    staged it — the state is in-memory, so anything on disk after a
    restart (or left by the version that just replaced itself) is an
    orphan the UI can never apply. Best-effort; returns how many went.
    """
    d = Path(dest_dir) if dest_dir else _updates_dir()
    with _DL_LOCK:
        st = dict(_DL)
    keep: set[str] = set()
    if st.get("status") in ("downloading", "verifying") and st.get("name"):
        keep = {str(st["name"]), str(st["name"]) + ".part"}
    elif st.get("status") == "ready" and st.get("path"):
        keep = {Path(st["path"]).name}
    removed = 0
    try:
        for p in d.iterdir():
            if p.is_file() and p.name not in keep:
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
    except OSError:
        return removed
    return removed


def download_asset(url: str, sha256, name: str, dest_dir) -> dict:
    """Stream one asset into dest_dir/name, verifying sha256 (required).

    Synchronous and stateful (progress lands in update_status() while it
    runs); the caller owns threading. A missing checksum is refused, and a
    mismatch or a network death leaves nothing behind: no final file, no
    .part.
    """
    name = str(name or "")
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"bad asset name: {name!r}")
    if not (sha256 and str(sha256).strip()):
        # no checksum, no staging: a manifest that omits the hash must not
        # fail open (audit finding 1)
        return _set_state(
            status="failed", sha256_ok=None,
            error="the release manifest carries no checksum for this "
                  "file, refusing to stage it")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    part = dest.with_name(dest.name + ".part")
    req = Request(url, headers={"User-Agent": "suravidl-update-download"})
    h = hashlib.sha256()
    got = 0

    def cancelled() -> bool:
        """The user asked to stop: clean up and end idle, voluntarily."""
        if not _DL.get("cancel"):
            return False
        part.unlink(missing_ok=True)
        _set_state(status="idle", name=None, path=None, bytes=0, total=0,
                   sha256_ok=None, error=None, cancel=False)
        return True
    try:
        with urlopen(req, timeout=30, context=ssl_context()) as r:
            total = int(r.headers.get("Content-Length") or 0)
            _set_state(status="downloading", name=name, path=None, bytes=0,
                       total=total, sha256_ok=None, error=None)
            with open(part, "wb") as f:
                while True:
                    if cancelled():
                        return update_status()
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    _set_state(bytes=got)
    except Exception as e:  # noqa: BLE001 - reported through the state
        part.unlink(missing_ok=True)
        return _set_state(status="failed", error=str(e))
    if cancelled():
        return update_status()
    _set_state(status="verifying")
    if h.hexdigest().lower() != str(sha256).strip().lower():
        part.unlink(missing_ok=True)
        return _set_state(
            status="failed", sha256_ok=False,
            error="sha256 mismatch — the download does not match the "
                  "release manifest")
    if cancelled():
        return update_status()
    try:
        part.replace(dest)
    except OSError as e:
        # a locked destination (AV scanner, open handle) must not leave
        # the .part behind (audit finding 11)
        part.unlink(missing_ok=True)
        return _set_state(status="failed", sha256_ok=True,
                          error=f"could not move the verified download "
                                f"into place: {e}")
    return _set_state(status="ready", path=str(dest), sha256_ok=True,
                      bytes=got, total=total or got)


def cancel_update_download() -> dict:
    """Abort a staged download in flight.

    The worker observes the flag between chunks and ends in idle, leaving
    nothing behind; with nothing running this is a no-op."""
    with _DL_LOCK:
        if _DL["status"] in ("downloading", "verifying"):
            _DL["cancel"] = True
        return dict(_DL)


def start_update_download(current: str, repo: str = DEFAULT_REPO,
                          manifest_fn=None, download_fn=None,
                          dest_dir=None) -> dict:
    """Check, then stage this platform's asset in a worker thread.

    Returns the current state immediately; callers poll update_status().
    `download_fn` and `manifest_fn` exist for tests — production uses the
    real ones.
    """
    with _DL_LOCK:
        if _DL["status"] in ("downloading", "verifying"):
            return dict(_DL)
        # claim BEFORE the blocking feed check: a second tap must see the
        # claim, not race past it into a duplicate download (finding 2)
        _DL.update(status="downloading", name=None, path=None, bytes=0,
                   total=0, sha256_ok=None, error=None, cancel=False)
    fetch = download_fn or download_asset
    dest = Path(dest_dir) if dest_dir else _updates_dir()
    # whatever a previous session staged is an orphan the moment a fresh
    # download starts — nothing else may linger beside it (v0.42.1)
    sweep_stale_downloads(dest)
    info = check_update(current, repo, manifest_fn=manifest_fn)
    if not info.get("update_available") or not info.get("asset"):
        return _set_state(status="idle", name=None, path=None, bytes=0,
                          total=0, sha256_ok=None, error=None)
    asset = info["asset"]
    url = str(asset.get("url") or "")
    # the asset must come from THIS project's release path, not any repo
    # an attacker could register (finding 6)
    if not url.startswith(f"https://github.com/{repo}/releases/download/"):
        return _set_state(status="failed",
                          error=f"untrusted asset url: {url!r}")
    if not str(asset.get("sha256") or "").strip():
        return _set_state(
            status="failed",
            error="the release manifest carries no checksum for this "
                  "asset, refusing to stage it")
    _set_state(status="downloading", name=asset.get("name"), path=None,
               bytes=0, total=int(asset.get("size") or 0), sha256_ok=None,
               error=None)

    def _run():
        try:
            result = fetch(url, asset.get("sha256"), asset["name"], dest)
        except Exception as e:  # noqa: BLE001 - reported through the state
            result = {"status": "failed", "error": str(e)}
        if isinstance(result, dict):
            _set_state(**{k: v for k, v in result.items() if k in _DL_INIT})

    threading.Thread(target=_run, daemon=True).start()
    return update_status()
