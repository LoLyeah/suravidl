"""Desktop entry: serve the engine, open it in a standalone window.

Falls back to the browser when no webview runtime is available (e.g. a
headless server, or a Linux frozen build without GTK bindings).
Runnable as `python -m suravidl_engine` or as a PyInstaller-frozen binary.
"""
import argparse
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def find_free_port(preferred: int) -> int:
    """Return `preferred` if bindable, else a random free port."""
    def bindable(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return True
            except OSError:
                return False

    if preferred != 0 and bindable(preferred):
        return preferred
    # resolve an ephemeral port to an actual usable number
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def token_path() -> Path:
    return Path.home() / ".suravidl" / "token"


def load_or_create_token() -> str:
    """The engine's token: `SURAVIDL_TOKEN` when set, else the token file.

    The env var came first here for a reason (v0.21.1 audit): the README tells
    people to run the engine with `SURAVIDL_TOKEN=x …`, but only the `.api`
    entry honoured it — `python -m suravid_engine` silently used the file
    instead, so a documented way of pinning a token did nothing. An env var
    that is set is a decision: it wins, and it is not written to disk.
    """
    env = os.environ.get("SURAVIDL_TOKEN", "").strip()
    if env:
        return env
    p = token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    _harden(p.parent, 0o700)
    if p.exists():
        t = p.read_text(encoding="utf-8").strip()
        if t:
            _harden(p, 0o600)
            return t
    t = secrets.token_hex(16)
    p.write_text(t, encoding="utf-8")
    _harden(p, 0o600)
    return t


def _harden(path: Path, mode: int) -> None:
    """Best-effort chmod: the token and its directory are for us only."""
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def start_server(download_dir, token: str, port: int, db_path=None,
                 desktop_actions: dict | None = None,
                 page_key: str | None = None, cache_dir=None):
    """Start uvicorn in a daemon thread; returns the server (for shutdown).

    `page_key` gates `GET /` (see create_app): the Android shell sets it so
    the page that carries the API token is not readable by every other app
    that can open a socket to the loopback port (v0.21.1 audit).

    `cache_dir` is where yt-dlp's cache lives; None means the engine's
    default resolution (the shell's `SURAVIDL_CACHE_DIR`, else the XDG
    cache home). The Android shell exports the env var before Python starts,
    so it needs no extra argument here.
    """
    import uvicorn

    from .api import create_app

    config = uvicorn.Config(
        create_app(download_dir=download_dir, auth_token=token, db_path=db_path,
                   desktop_actions=desktop_actions, page_key=page_key,
                   cache_dir=cache_dir),
        host="127.0.0.1", port=port, log_level="warning",
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    return server


def _impersonation_probe() -> tuple[bool, str]:
    """Can this build really impersonate a browser? (v0.27.0)

    Constructing the session loads the bundled libcurl-impersonate, so this
    proves the whole chain travelled — the Python package AND its shared
    library. The desktop release smoke test sets SURAVIDL_EXPECT_IMPERSONATE=1
    so a build that lost curl_cffi fails in CI instead of on a user's Mac.
    """
    try:
        import curl_cffi.requests

        curl_cffi.requests.Session(impersonate="chrome")
        return True, f"curl_cffi {getattr(curl_cffi, '__version__', '?')}, chrome target loads"
    except Exception as e:  # noqa: BLE001 - any failure means "no"
        return False, f"{e.__class__.__name__}: {e}"


def self_test(download_dir, port: int = 0, timeout_s: float = 20) -> bool:
    """Boot the full app on a free port and poll /health. CI verification."""
    import urllib.request

    port = find_free_port(port)
    token = load_or_create_token()
    start_server(download_dir=download_dir, token=token, port=port,
                 db_path=Path(download_dir) / "jobs.db")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    imp_ok, imp_detail = _impersonation_probe()
                    print(f"SELFTEST_IMPERSONATE "
                          f"{'ok' if imp_ok else 'missing'} — {imp_detail}")
                    if (os.environ.get("SURAVIDL_EXPECT_IMPERSONATE") == "1"
                            and not imp_ok):
                        print("SELFTEST_FAIL (impersonation was expected, "
                              "but this build cannot do it)")
                        return False
                    print(f"SELFTEST_OK http://127.0.0.1:{port}/")
                    return True
        except Exception:
            time.sleep(0.3)
    print("SELFTEST_FAIL")
    return False


def _open_folder(path) -> None:
    """Reveal a downloaded file in the OS file manager."""
    import subprocess
    from pathlib import Path as _Path

    target = _Path(path)
    if sys.platform == "win32":
        import os

        os.startfile(str(target.parent if target.is_file() else target))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", str(target)], check=False)
    else:
        subprocess.run(["xdg-open", str(target.parent if target.is_file() else target)],
                       check=False)


def _load_webview():
    try:
        import webview  # pywebview

        return webview
    except Exception:  # noqa: BLE001 - optional dependency
        return None


def _try_window(webview, url: str):
    """Create (but don't start) the standalone window; None if impossible."""
    # macOS goes transparent so the native glass material can sit behind
    # the page (v0.38.4); other platforms stay opaque.
    try:
        return webview.create_window(
            "suravidl", url, width=1100, height=780, min_size=(760, 480),
            transparent=sys.platform == "darwin",
        )
    except TypeError:  # an older pywebview without the transparent kwarg
        try:
            return webview.create_window(
                "suravidl", url, width=1100, height=780, min_size=(760, 480))
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001 - e.g. GTK bindings missing
        return None


def _import_appkit():
    """pyobjc is optional even on darwin; (None, None) means no material."""
    try:
        import AppKit
        import Foundation

        return AppKit, Foundation
    except Exception:  # noqa: BLE001 - not macOS, or pyobjc missing
        return None, None


def _find_webview_view(root):
    """Depth-first: the WKWebView pywebview wrapped (its own container first)."""
    stack = [root]
    while stack:
        view = stack.pop(0)
        if type(view).__name__ == "WKWebView":
            return view
        stack.extend(view.subviews())
    return None


def _install_material(window, AppKit, Foundation) -> bool:
    """Insert a real native material behind the page content.

    NSGlassEffectView is Apple's Liquid Glass material (macOS 26+). Older
    systems get the long-established NSVisualEffectView vibrancy in
    behind-window mode — the material the UI's 'frosted' theme imitates.
    Returns True when a layer was actually inserted.
    """
    if AppKit is None:
        return False
    native = getattr(window, "native", None)
    if native is None:
        return False
    try:
        content = native.contentView()
        webview_view = _find_webview_view(content)
        if webview_view is None:
            return False
        glass_cls = getattr(AppKit, "NSGlassEffectView", None)
        if glass_cls is None:
            glass_cls = AppKit.NSVisualEffectView
        material = glass_cls.alloc().init()
        material.setFrame_(content.bounds())
        if glass_cls is AppKit.NSVisualEffectView:
            material.setMaterial_(
                AppKit.NSVisualEffectMaterialUnderWindowBackground)
            material.setBlendingMode_(
                AppKit.NSVisualEffectBlendingModeBehindWindow)
            material.setState_(AppKit.NSVisualEffectStateActive)
        content.addSubview_positioned_relativeTo_(
            material, AppKit.NSWindowBelow, webview_view)
        try:
            # the page composites over the material instead of a white box
            webview_view.setValue_forKey_(False, "drawsBackground")
        except Exception:  # noqa: BLE001 - private-ish KVC key
            pass
        try:
            # follow the page's theme at launch (a mid-session theme switch
            # keeps the material it was born with — restart to re-sync)
            theme = window.evaluate_js(
                'document.documentElement.dataset.theme') or "dark"
            named = ("NSAppearanceNameDarkAqua"
                     if theme in ("dark", "amoled") else "NSAppearanceNameAqua")
            material.setAppearance_(AppKit.NSAppearance.appearanceNamed_(named))
        except Exception:  # noqa: BLE001 - decoration, never fatal
            pass
        return True
    except Exception:  # noqa: BLE001 - unknown shells: stay plain
        return False


def _apply_native_material(window) -> bool:
    """macOS only: the real glass. Windows and Linux keep their own look."""
    if sys.platform != "darwin":
        return False
    AppKit, Foundation = _import_appkit()
    return _install_material(window, AppKit, Foundation)


def _native_glass_ready(window):
    """webview.start callback: window.native exists only after the GUI is up."""
    try:
        if _apply_native_material(window):
            # the body steps aside so the native material shows through
            window.evaluate_js(
                'document.documentElement.dataset.host = "darwin-glass"; true')
    except Exception:  # noqa: BLE001 - the plain window still works
        pass


def _try_tray(url: str, open_downloads: Path):
    """Tray icon with Open/Quit. Returns the pystray Icon or None."""
    try:
        from PIL import Image  # noqa: F401
        import pystray
    except Exception:  # noqa: BLE001 - tray is optional
        return None

    icon_file = Path(__file__).parent / "web" / "icon.png"
    if not icon_file.exists():
        return None
    from PIL import Image

    def on_open(icon, item):
        webbrowser.open(url)

    def on_folder(icon, item):
        import subprocess

        if sys.platform == "win32":
            import os

            os.startfile(open_downloads)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(open_downloads)], check=False)
        else:
            subprocess.run(["xdg-open", str(open_downloads)], check=False)

    def on_quit(icon, item):
        icon.stop()
        import os

        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open suravidl", on_open, default=True),
        pystray.MenuItem("Open downloads folder", on_folder),
        pystray.MenuItem("Quit", on_quit),
    )
    return pystray.Icon("suravidl", Image.open(icon_file), "suravidl", menu)


def main() -> None:
    p = argparse.ArgumentParser(
        description="suravidl desktop: engine + UI window (+ tray fallback)")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--download-dir", type=Path, default=Path.home() / "Downloads")
    p.add_argument("--db", type=Path, default=Path.home() / ".suravidl" / "jobs.db")
    p.add_argument("--cache-dir", type=Path, default=None,
                   help="where yt-dlp's cache lives "
                        "(default: XDG cache home, ~/.cache/suravidl)")
    p.add_argument("--no-browser", action="store_true",
                   help="don't fall back to opening a browser tab")
    p.add_argument("--no-window", action="store_true",
                   help="force browser mode instead of the app window")
    p.add_argument("--no-tray", action="store_true")
    p.add_argument("--selftest", action="store_true",
                   help="boot, verify /health, exit (CI)")
    args = p.parse_args()

    if args.selftest:
        ok = self_test(download_dir=args.download_dir, port=args.port)
        sys.exit(0 if ok else 1)

    token = load_or_create_token()
    port = find_free_port(args.port)
    url = f"http://127.0.0.1:{port}/"

    webview = None if args.no_window else _load_webview()
    window = _try_window(webview, url) if webview else None
    actions = {}
    if window is not None:
        def _pick_file():
            try:
                picked = window.create_file_dialog(webview.OPEN_DIALOG)
            except Exception:  # noqa: BLE001 - dialog cancelled or unsupported
                return None
            return picked[0] if picked else None

        def _open_url(url):
            """Open a link in the user's REAL browser: the embedded window
            cannot honour target=_blank, so release pages must go outside."""
            if webbrowser.open(url):
                return
            import subprocess

            opener = "open" if sys.platform == "darwin" else "xdg-open"
            with open(os.devnull, "wb") as sink:
                subprocess.Popen([opener, url], stdout=sink, stderr=sink)

        actions = {"minimize": window.minimize, "quit": window.destroy,
                   "reveal": _open_folder, "pick_file": _pick_file,
                   "open_url": _open_url}

    server = start_server(download_dir=args.download_dir, token=token, port=port,
                          db_path=args.db, desktop_actions=actions or None,
                          cache_dir=args.cache_dir)
    print(f"suravidl running at {url}  (token: {token[:4]}…{token[-4:]})")

    if window is not None:
        def _ready():
            _native_glass_ready(window)   # runs once the GUI loop is up

        try:
            webview.start(_ready)
        except Exception:  # noqa: BLE001 - fall back to the browser
            window = None
            # the window never came up (headless host, missing Qt/GTK, …):
            # stop advertising a desktop app we cannot honour, so /app/info
            # says the truth and /app/* answer 501 instead of a 500 from a
            # window that does not exist (v0.21.1 audit)
            actions.clear()
        else:
            server.should_exit = True
            print("bye")
            return

    if not args.no_browser:
        webbrowser.open(url)

    icon = None if args.no_tray else _try_tray(url, args.download_dir)
    if icon is not None:
        icon.run_detached()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    else:
        # headless or no tray available: serve until Ctrl+C
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("bye")


if __name__ == "__main__":
    main()
