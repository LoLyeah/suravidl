"""The second copy of yt-dlp — in-app updates for packaged builds (v0.43.0).

A packaged build (PyInstaller one-file on Windows/macOS/Linux, Chaquopy on
Android) carries the downloader inside the app: no pip runs there and no
site-packages exists to upgrade. So updates go the other way around — the
official py3-none-any wheel is fetched from PyPI, its sha256 verified
against PyPI's own metadata (stricter than pip, which trusts TLS alone),
unpacked into `<data dir>/ytdlp` beside jobs.db, and put ahead of the
bundled copy on sys.path before the first import. A running process keeps
what it already imported: the new copy applies from the next start.

Which copy runs is decided by version, not by who downloaded what — the
newer one wins. When an app update ships a bundle newer than the staged
copy, the stage is removed on the next boot. The exact comparison uses
importlib.metadata; where a runtime cannot answer that (see
suravidl.spec for the desktop bundle, Chaquopy for Android), a stage is
trusted only while the app version it was staged under still matches.

This module must stay import-light: it runs before the shadow is on
sys.path, so nothing here may import yt_dlp at module level.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path

from . import __version__
from .net import ssl_context

# One staging run per process (v0.43.2 audit): POST /update is synchronous,
# and two worker threads share os.getpid() — the same part file, the same
# stage directory, interleaved writes. The second caller gets an honest
# busy answer instead.
_STAGE_LOCK = threading.Lock()

# A scheduled removal (v0.43.2): an ACTIVE copy cannot be unlinked while the
# process runs (yt-dlp imports extractors from it lazily), so the request
# lands as a marker file and activate() honours it at the next start.
_REMOVE_MARKER = "remove-pending"

PYPI_JSON = "https://pypi.org/pypi/yt-dlp/json"
ALLOWED_HOST = "files.pythonhosted.org"
MAX_WHEEL = 80 * 1024 * 1024
_UA = "suravidl-engine"
_CHUNK = 256 * 1024


def _dbg(msg: str) -> None:
    """Boot-decision trace, off unless SURAVIDL_YTDLP_DEBUG names a file.

    A frozen build's stdout is not somewhere to debug from (windowed
    bundles boot with ``sys.stdout = None``; the desktop build swallows
    it), so the shadow decision — the one thing that must happen before
    anything else can even import — records itself to a file on demand.
    """
    dest = os.environ.get("SURAVIDL_YTDLP_DEBUG")
    if not dest:
        return
    try:
        with open(dest, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def _tup(v) -> tuple | None:
    parts = str(v).split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def is_stable(v) -> bool:
    """yt-dlp stable releases are plain calendar versions (2026.8.19).

    Nightlies carry a .devN suffix; only stable versions are ever staged.
    """
    t = _tup(v)
    return t is not None and len(t) >= 2


def is_newer(a, b) -> bool:
    """Numeric calendar comparison — 2026.10.1 IS newer than 2026.8.19.

    Unparseable versions never count as newer: "newer wins" must be
    provable, or the older copy stays.
    """
    ta, tb = _tup(a), _tup(b)
    if ta is None or tb is None:
        return False
    return ta > tb


def _app_data_dir(db_path=None) -> Path:
    if db_path is None or str(db_path) == ":memory:":
        return Path.home() / ".suravidl"
    return Path(db_path).parent


def _shadow_dir(db_path=None) -> Path:
    return _app_data_dir(db_path) / "ytdlp"


def shadow_version(shadow_dir) -> str | None:
    """The staged copy's version, read from its dist-info — no imports."""
    for meta in sorted(Path(shadow_dir).glob("yt_dlp-*.dist-info/METADATA")):
        m = re.search(r"^Version:\s*(\S+)\s*$",
                      meta.read_text(errors="replace"), re.M)
        if m:
            return m.group(1)
    return None


def bundled_version() -> str | None:
    """The app's own yt-dlp version, when this runtime can say.

    importlib.metadata does not import the package, so calling this before
    the shadow decision cannot poison sys.modules. The desktop bundle
    needs PyInstaller's copy_metadata("yt-dlp") for this to answer (see
    suravidl.spec); Chaquopy may not expose distribution metadata at all.
    None simply means "compare by app version instead" (see activate).
    """
    try:
        import importlib.metadata as md

        return md.version("yt-dlp")
    except Exception:  # noqa: BLE001 - absence is a normal outcome here
        return None


def active_version() -> str:
    """The version THIS process actually runs (shadow if it was activated)."""
    import yt_dlp.version

    return yt_dlp.version.__version__


def _read_stamp(shadow: Path) -> dict:
    try:
        data = json.loads((shadow / "staged.json").read_text())
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - staging info is best-effort
        return {}


def _sweep_leftovers(base: Path) -> None:
    """Crashed stages and half-downloads never outlive a boot."""
    for p in base.glob("ytdlp.stage.*"):
        shutil.rmtree(p, ignore_errors=True)
    # a swap that crashed between its renames leaves the previous copy
    # renamed aside as ytdlp.old — it is garbage either way
    shutil.rmtree(base / "ytdlp.old", ignore_errors=True)
    _unlink(base / "ytdlp.whl.part")


def _unlink(p: Path) -> None:
    try:
        p.unlink()
    except OSError:
        pass


def _put_on_path(shadow: Path) -> None:
    s = str(shadow)
    if s not in sys.path:
        sys.path.insert(0, s)


def activate(db_path=None) -> str | None:
    """Put a staged copy ahead of the bundle when it should win; else sweep.

    Call before any import of yt_dlp — start_server and main() do it first
    thing, before even the updater module (which imports yt_dlp) loads.
    Idempotent; never raises.
    """
    try:
        base = _app_data_dir(db_path)
        _dbg(f"activate: db={db_path!r} base={base} frozen={getattr(sys, 'frozen', None)} "
             f"py={sys.version.split()[0]} path0={sys.path[0]!r}")
        _sweep_leftovers(base)
        shadow = _shadow_dir(db_path)
        _dbg(f"activate: shadow={shadow} isdir={shadow.is_dir()}")
        # Already decided in THIS process? main() and start_server() both
        # call us, and the second call must not re-derive "bundled": by then
        # importlib.metadata scans sys.path, finds the SHADOW's dist-info,
        # reports the shadow's version as the bundle's — and the "stale"
        # branch wipes the copy the first call just activated (v0.43.0
        # freeze test: the app deleted its own update on every boot). The
        # first decision stands; later calls only report it.
        if str(shadow) in sys.path:
            _dbg("activate: already on path - first decision stands")
            return shadow_version(shadow)
        if not shadow.is_dir():
            return None
        if (shadow / _REMOVE_MARKER).exists():
            # the user asked for this while the copy was live last session
            # (v0.43.2): this is the first start where nothing has imported
            # from it, so deleting it now cannot break anything
            _dbg("activate: pending removal - dropping the downloaded copy")
            shutil.rmtree(shadow, ignore_errors=True)
            return None
        sv = shadow_version(shadow)
        _dbg(f"activate: shadow_version={sv!r}")
        if sv is None:
            # a torn extraction: nothing runnable in there
            shutil.rmtree(shadow, ignore_errors=True)
            return None
        bundled = bundled_version()
        _dbg(f"activate: bundled={bundled!r} newer_than_bundled={is_newer(sv, bundled) if bundled else None}")
        if bundled is not None:
            if is_newer(sv, bundled):
                _put_on_path(shadow)
                _dbg("activate: ACTIVATED (beat bundle)")
                return sv
            # an app update brought something at least as new — the stage
            # can only ever lose to the bundle now
            _dbg("activate: REMOVED (stale vs bundle)")
            shutil.rmtree(shadow, ignore_errors=True)
            return None
        # No metadata to compare with (some packaged runtimes). Trust a
        # stage made under THIS app build — by construction it was newer
        # than the bundle then, and the bundle cannot have changed. If the
        # app HAS changed since, its own copy wins until the user re-taps
        # Update, which re-stages the true latest and converges.
        stamp = _read_stamp(shadow)
        _dbg(f"activate: stamp={stamp!r} this_app={__version__!r}")
        if stamp.get("app") == __version__ and \
                is_newer(sv, str(stamp.get("baseline", "0"))):
            _put_on_path(shadow)
            _dbg("activate: ACTIVATED (same-app stage)")
            return sv
        _dbg("activate: kept (app changed, no metadata)")
        return None
    except Exception as e:  # noqa: BLE001 - a boot must never fail here
        _dbg(f"activate: CRASHED {e!r}")
        return None


def activate_safe(db_path=None) -> str | None:
    """activate() for boot call-sites: never raises, traces to _dbg."""
    try:
        return activate(db_path)
    except Exception as e:  # noqa: BLE001 - a boot must never fail here
        _dbg(f"activate raised: {e!r}")
        return None


def active_source(db_path=None) -> str:
    """Where the running yt_dlp comes from: downloaded, bundled, environment.

    "downloaded" — the shadow is on sys.path, so imports resolved to it;
    "bundled" — a packaged build with no shadow (its yt-dlp is inside);
    "environment" — a pip/venv install (dev runs).
    """
    if str(_shadow_dir(db_path)) in sys.path:
        return "downloaded"
    return "bundled" if getattr(sys, "frozen", False) else "environment"


def remove_shadow(db_path=None) -> dict:
    """Remove the downloaded copy; the bundled one takes over.

    A staged copy is canceled on the spot — nothing has imported from it.
    An ACTIVE copy is different: its modules are loaded, and yt-dlp pulls
    extractor submodules from that directory lazily for as long as the
    process lives, so deleting it mid-run turns the next unseen site into
    a ModuleNotFoundError (v0.43.2 audit). The removal is scheduled
    instead: a marker file lands inside the copy, `activate()` drops it
    at the next start — before anything has imported from it — and the
    bundle serves from then on. Only the files this feature created are
    ever touched; the bundle is never modified.
    """
    base = _app_data_dir(db_path)
    shadow = _shadow_dir(db_path)
    _sweep_leftovers(base)
    if not shadow.is_dir():
        return {"ok": True, "removed": False, "pending": False,
                "version": None}
    ver = shadow_version(shadow)
    if str(shadow) in sys.path:
        try:
            (shadow / _REMOVE_MARKER).write_text("1", encoding="utf-8")
        except OSError as e:
            return {"ok": False, "removed": False, "pending": False,
                    "version": ver,
                    "detail": f"couldn't schedule the removal: {e}"}
        return {"ok": True, "removed": False, "pending": True, "version": ver}
    shutil.rmtree(shadow, ignore_errors=True)
    # drop any stale sys.path entry too — a path that points at nothing
    # must not linger for whatever asks next
    s = str(shadow)
    while s in sys.path:
        sys.path.remove(s)
    gone = not shadow.exists()
    return {"ok": gone, "removed": gone, "pending": False, "version": ver}


def removal_pending(db_path=None) -> bool:
    """True when a removal is scheduled for the next start (v0.43.2)."""
    try:
        return (_shadow_dir(db_path) / _REMOVE_MARKER).exists()
    except Exception:  # noqa: BLE001 - a hint must never fail
        return False


def _fetch_json(url: str = PYPI_JSON) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    # net.ssl_context(): the frozen macOS bundle has no discoverable store,
    # so a bare urlopen dies with CERTIFICATE_VERIFY_FAILED there
    with urllib.request.urlopen(req, timeout=20, context=ssl_context()) as r:
        return json.load(r)


def pick_stable(payload: dict) -> dict | None:
    """Newest stable release with a verifiable universal wheel.

    Walk down from the newest stable version until a release has a file
    that qualifies: a py3-none-any wheel, served over https from PyPI's
    own file host, with the sha256 PyPI publishes for it.
    """
    releases = payload.get("releases") or {}
    stable = [v for v in releases if is_stable(v)]
    for v in sorted(stable, key=lambda s: _tup(s) or (0,), reverse=True):
        for f in releases.get(v) or []:
            if (f or {}).get("packagetype") != "bdist_wheel":
                continue
            if not str(f.get("filename", "")).endswith("-py3-none-any.whl"):
                continue
            url = str(f.get("url", ""))
            if not url.startswith(f"https://{ALLOWED_HOST}/"):
                continue
            sha = (f.get("digests") or {}).get("sha256")
            if not sha:
                continue
            return {"version": v, "url": url, "sha256": str(sha).lower(),
                    "size": int(f.get("size") or 0)}
    return None


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_wheel(url: str, dest: Path) -> int:
    """Stream the wheel to dest, https from PyPI's file host only."""
    if not url.startswith(f"https://{ALLOWED_HOST}/"):
        raise ValueError(f"refusing a download from {url[:60]}")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    n = 0
    with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as r, \
            open(dest, "wb") as f:
        while True:
            chunk = r.read(_CHUNK)
            if not chunk:
                break
            n += len(chunk)
            if n > MAX_WHEEL:
                raise ValueError("wheel exceeded the size cap while downloading")
            f.write(chunk)
    return n


def _extract_wheel(wheel: Path, dest: Path, expect_version: str) -> None:
    """Unpack a wheel into dest — every entry checked while it is closed.

    Traversal guard first (a wheel that writes outside itself is refused
    whole), then metadata and payload sanity against the expected version.
    """
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(wheel) as z:
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if target != root and not target.is_relative_to(root):
                raise ValueError(
                    f"refusing a wheel that writes outside itself ({info.filename})")
            if info.file_size > MAX_WHEEL:
                raise ValueError("refusing an oversized wheel entry")
        z.extractall(dest)
    meta = dest / f"yt_dlp-{expect_version}.dist-info" / "METADATA"
    if not meta.exists():
        raise ValueError("wheel is missing its metadata")
    if not re.search(rf"^Version:\s*{re.escape(expect_version)}\s*$",
                     meta.read_text(errors="replace"), re.M):
        raise ValueError("wheel metadata disagrees with its filename")
    if not (dest / "yt_dlp" / "version.py").exists():
        raise ValueError("wheel is missing yt_dlp itself")


def _swap_in(stage: Path, shadow: Path) -> None:
    """stage → shadow, atomically enough: rename aside, rename in, drop."""
    old = shadow.with_name("ytdlp.old")
    shutil.rmtree(old, ignore_errors=True)
    if shadow.exists():
        shadow.rename(old)
    stage.rename(shadow)
    shutil.rmtree(old, ignore_errors=True)


def stage_update(db_path=None, *, fetch_json=None, download=None,
                 before=None) -> dict:
    """Fetch, verify and unpack the newest release; live from the next start.

    `fetch_json` / `download` / `before` exist for the tests; the defaults
    talk to PyPI and to the running copy.
    """
    fetch_json = fetch_json or _fetch_json
    download = download or _download_wheel
    if before is None:
        try:
            before = active_version()
        except Exception:  # noqa: BLE001
            before = "unknown"
    base = _app_data_dir(db_path)

    def fail(detail: str) -> dict:
        return {"ok": False, "updated": False, "bundled": True,
                "before": before, "after": before, "detail": detail}

    if not _STAGE_LOCK.acquire(blocking=False):
        return fail("another yt-dlp update is already running")
    try:
        try:
            payload = fetch_json()
        except Exception as e:  # noqa: BLE001 - surfaced to the client
            return fail(f"couldn't reach PyPI: {e}")
        latest = pick_stable(payload)
        if latest is None:
            return fail("no suitable yt-dlp release found on PyPI")
        if not is_newer(latest["version"], before):
            return {"ok": True, "updated": False, "bundled": True,
                    "before": before, "after": before,
                    "detail": f"already on the latest release ({before})"}
        if latest["size"] and latest["size"] > MAX_WHEEL:
            return fail(f"refusing a {latest['size']}-byte wheel")
        base.mkdir(parents=True, exist_ok=True)
        part = base / "ytdlp.whl.part"
        stage = base / f"ytdlp.stage.{os.getpid()}"
        shadow = _shadow_dir(db_path)
        try:
            _sweep_leftovers(base)
            download(latest["url"], part)
            got = _file_sha256(part)
            if got != latest["sha256"]:
                raise ValueError(
                    f"sha256 mismatch (wanted {latest['sha256'][:12]}…, got {got[:12]}…)")
            _extract_wheel(part, stage, expect_version=latest["version"])
            (stage / "staged.json").write_text(json.dumps({
                "version": latest["version"], "baseline": before,
                "app": __version__}))
            _swap_in(stage, shadow)
        except Exception as e:  # noqa: BLE001 - surfaced to the client
            shutil.rmtree(stage, ignore_errors=True)
            _unlink(part)
            return fail(str(e))
        finally:
            _unlink(part)
        return {"ok": True, "updated": True, "bundled": True,
                "before": before, "after": latest["version"],
                "restart": True,
                "detail": f"staged {latest['version']} — applies on next start"}
    finally:
        _STAGE_LOCK.release()


def pending_version(db_path=None) -> str | None:
    """A staged copy newer than what this process runs (the UI's hint)."""
    try:
        sv = shadow_version(_shadow_dir(db_path))
        if sv and is_newer(sv, active_version()):
            return sv
    except Exception:  # noqa: BLE001 - a display hint must never fail
        pass
    return None
