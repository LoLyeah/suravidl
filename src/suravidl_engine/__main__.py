"""Desktop entry: serve the engine, open it in a standalone window.

Falls back to the browser when no webview runtime is available (e.g. a
headless server, or a Linux frozen build without GTK bindings).
Runnable as `python -m suravidl_engine` or as a PyInstaller-frozen binary.
"""
import argparse
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
    p = token_path()
    if p.exists():
        t = p.read_text(encoding="utf-8").strip()
        if t:
            return t
    t = secrets.token_hex(16)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")
    return t


def start_server(download_dir, token: str, port: int, db_path=None,
                 desktop_actions: dict | None = None):
    """Start uvicorn in a daemon thread; returns the server (for shutdown)."""
    import uvicorn

    from .api import create_app

    config = uvicorn.Config(
        create_app(download_dir=download_dir, auth_token=token, db_path=db_path,
                   desktop_actions=desktop_actions),
        host="127.0.0.1", port=port, log_level="warning",
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    return server


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
    try:
        return webview.create_window(
            "suravidl", url, width=1100, height=780, min_size=(760, 480),
        )
    except Exception:  # noqa: BLE001 - e.g. GTK bindings missing
        return None


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

        actions = {"minimize": window.minimize, "quit": window.destroy,
                   "reveal": _open_folder, "pick_file": _pick_file}

    server = start_server(download_dir=args.download_dir, token=token, port=port,
                          db_path=args.db, desktop_actions=actions or None)
    print(f"suravidl running at {url}  (token: {token[:4]}…{token[-4:]})")

    if window is not None:
        try:
            webview.start()
        except Exception:  # noqa: BLE001 - fall back to the browser
            window = None
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
