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


# Windows hides consoles with this spawn flag (subprocess.CREATE_NO_WINDOW;
# spelled out so the constant exists on every platform for the tests).
_CREATE_NO_WINDOW = 0x08000000
_CONSOLES_HIDDEN: list[bool] = []


def _hidden_popen_init(orig_init):
    """Wrap a Popen.__init__ so every child spawns without a console."""

    def _init(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | _CREATE_NO_WINDOW
        orig_init(self, *args, **kwargs)

    return _init


def _hide_child_consoles() -> None:
    """Windows: no console windows for anything we spawn.

    The build is windowed (``console=False`` in the spec), so a
    console-subsystem child — ffmpeg during a merge, pip during a yt-dlp
    update — would otherwise flash a black window on screen. One wrapper at
    subprocess.Popen covers every spawner, the bundled yt-dlp's included.
    No-op off Windows; idempotent.
    """
    if os.name != "nt" or _CONSOLES_HIDDEN:
        return
    import subprocess

    _CONSOLES_HIDDEN.append(True)
    subprocess.Popen.__init__ = _hidden_popen_init(subprocess.Popen.__init__)


def _ensure_log_targets(log_path: Path) -> None:
    """A windowed build boots with ``sys.stdout = None``: every print() would
    vanish and a crash would leave no trail. Point them at a log file."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        log_path.parent.mkdir(mode=0o700, exist_ok=True)
        if log_path.exists() and log_path.stat().st_size > 1_000_000:
            log_path.write_text("", encoding="utf-8")  # one boot's trail is enough
        stream = open(log_path, "a", encoding="utf-8", errors="replace",
                      buffering=1)
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


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


# ---------- the tray (v0.38.7) ----------
# The window's own "−" button is a tray habit, not a Dock habit: on macOS
# the whole app tucks away behind a menu-bar item ("Show suravidl" a click
# away — the Dock icon brings it back too). Windows and Linux hide the
# window behind a real tray icon. Every missing piece — no pyobjc, no
# pystray, no icon file — degrades to the previous plain minimize.

_TRAY: dict = {}          # the live status item / tray icon + its window
_MOTION_SETTLE = 2.5      # seconds the window lives before the motion probe


def _on_main(fn) -> None:
    """Run `fn` on the AppKit main thread when we can; inline otherwise."""
    try:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(fn)
    except Exception:  # noqa: BLE001 - tests / non-mac: call it right here
        fn()


def _tray_target(Foundation):
    """The menu's action target: plain methods, worn as objc selectors."""

    class _TrayTarget(Foundation.NSObject):
        def showWindow_(self, _sender):  # noqa: N802 - the objc spelling
            item = _TRAY.get("item")
            if item is not None:
                try:
                    item.setVisible_(False)
                except Exception:  # noqa: BLE001
                    pass
            appkit = _TRAY.get("AppKit")
            if appkit is not None:
                try:
                    app = appkit.NSApplication.sharedApplication()
                    app.unhide_(None)
                    app.activateIgnoringOtherApps_(True)
                except Exception:  # noqa: BLE001
                    pass
            win = _TRAY.get("window")
            if win is not None:
                win.show()

        def quitApp_(self, _sender):  # noqa: N802
            win = _TRAY.get("window")
            if win is not None:
                win.destroy()

    return _TrayTarget


def _install_tray_item(window, AppKit, Foundation):
    """Create the macOS menu-bar item (hidden until the app tucks away)."""
    if "item" in _TRAY:
        return _TRAY["item"]
    try:
        item = (AppKit.NSStatusBar.systemStatusBar()
                .statusItemWithLength_(AppKit.NSVariableStatusItemLength))
        try:
            img = AppKit.NSImage \
                .imageWithSystemSymbolName_accessibilityDescription_(
                    "arrow.down.circle.fill", "suravidl")
        except Exception:  # noqa: BLE001 - AppKit without SF Symbols
            img = None
        if img is not None:
            img.setTemplate_(True)   # follows the menu bar's own light/dark
            item.button().setImage_(img)
        else:
            item.button().setTitle_("suravidl")
        target = _tray_target(Foundation).alloc().init()
        menu = AppKit.NSMenu.alloc().init()
        show_item = AppKit.NSMenuItem.alloc() \
            .initWithTitle_action_keyEquivalent_(
                "Show suravidl", "showWindow:", "")
        show_item.setTarget_(target)
        quit_item = AppKit.NSMenuItem.alloc() \
            .initWithTitle_action_keyEquivalent_(
                "Quit suravidl", "quitApp:", "")
        quit_item.setTarget_(target)
        menu.addItem_(show_item)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        menu.addItem_(quit_item)
        item.setMenu_(menu)
        item.setVisible_(False)
        _TRAY.update(item=item, target=target, window=window, AppKit=AppKit)
        # the item lives exactly as long as the app is tucked away
        try:
            center = Foundation.NSNotificationCenter.defaultCenter()
            center.addObserverForName_object_queue_usingBlock_(
                AppKit.NSApplicationDidHideNotification, None, None,
                lambda _n: item.setVisible_(True))
            center.addObserverForName_object_queue_usingBlock_(
                AppKit.NSApplicationDidUnhideNotification, None, None,
                lambda _n: item.setVisible_(False))
        except Exception:  # noqa: BLE001 - the item still works without
            pass
        return item
    except Exception:  # noqa: BLE001 - no item is not fatal
        return None


def _darwin_minimize_action(window):
    """macOS "−": tuck the whole app away; the menu-bar item brings it back."""

    def tuck():
        AppKit, Foundation = _import_appkit()
        if AppKit is None:
            window.minimize()   # no pyobjc: exactly the old behaviour
            return

        def worker():
            item = (_TRAY.get("item")
                    or _install_tray_item(window, AppKit, Foundation))
            if item is not None:
                item.setVisible_(True)
            # NSApp-level hide, not window.hide(): the Dock icon then
            # restores everything the way every Mac user expects
            AppKit.NSApplication.sharedApplication().hide_(None)

        try:
            _on_main(worker)
        except Exception:  # noqa: BLE001 - last resort, stay useful
            window.minimize()

    return tuck


def _make_window_tray(window):
    """Windows/Linux: a pystray icon whose menu restores the window."""
    try:
        from PIL import Image
        import pystray
    except Exception:  # noqa: BLE001 - tray is optional
        return None
    icon_file = Path(__file__).parent / "web" / "icon.png"
    if not icon_file.exists():
        return None

    def on_show(_icon, _item):
        try:
            window.show()
        except Exception:  # noqa: BLE001 - the window may be gone
            pass

    def on_quit(icon, _item):
        try:
            icon.stop()
        except Exception:  # noqa: BLE001
            pass
        window.destroy()

    menu = pystray.Menu(
        pystray.MenuItem("Show suravidl", on_show, default=True),
        pystray.MenuItem("Quit suravidl", on_quit),
    )
    return pystray.Icon("suravidl", Image.open(icon_file), "suravidl", menu)


def _tray_minimize_action(window):
    """Windows/Linux "−": hide the window; the tray icon puts it back."""

    def tuck():
        icon = _TRAY.get("icon")
        if icon is None:
            icon = _make_window_tray(window)
            if icon is not None:
                try:
                    icon.run_detached()
                except Exception:  # noqa: BLE001 - no tray after all
                    icon = None
                else:
                    _TRAY.update(icon=icon, window=window)
        if icon is None:
            window.minimize()   # no tray: exactly the old behaviour
            return
        try:
            window.hide()
        except Exception:  # noqa: BLE001
            window.minimize()

    return tuck


def _minimize_action(window, tray_ok=True):
    """The action behind the window's "−" button (v0.38.7)."""
    if not tray_ok:
        return window.minimize
    if sys.platform == "darwin":
        return _darwin_minimize_action(window)
    return _tray_minimize_action(window)


# ---------- the motion probe (v0.38.7) ----------
# Two system-level switches can hold every animation still inside a
# WebView: the user asking for reduced motion, and — a WebKit behaviour —
# a page that reports itself hidden (transitions never tick while hidden).
# The probe logs what the page sees, and re-fronts the window once when it
# claims to be hidden: that state is sometimes stuck from launch.


def _motion_probe(window) -> None:
    def read():
        try:
            return window.evaluate_js(
                "(function(){var m=window.matchMedia("
                "'(prefers-reduced-motion: reduce)');"
                "return {v: document.visibilityState, r: m.matches};})()"
            ) or {}
        except Exception:  # noqa: BLE001 - the page may not be up yet
            return {}

    try:
        time.sleep(_MOTION_SETTLE)
    except Exception:  # noqa: BLE001
        pass
    state = read()
    print(f"SURAVIDL_MOTION visibilityState={state.get('v')!r} "
          f"reduced-motion={state.get('r')!r}")
    if state.get("v") != "hidden":
        return
    native = getattr(window, "native", None)
    if native is None or not hasattr(native, "orderFront_"):
        return
    try:
        _on_main(lambda: native.orderFront_(None))
    except Exception:  # noqa: BLE001
        return
    try:
        time.sleep(_MOTION_SETTLE)
    except Exception:  # noqa: BLE001
        pass
    after = read()
    print(f"SURAVIDL_MOTION after nudge: visibilityState={after.get('v')!r}")


def _start_motion_probe(window) -> None:
    """Run the probe off the GUI thread: it sleeps, the app must not."""
    try:
        threading.Thread(target=_motion_probe, args=(window,),
                         daemon=True).start()
    except Exception:  # noqa: BLE001
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
    _hide_child_consoles()
    _ensure_log_targets(Path.home() / ".suravidl" / "app.log")
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

        def _focus_window():
            """Raise the window — a browser handoff just arrived.

            Minimize-to-tray means the window can be hidden (macOS app-hide)
            or iconified (pystray); restore covers both, and on macOS the
            app is also activated so it comes forward over the browser the
            user clicked in.
            """
            try:
                window.restore()
            except Exception:  # noqa: BLE001 - window may be visible already
                pass
            try:
                window.show()
            except Exception:  # noqa: BLE001
                pass
            if sys.platform == "darwin":
                try:
                    from AppKit import NSApplication  # noqa: PLC0415

                    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
                except Exception:  # noqa: BLE001 - pyobjc is best-effort
                    pass

        actions = {"minimize": _minimize_action(window,
                                                tray_ok=not args.no_tray),
                   "quit": window.destroy,
                   "focus": _focus_window,
                   "reveal": _open_folder, "pick_file": _pick_file,
                   "open_url": _open_url}

    server = start_server(download_dir=args.download_dir, token=token, port=port,
                          db_path=args.db, desktop_actions=actions or None,
                          cache_dir=args.cache_dir)
    print(f"suravidl running at {url}  (token: {token[:4]}…{token[-4:]})")

    if window is not None:
        def _ready():
            _native_glass_ready(window)   # runs once the GUI loop is up
            _start_motion_probe(window)   # v0.38.7: log the motion state

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
