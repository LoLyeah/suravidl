"""Desktop entry: serve the engine, open it in a standalone window.

Falls back to the browser when no webview runtime is available (e.g. a
headless server, or a Linux frozen build without GTK bindings).
Runnable as `python -m suravidl_engine` or as a PyInstaller-frozen binary.
"""
import argparse
import base64
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


_ENGINE_PORT = 8787
_PORT_LADDER_SPAN = 5      # the engine may sit on 8787..8792 — see PORT_LADDER
                           # in extension/background.js; a test pins both sides


def _port_candidates(preferred: int) -> list[int]:
    """The fixed ladder the engine is allowed to sit on: the preferred port,
    then its neighbours. Never a random port — the extension walks the same
    ladder to find the app (the "suravidl isn't running" bug: a busy 8787
    used to move the engine somewhere nothing would ever look)."""
    return list(range(preferred, preferred + _PORT_LADDER_SPAN + 1))


def find_free_port(preferred: int) -> int:
    """First free port on the ladder, else whichever the OS offers."""
    def bindable(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return True
            except OSError:
                return False

    if preferred != 0:
        for p in _port_candidates(preferred):
            if bindable(p):
                return p
    # port 0 asked for, or six engines on one machine: any free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def token_path() -> Path:
    return Path.home() / ".suravidl" / "token"


def load_or_create_token() -> str:
    """The engine's token: `SURAVIDL_TOKEN` when set, else the token file.

    An env var that is set is a decision: it wins, and it is never written
    to disk. Both entry points honour it — the README documents pinning a
    token this way.
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
    # born 0600 (v0.43.2 audit): a write-then-chmod pair leaves a window in
    # which a watcher on the same machine can read the token
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(t)
    _harden(p, 0o600)   # belt: an exotic umask or filesystem may need it
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
    # v0.43.0: a staged yt-dlp update (the PyPI wheel copy) must be ahead of
    # the bundled one on sys.path BEFORE anything imports yt_dlp — the sweep
    # right below imports the updater, and the updater imports yt_dlp.
    try:
        from .ytdlp_update import activate_safe

        activate_safe(db_path)
    except Exception:  # noqa: BLE001 - a boot must never fail here
        pass
    # a previous session's staged update can never be applied again (its
    # state died with that process) — clear it before serving; this also
    # cleans up right after a self-update on every platform that stages
    # into the cache (v0.42.1)
    try:
        from .updater import sweep_stale_downloads
        sweep_stale_downloads()
    except Exception:  # noqa: BLE001 - housekeeping must never block a boot
        pass
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
    """Depth-first: the WKWebView pywebview wrapped (its own container first).

    pywebview wraps WKWebView in a `WebKitHost` subclass (v6.2.1), so the
    name check alone never matched and the native material silently never
    inserted (caught by the mac motion probe, v0.39.9). Match the class
    itself — isKindOfClass covers every wrapper — and keep the name check
    as the fallback for the odd shell where the bridge can't look it up."""
    wk = None
    try:
        import objc

        wk = objc.lookUpClass("WKWebView")
    except Exception:  # noqa: BLE001 - no bridge: the name check decides
        pass

    def _match(view):
        return (wk is not None and view.isKindOfClass_(wk)) or (
            type(view).__name__ == "WKWebView")

    def _bfs(node):
        stack = [node]
        while stack:
            view = stack.pop(0)
            if view is not None and _match(view):
                return view
            try:
                stack.extend(view.subviews())
            except Exception:  # noqa: BLE001 - dead view: keep walking
                pass
        return None

    view = _bfs(root)
    if view is not None:
        return view
    # climb (v0.39.10): some shells keep the webview above the contentView
    node, hops = root, 0
    while hops < 3:
        try:
            node = node.superview()
        except Exception:  # noqa: BLE001 - no parent: the walk is done
            return None
        if node is None:
            return None
        hops += 1
        view = _bfs(node)
        if view is not None:
            return view
    return None


MATERIAL_ID = "suravidl.material"   # how a dressed window is recognized
_MATERIAL_LOCK = threading.Lock()   # at most one insert in flight, ever


def _find_material(root):
    """A material view this window already carries, if any — idempotency by
    observation (v0.39.11). An `id()`-keyed set was the first shape, and
    CPython reuses the ids of freed objects, so a brand-new window could be
    mistaken for a dressed one. The hierarchy does not lie.

    v0.39.12: the match is OUR identifier, not a class name — every titled
    NSWindow carries an NSVisualEffectView for its titlebar, and the first
    class-name scan mistook that vibrancy for a dressed window and skipped
    the insert (page transparent, nothing behind it)."""
    stack = [root]
    while stack:
        view = stack.pop(0)
        try:
            if view.identifier() == MATERIAL_ID:
                return view
        except Exception:  # noqa: BLE001 - cannot answer: walk on
            pass
        try:
            stack.extend(view.subviews())
        except Exception:  # noqa: BLE001 - dead view: keep walking
            pass
    return None


def _install_material(window, AppKit, Foundation) -> bool:
    """Insert a real native material behind the page content.

    NSGlassEffectView is Apple's Liquid Glass material (macOS 26+). Older
    systems get the long-established NSVisualEffectView vibrancy in
    behind-window mode — the material the UI's 'frosted' theme imitates.
    Returns True when a layer was actually inserted (or already sits
    there). Idempotent (v0.39.10): the dressing runs on every `loaded`,
    and a second layer behind the page would just stack glass.

    v0.39.12, the audit: the AppKit mutations ride the main thread (view
    allocation and addSubview off-main is how intermittent crashes and
    silent drawing failures start); the JS reads stay on this worker
    thread (evaluate_js marshals to the main loop and waits, so calling it
    on that loop would deadlock); the material tracks resizes; and it
    carries an identifier of our own — a class-name scan had mistaken the
    titlebar's vibrancy view for a dressed window and skipped every insert.
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
        # The material must be a SIBLING of the webview, never a child:
        # pywebview makes the WKWebView the contentView, so `content` can BE
        # the webview — addSubview(below: self) degenerates and the glass
        # covers the page (the "I can't see anything" report, v0.39.10's
        # first-ever real insert). Host it in the webview's own superview.
        host = None
        try:
            host = webview_view.superview()
        except Exception:  # noqa: BLE001 - no parent: nothing to host in
            host = None
        if host is None:
            return False
        if _find_material(host) is not None:
            return True   # dressed already — never stack a second layer
        frame = webview_view.frame()
        theme = "dark"
        try:
            # follow the page's theme at launch (a mid-session theme switch
            # keeps the material it was born with — restart to re-sync)
            theme = window.evaluate_js(
                'document.documentElement.dataset.theme') or "dark"
        except Exception:  # noqa: BLE001 - the default stands
            pass
        named = ("NSAppearanceNameDarkAqua"
                 if theme in ("dark", "amoled") else "NSAppearanceNameAqua")
        if not _MATERIAL_LOCK.acquire(blocking=False):
            return True   # an insert is already in flight for this window

        def perform():
            """The AppKit half, on the main thread. No JS from in here: it
            would wait on a main loop that is running this very call."""
            try:
                material = glass_cls.alloc().init()
                if glass_cls is AppKit.NSVisualEffectView:
                    material.setMaterial_(
                        AppKit.NSVisualEffectMaterialUnderWindowBackground)
                    material.setBlendingMode_(
                        AppKit.NSVisualEffectBlendingModeBehindWindow)
                    material.setState_(AppKit.NSVisualEffectStateActive)
                try:
                    material.setIdentifier_(MATERIAL_ID)
                except Exception:  # noqa: BLE001 - the lock still guards us
                    pass
                try:
                    # track the webview on resize: a bare NSView is not
                    # sizable by default, and the glass used to freeze at
                    # boot geometry while the page resized past it
                    material.setAutoresizingMask_(
                        getattr(AppKit, "NSViewWidthSizable", 2)
                        | getattr(AppKit, "NSViewHeightSizable", 16))
                except Exception:  # noqa: BLE001 - decoration
                    pass
                material.setFrame_(frame)
                host.addSubview_positioned_relativeTo_(
                    material, AppKit.NSWindowBelow, webview_view)
                try:
                    # the page composites over the material instead of a
                    # white box
                    webview_view.setValue_forKey_(False, "drawsBackground")
                except Exception:  # noqa: BLE001 - private-ish KVC key
                    pass
                try:
                    material.setAppearance_(
                        AppKit.NSAppearance.appearanceNamed_(named))
                except Exception:  # noqa: BLE001 - decoration, never fatal
                    pass
            except Exception:  # noqa: BLE001 - unknown shells: stay plain
                pass
            finally:
                try:
                    _MATERIAL_LOCK.release()
                except Exception:  # noqa: BLE001
                    pass

        try:
            _on_main(perform)
        except Exception:  # noqa: BLE001 - never leave the lock held
            try:
                _MATERIAL_LOCK.release()
            except Exception:  # noqa: BLE001
                pass
            return False
        return True
    except Exception:  # noqa: BLE001 - unknown shells: stay plain
        return False


def _apply_native_material(window) -> bool:
    """macOS only: the real glass. Windows and Linux keep their own look."""
    if sys.platform != "darwin":
        return False
    AppKit, Foundation = _import_appkit()
    return _install_material(window, AppKit, Foundation)


_CALM_DONE = False   # the flip is a once-per-process affair (v0.39.12)


def _calm_page_visibility(window) -> bool:
    """macOS only, v0.39.9 "the calm": tell WKWebView to stop deciding the
    view is hidden.

    The mac motion probe caught it: the app's page reports
    `document.visibilityState === 'hidden'` while the OS says the window is
    VISIBLE and rAF still ticks — and WebKit skips CSS transitions in
    hidden documents, so every animation jumps to its end state (the v0.38.7
    "no animation" report). The field-proven cure (the Sonoma screensaver
    fix, liquidx/webviewscreensaver) is the WKWebView SPI
    `_setWindowOcclusionDetectionEnabled: NO`. PyObjC hides underscore
    selectors, so the call goes through ctypes objc_msgSend — gated by
    respondsToSelector, darwin-only, and a throw may never take the
    window down (the v0.39.7 law).

    v0.39.12, the audit: the flip stops FUTURE occlusion tracking, but a
    page WebKit already marked hidden stays hidden until the window is
    ordered in again — so the flip is followed by a nudge (orderFront_), it
    all rides the main thread (AppKit belongs there), the objc library
    lookup walks a ladder (find_library can answer None in frozen bundles),
    and it happens exactly once per process."""
    global _CALM_DONE
    if sys.platform != "darwin" or _CALM_DONE:
        return False
    try:
        native = getattr(window, "native", None)
        if native is None:
            return False
        content = native.contentView()
        wk = _find_webview_view(content)
        if wk is None:
            return False
        selector = "_setWindowOcclusionDetectionEnabled:"
        if not wk.respondsToSelector_(selector):
            return False
        import ctypes
        import ctypes.util
        import objc

        lib = None
        for attempt in (lambda: ctypes.CDLL(None),
                        lambda: ctypes.cdll.LoadLibrary(
                            ctypes.util.find_library("objc") or ""),
                        lambda: ctypes.cdll.LoadLibrary(
                            "/usr/lib/libobjc.A.dylib")):
            try:
                lib = attempt()
                break
            except Exception:  # noqa: BLE001 - try the next address
                lib = None
        if lib is None:
            return False
        send = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool,
        )(("objc_msgSend", lib))
        reg = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(
            ("sel_registerName", lib))

        def _flip():
            global _CALM_DONE
            try:
                send(objc.pyobjc_id(wk), reg(selector.encode()), False)
            except Exception:  # noqa: BLE001
                pass
            finally:
                _CALM_DONE = True
            # detection off is not retroactive: make the window re-enter
            # its own visibility evaluation
            nudge = getattr(native, "orderFront_", None)
            if nudge is not None:
                try:
                    nudge(None)
                except Exception:  # noqa: BLE001
                    pass

        _on_main(_flip)
        return True
    except Exception:  # noqa: BLE001 - a calm attempt never kills the shell
        return False


def _dress(window) -> None:
    """Calm + material, (re)applied whenever the page lands (v0.39.10).

    pywebview parents the WKWebView into the window only when the FIRST
    navigation finishes (`webView_didFinishNavigation_` ->
    `setContentView_`), so dressing at GUI-start walked an empty hierarchy
    and both the calm and the glass silently no-op'd — the walkabout the
    mac probe caught. The `loaded` event is the moment the view exists;
    it can fire again (reload), so every step is idempotent."""
    try:
        _calm_page_visibility(window)
        if _apply_native_material(window):
            # the body steps aside so the native material shows through
            window.evaluate_js(
                'document.documentElement.dataset.host = "darwin-glass"; true')
    except Exception:  # noqa: BLE001 - the plain window still works
        pass


def _native_glass_ready(window) -> None:
    """webview.start callback: window.native exists only after the GUI is up."""
    try:
        # the webview is parented at first-load, not at GUI-start (v0.39.10);
        # some shells (and the test fixtures) carry no events object at all
        events = getattr(window, "events", None)
        if events is not None:
            events.loaded += lambda *_: _dress(window)
        _dress(window)   # and once now, in case the page is already in
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


# ---------- the tally (v0.40.6) ----------
# The queue should be readable from outside the window: macOS paints the
# Dock tile's badge label, Linux docks that speak Unity's LauncherEntry
# protocol get a count, and everything else wears it in the window title.
# A failed read is silence — never a crash, and never a zero: "unknown"
# must not clear a truthful badge.

_BADGE_EVERY = 2.5       # seconds between queue reads
_BADGE = {"last": None}  # the last count we painted
_BADGE_ENTRY = "suravidl.desktop"   # the launcher entry (the app's own id)


def badge_text(active: int) -> str:
    """The label: "" clears, small counts go verbatim, 100+ caps at 99+."""
    if active <= 0:
        return ""
    if active > 99:
        return "99+"
    return str(active)


def active_count(jobs) -> int:
    """Going jobs only — the same three words the engine and the page use."""
    from .jobs import ACTIVE_STATUSES

    return sum(1 for j in jobs
               if (j.get("status") or "") in ACTIVE_STATUSES)


def title_for(active: int, base: str = "suravidl") -> str:
    """The floor: the title says it where no badge exists."""
    text = badge_text(active)
    if not text:
        return base
    return f"{base} — {text} job" if active == 1 else f"{base} — {text} jobs"


def read_active(base_url: str, token: str, timeout: float = 3.0):
    """How many jobs are going, straight from the engine; None when the
    answer is not knowable (engine busy, port gone, auth refused)."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            base_url.rstrip("/") + "/jobs",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if isinstance(jobs, list):
            return active_count(jobs)
    except Exception:  # noqa: BLE001 - a badge is never worth a crash
        pass
    return None


def _set_dock_badge(text: str) -> bool:
    """macOS: the Dock tile's own label; "" clears it (None to AppKit)."""
    AppKit, _Foundation = _import_appkit()
    if AppKit is None:
        return False

    def paint():
        try:
            AppKit.NSApplication.sharedApplication() \
                .dockTile().setBadgeLabel_(text or None)
        except Exception:  # noqa: BLE001 - a decoration may never crash us
            pass

    _on_main(paint)   # AppKit state rides the main thread
    return True


def _set_launcher_badge(active: int) -> bool:
    """Linux docks that speak Unity's LauncherEntry protocol get a count;
    everywhere else (no dbus bindings, no session bus, no dock) this
    reports False and the title carries it instead."""
    try:
        import dbus  # noqa: PLC0415 - optional on every platform
    except Exception:  # noqa: BLE001 - no bindings, no badge
        return False
    try:
        bus = dbus.SessionBus()
        launcher = dbus.Interface(
            bus.get_object("com.canonical.Unity", "/"),
            "com.canonical.Unity.LauncherEntry")
        launcher.Update(_BADGE_ENTRY, {
            "count": dbus.Int64(active),
            "count-visible": dbus.Boolean(active > 0)})
        return True
    except Exception:  # noqa: BLE001 - no dock listening: title it is
        return False


def _apply_badge(window, active: int) -> None:
    """Put the count where this platform keeps it; the title is the floor."""
    text = badge_text(active)
    try:
        if sys.platform == "darwin" and _set_dock_badge(text):
            return
        if sys.platform.startswith("linux") and _set_launcher_badge(active):
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        window.title = title_for(active)
    except Exception:  # noqa: BLE001 - the window may be gone
        pass


def _badge_once(window, base_url: str, token: str) -> None:
    """One read, one re-dress — split out so a test can take one step."""
    active = read_active(base_url, token)
    if active is None or active == _BADGE["last"]:
        return
    _BADGE["last"] = active
    _apply_badge(window, active)


def _badge_watch(window, base_url: str, token: str) -> None:
    while True:
        try:
            _badge_once(window, base_url, token)
        except Exception:  # noqa: BLE001 - the watch never dies
            pass
        time.sleep(_BADGE_EVERY)


def _start_badge_poller(window, base_url: str, token: str) -> None:
    """Run the watch off the GUI thread: it sleeps, the app must not."""
    try:
        threading.Thread(target=_badge_watch, args=(window, base_url, token),
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


# ---------- the front door (v0.40.9) ----------
# The AppImage and the Windows exe run from wherever the user put them —
# they show up in no menu at all. One flag puts them there: a desktop entry
# in the user's XDG dirs on Linux (the tally's launcher id, suravidl.desktop,
# is exactly this file's name), a Start Menu shortcut on Windows. Nothing
# outside the user's own folders, no sudo, and installing never boots the
# engine: this is plumbing, not a run.

def app_launch_paths() -> tuple[str, str]:
    """(target, arguments) for a menu entry that points back at this app."""
    if os.environ.get("APPIMAGE"):
        return os.environ["APPIMAGE"], ""          # an AppImage knows itself
    if getattr(sys, "frozen", False):
        return sys.executable, ""                  # the one-file build
    return sys.executable, "-m suravidl_engine"    # a source checkout


def desktop_entry_text(target: str, arguments: str = "") -> str:
    """The freedesktop launcher file, written out in full."""
    exec_line = f'"{target}"'
    if arguments:
        exec_line += f" {arguments}"
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=suravidl",
        "Comment=Universal web video downloader",
        f"Exec={exec_line}",
        "Icon=suravidl",
        "Terminal=false",
        "Categories=AudioVideo;Network;",
        "",
    ])


def _applications_dir(home: Path) -> Path:
    return home / ".local" / "share" / "applications"


def _icon_dir(home: Path) -> Path:
    # the shipped tile is 128x128; it is installed as exactly that size
    return home / ".local" / "share" / "icons" / "hicolor" / "128x128" / "apps"


def install_desktop_entry(home: Path | None = None) -> list[Path]:
    """Write the launcher entry + icon; returns what was written."""
    home = home or Path.home()
    target, arguments = app_launch_paths()
    written: list[Path] = []
    entry = _applications_dir(home) / "suravidl.desktop"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(desktop_entry_text(target, arguments))
    written.append(entry)
    icon_src = Path(__file__).parent / "web" / "icon.png"
    if icon_src.exists():
        icon_dst = _icon_dir(home) / "suravidl.png"
        icon_dst.parent.mkdir(parents=True, exist_ok=True)
        icon_dst.write_bytes(icon_src.read_bytes())
        written.append(icon_dst)
    return written


def remove_desktop_entry(home: Path | None = None) -> list[Path]:
    """Take the entry + icon back out; silence when they were never there."""
    home = home or Path.home()
    removed: list[Path] = []
    for path in (_applications_dir(home) / "suravidl.desktop",
                 _icon_dir(home) / "suravidl.png"):
        try:
            path.unlink()
            removed.append(path)
        except FileNotFoundError:
            pass
    return removed


def _refresh_desktop_db(apps_dir: Path) -> None:
    """Let the desktop notice immediately; the cache is optional."""
    import shutil
    import subprocess

    tool = shutil.which("update-desktop-database")
    if not tool:
        return
    try:
        subprocess.run([tool, str(apps_dir)], check=False,
                       capture_output=True, timeout=10)
    except Exception:  # noqa: BLE001 - a stale cache, nothing more
        pass


def _ps_quote(text) -> str:
    """PowerShell single-quoted literal: an apostrophe doubles."""
    return "'" + str(text).replace("'", "''") + "'"


def windows_shortcut_command(lnk_path, target: str,
                             arguments: str = "") -> list[str]:
    """The PowerShell that stamps a .lnk — present on every Windows."""
    steps = [
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        + _ps_quote(lnk_path) + ")",
        "$s.TargetPath = " + _ps_quote(target),
    ]
    if arguments:
        steps.append("$s.Arguments = " + _ps_quote(arguments))
    steps.append("$s.IconLocation = " + _ps_quote(str(target) + ",0"))
    steps.append("$s.Save()")
    return ["powershell", "-NoProfile", "-NonInteractive",
            "-Command", "; ".join(steps)]


def start_menu_programs_dir(roaming) -> Path:
    """Where per-user Start Menu shortcuts live, under %APPDATA%."""
    return (Path(roaming) / "Microsoft" / "Windows" / "Start Menu" / "Programs")


def _desktop_install_cli(uninstall: bool) -> int:
    """--install-desktop / --uninstall-desktop, per platform, no engine."""
    import subprocess

    if sys.platform == "darwin":
        print("On macOS, the dmg window puts suravidl.app in Applications —"
              " that is already the menu. Nothing to install here.")
        return 0

    if sys.platform == "win32":
        roaming = os.environ.get("APPDATA")
        base = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
        lnk = start_menu_programs_dir(base) / "suravidl.lnk"
        if uninstall:
            try:
                lnk.unlink()
                print(f"removed {lnk}")
            except FileNotFoundError:
                print("suravidl is not in the Start Menu — nothing to remove.")
            return 0
        target, arguments = app_launch_paths()
        lnk.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(windows_shortcut_command(lnk, target, arguments),
                                capture_output=True, text=True)
        if result.returncode != 0:
            print("could not create the shortcut — creating one by hand works"
                  " too (right-click suravidl.exe → Send to → Desktop).")
            return 1
        print(f"suravidl is in the Start Menu now — find it any time. ({lnk})")
        return 0

    # linux: the XDG story
    if uninstall:
        gone = remove_desktop_entry()
        _refresh_desktop_db(_applications_dir(Path.home()))
        print("suravidl left your applications menu."
              if gone else "suravidl was not in your applications menu.")
        return 0
    written = install_desktop_entry()
    _refresh_desktop_db(_applications_dir(Path.home()))
    print("suravidl is in your applications menu now — launch it from there"
          f" any time. ({written[0]})")
    return 0


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


def _windows_apply_command(installer: str, relaunch: str | None) -> list[str]:
    """The silent-upgrade invocation the courier rides (v0.41.0; v0.43.2).

    A detached PowerShell script, base64-encoded (`-EncodedCommand`). The
    v0.41 chain handed cmd.exe a multi-command string, and subprocess on
    Windows re-quotes such strings for CreateProcess — the embedded quotes
    come out `\\"`, which cmd does not parse as quoting, so every path
    boundary was a parsing edge: a `&` in %LOCALAPPDATA% broke the chain,
    and a hostile asset NAME could have ridden the gaps (audit). As one
    opaque ASCII argument there is nothing left to re-quote — UTF-16LE
    base64 survives any username, path metacharacter or locale.

    The script preserves the chain's promises: a short wait lets THIS
    process die and hand back its file locks; the installer runs silent
    (no wizard, no restart prompt, it closes stragglers through the
    Restart Manager); the spent setup is deleted the moment the installer
    exits; and even a failed install brings the app back up (statements
    run in order regardless of any one step's outcome).
    """

    def q(s: str) -> str:
        # PowerShell single-quoted literal: '' is the only escape it has
        return "'" + s.replace("'", "''") + "'"

    lines = [
        "$ErrorActionPreference = 'SilentlyContinue'",
        # the wait is Start-Sleep, not ping/timeout: a detached process has
        # no console, and timeout.exe exits instantly without one (v0.41.x
        # audit, finding 10)
        "Start-Sleep -Seconds 2   # let the app exit and drop its file locks",
        f"Start-Process -FilePath {q(installer)} "
        "-ArgumentList '/SILENT','/SP-','/NORESTART','/CLOSEAPPLICATIONS' -Wait",
        f"Remove-Item -LiteralPath {q(installer)} -Force",
    ]
    if relaunch:
        lines.append(f"Start-Process -FilePath {q(relaunch)}")
    script = "\r\n".join(lines)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive",
            "-EncodedCommand", encoded]


def _installed_exe() -> str | None:
    """Where the per-user installer puts the app ("" until it ran once)."""
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if not local:
        return None
    return str(Path(local) / "Programs" / "suravidl" / "suravidl.exe")


def _make_apply_update_action(window):
    """The desktop_actions["apply_update"] the courier's /update/apply calls.

    Spawns the staged updater DETACHED (it must outlive us), then destroys
    the window so the app exits and lets its files go — on Windows the
    silent installer, on macOS the bundle-swap script. A refusal with a
    REASON (a translocated or read-only copy) comes back as a string for
    the UI to put into words; everywhere else the action honestly refuses.
    """
    def _apply_update(installer_path=None):
        if not installer_path:
            return False
        staged = str(installer_path)
        if not Path(staged).is_file():
            return False
        import subprocess

        if os.name == "nt":
            cmd = _windows_apply_command(staged, _installed_exe())
            try:
                subprocess.Popen(
                    cmd, close_fds=True,
                    # DETACHED_PROCESS | CREATE_NO_WINDOW: the upgrade keeps
                    # running after this process (and its console) is gone
                    creationflags=0x00000008 | 0x08000000)
            except Exception:  # noqa: BLE001 - the UI reports nothing staged ran
                return False
            window.destroy()   # hand the locks back; the chain does the rest
            return True

        if sys.platform == "darwin":
            from .updater import (app_bundle_from, macos_apply_command,
                                  macos_apply_refusal)
            bundle = app_bundle_from(sys.executable)
            if bundle is None:
                return False
            why = macos_apply_refusal(bundle)
            if why:
                return why   # the UI says this verbatim (translocated etc.)
            cmd = macos_apply_command(bundle, staged, os.getpid())
            try:
                # start_new_session: the swap must keep running after we
                # die — it IS waiting for exactly that (v0.42.0)
                subprocess.Popen(cmd, close_fds=True, start_new_session=True,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except Exception:  # noqa: BLE001
                return False
            window.destroy()   # the script waits for this pid to go
            return True

        return False

    return _apply_update


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
    p.add_argument("--install-desktop", action="store_true",
                   help="put suravidl in your applications menu / Start Menu")
    p.add_argument("--uninstall-desktop", action="store_true",
                   help="take suravidl back out of the menu")
    p.add_argument("--selftest", action="store_true",
                   help="boot, verify /health, exit (CI)")
    args = p.parse_args()

    # v0.43.0: a staged yt-dlp update goes ahead of the bundled copy before
    # any lazy import can reach yt_dlp (start_server does it again; cheap)
    try:
        from .ytdlp_update import activate_safe

        activate_safe(args.db)
    except Exception:  # noqa: BLE001 - never block a launch
        pass

    if args.install_desktop or args.uninstall_desktop:
        # plumbing, not a run: no token, no port, no window
        sys.exit(_desktop_install_cli(uninstall=args.uninstall_desktop))

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
                def _activate():
                    """AppKit state belongs on the main thread — this runs
                    on an HTTP worker (the audit)."""
                    try:
                        from AppKit import NSApplication  # noqa: PLC0415

                        NSApplication.sharedApplication().activateIgnoringOtherApps_(
                            True)
                    except Exception:  # noqa: BLE001 - pyobjc is best-effort
                        pass

                _on_main(_activate)

        actions = {"minimize": _minimize_action(window,
                                                tray_ok=not args.no_tray),
                   "quit": window.destroy,
                   "focus": _focus_window,
                   "reveal": _open_folder, "pick_file": _pick_file,
                   "open_url": _open_url,
                   "apply_update": _make_apply_update_action(window)}

    server = start_server(download_dir=args.download_dir, token=token, port=port,
                          db_path=args.db, desktop_actions=actions or None,
                          cache_dir=args.cache_dir)
    print(f"suravidl running at {url}  (token: {token[:4]}…{token[-4:]})")

    if window is not None:
        def _ready():
            _native_glass_ready(window)   # runs once the GUI loop is up
            _start_motion_probe(window)   # v0.38.7: log the motion state
            _start_badge_poller(window, url, token)   # v0.40.6: the tally

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
