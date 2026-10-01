"""v0.38.7 — the tuck (desktop tray minimize) + the motion note.

Two desktop reports (2026-10-01): the window's "−" should tuck the app
away to the tray (menu bar on macOS) instead of the standard Dock
minimize, and the desktop app shows no motion at all.

The tray path is tested behaviourally against fake AppKit / fake pystray:
macOS hides the whole app behind an NSStatusItem (Show/Quit), Windows and
Linux hide the window behind a pystray icon, and every missing piece
degrades to the previous plain minimize. The motion side ships a boot
probe (visibilityState + reduced-motion, logged) with one re-front nudge
when the page claims to be hidden, and a quiet note in Settings →
Appearance that names whichever switch is suppressing motion.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()

from suravidl_engine import __main__ as engine_main


# ---------- fakes: just enough AppKit / Foundation for the tray ----------
class _Rec:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name.endswith("_"):
            def call(*args):
                self.calls.append((name, args))
                return None
            return call
        raise AttributeError(name)


class _FakeImage(_Rec):
    pass


class _FakeButton(_Rec):
    pass


class _FakeStatusItem(_Rec):
    def __init__(self):
        super().__init__()
        self._button = _FakeButton()
        self.visible = None
        self.menu = None

    def button(self):
        return self._button

    def setVisible_(self, v):
        self.visible = bool(v)
        self.calls.append(("setVisible_", (v,)))

    def setMenu_(self, m):
        self.menu = m
        self.calls.append(("setMenu_", (m,)))


class _FakeMenuItem(_Rec):
    def __init__(self, title, action, key):
        super().__init__()
        self.title = title
        self.action = action
        self.key = key
        self.target = None

    def setTarget_(self, t):
        self.target = t


class _FakeMenu(_Rec):
    def __init__(self):
        super().__init__()
        self.items = []

    def addItem_(self, item):
        self.items.append(item)


class _FakeStatusBar:
    def __init__(self):
        self.last = None

    def statusItemWithLength_(self, length):
        self.last = _FakeStatusItem()
        return self.last


class _FakeApp:
    def __init__(self):
        self.hides = 0
        self.unhides = 0
        self.activates = 0

    def hide_(self, _):
        self.hides += 1

    def unhide_(self, _):
        self.unhides += 1

    def activateIgnoringOtherApps_(self, _):
        self.activates += 1


class _FakeAppKit:
    NSVariableStatusItemLength = -1.0
    NSApplicationDidHideNotification = "did-hide"
    NSApplicationDidUnhideNotification = "did-unhide"

    def __init__(self):
        outer = self
        self.statusbar = _FakeStatusBar()
        self.app = _FakeApp()
        self.images = []

        class NSStatusBar:
            @staticmethod
            def systemStatusBar():
                return outer.statusbar
        self.NSStatusBar = NSStatusBar

        class NSImage:
            @staticmethod
            def imageWithSystemSymbolName_accessibilityDescription_(name, desc):
                img = _FakeImage()
                img.symbol = name
                outer.images.append(img)
                return img
        self.NSImage = NSImage

        class NSMenu(_FakeMenu):
            @classmethod
            def alloc(cls):
                return cls()

            def init(self):
                return self
        self.NSMenu = NSMenu

        class NSMenuItem(_FakeMenuItem):
            def __init__(self):
                _FakeMenuItem.__init__(self, None, None, None)

            @classmethod
            def alloc(cls):
                return cls()

            def initWithTitle_action_keyEquivalent_(self, t, a, k):
                self.title, self.action, self.key = t, a, k
                return self

            @staticmethod
            def separatorItem():
                return _FakeMenuItem("-", None, "")
        self.NSMenuItem = NSMenuItem

        class NSApplication:
            @staticmethod
            def sharedApplication():
                return outer.app
        self.NSApplication = NSApplication


class _FakeFoundation:
    class NSObject:
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return self

    class _Center:
        def __init__(self):
            self.observers = []

        def addObserverForName_object_queue_usingBlock_(self, name, obj, q, fn):
            self.observers.append((name, fn))
            return object()

    def __init__(self):
        self.center = _FakeFoundation._Center()

    def NSNotificationCenter(self):  # noqa: N802
        outer = self

        class _NC:
            @staticmethod
            def defaultCenter():
                return outer.center
        return _NC


class _Window:
    """The pywebview window surface the actions actually touch."""

    def __init__(self, native=None):
        self.minimized = 0
        self.hidden = 0
        self.shown = 0
        self.destroyed = 0
        self.native = native

    def minimize(self):
        self.minimized += 1

    def hide(self):
        self.hidden += 1

    def show(self):
        self.shown += 1

    def destroy(self):
        self.destroyed += 1


@pytest.fixture()
def tray_env(monkeypatch):
    """Fake AppKit/Foundation, inline main-thread dispatch, fresh registry."""
    appkit, foundation = _FakeAppKit(), _FakeFoundation()
    monkeypatch.setattr(engine_main, "_TRAY", {})
    monkeypatch.setattr(engine_main, "_on_main", lambda fn: fn())
    monkeypatch.setattr(engine_main, "_import_appkit",
                        lambda: (appkit, foundation))
    return appkit, foundation


# ---------- macOS: − tucks the whole app behind a menu-bar item ----------
def test_darwin_minimize_tucks_and_raises_the_item(tray_env):
    appkit, foundation = tray_env
    win = _Window()
    engine_main._darwin_minimize_action(win)()
    item = engine_main._TRAY.get("item")
    assert item is not None, "the status item must exist after a tuck"
    assert item.visible is True, "the item shows only while tucked away"
    assert appkit.app.hides == 1, "the whole app hides (dock click restores)"
    # the item carries a template image + a real menu
    button_calls = [c[0] for c in item.button().calls]
    assert "setImage_" in button_calls or "setTitle_" in button_calls
    assert appkit.images, "an SF Symbol image was requested"
    assert ("setTemplate_", (True,)) in appkit.images[0].calls
    assert item.menu is not None
    titles = [i.title for i in item.menu.items]
    assert "Show suravidl" in titles and "Quit suravidl" in titles


def test_darwin_show_and_quit_are_wired(tray_env):
    appkit, foundation = tray_env
    win = _Window()
    engine_main._darwin_minimize_action(win)()
    target = engine_main._TRAY.get("target")
    assert target is not None
    target.showWindow_(None)
    assert win.shown == 1 and appkit.app.unhides == 1
    assert engine_main._TRAY["item"].visible is False, "item bows out on show"
    target.quitApp_(None)
    assert win.destroyed == 1


def test_darwin_item_is_created_once(tray_env):
    appkit, _ = tray_env
    win = _Window()
    act = engine_main._darwin_minimize_action(win)
    act()
    first = engine_main._TRAY["item"]
    act()
    assert engine_main._TRAY["item"] is first
    assert appkit.app.hides == 2


def test_no_pyobjc_keeps_the_old_minimize(monkeypatch):
    monkeypatch.setattr(engine_main, "_TRAY", {})
    monkeypatch.setattr(engine_main, "_import_appkit", lambda: (None, None))
    win = _Window()
    engine_main._darwin_minimize_action(win)()
    assert win.minimized == 1, "without pyobjc the − button minimizes as before"


# ---------- Windows/Linux: − hides the window behind a pystray icon ----------
class _FakePystray:
    def __init__(self):
        self.icons = []

        outer = self

        class Item:
            def __init__(self, text, action, default=False):
                self.text = text
                self.action = action
                self.default = default

        class Menu:
            def __init__(self, *items):
                self.items = items

        class Icon:
            def __init__(self, name, image, title, menu):
                self.name, self.image, self.title, self.menu = name, image, title, menu
                self.detached = 0
                self.stopped = 0
                outer.icons.append(self)

            def run_detached(self):
                self.detached += 1

            def stop(self):
                self.stopped += 1

        self.MenuItem = Item
        self.Menu = Menu
        self.Icon = Icon


@pytest.fixture()
def pystray_env(monkeypatch):
    import types

    fake = _FakePystray()
    fake_pil = types.ModuleType("PIL")
    fake_img = types.ModuleType("PIL.Image")
    fake_img.open = lambda path: ("img", str(path))
    fake_pil.Image = fake_img
    monkeypatch.setitem(sys.modules, "pystray", fake)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_img)
    monkeypatch.setattr(engine_main, "_TRAY", {})
    return fake


def test_windows_minimize_hides_behind_the_tray(pystray_env):
    win = _Window()
    act = engine_main._tray_minimize_action(win)
    act()
    icons = pystray_env.icons
    assert len(icons) == 1 and icons[0].detached == 1
    assert win.hidden == 1, "the window hides behind the icon"
    act()  # second tuck reuses the icon
    assert len(pystray_env.icons) == 1


def test_tray_show_and_quit_are_wired(pystray_env):
    win = _Window()
    engine_main._tray_minimize_action(win)()
    icon = pystray_env.icons[0]
    items = {i.text: i for i in icon.menu.items}
    items["Show suravidl"].action(icon, None)
    assert win.shown == 1
    items["Quit suravidl"].action(icon, None)
    assert icon.stopped == 1 and win.destroyed == 1


def test_no_tray_available_falls_back_to_minimize(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)  # import raises
    monkeypatch.setattr(engine_main, "_TRAY", {})
    win = _Window()
    engine_main._tray_minimize_action(win)()
    assert win.minimized == 1


def test_minimize_action_routes_per_platform(monkeypatch):
    win = _Window()
    assert engine_main._minimize_action(win, tray_ok=False) == win.minimize


# ---------- the motion probe: read it, log it, nudge once if hidden ----------
class _ProbeWindow(_Window):
    def __init__(self, states):
        super().__init__(native=_Rec())
        self._states = list(states)
        self.scripts = []

    def evaluate_js(self, script):
        self.scripts.append(script)
        return self._states.pop(0)


def test_motion_probe_logs_state(monkeypatch, capsys):
    monkeypatch.setattr(engine_main, "_MOTION_SETTLE", 0)
    win = _ProbeWindow([{"v": "visible", "r": False}])
    engine_main._motion_probe(win)
    out = capsys.readouterr().out
    assert "visibilityState" in out and "visible" in out
    assert not win.native.calls, "no nudge when the page is visible"


def test_motion_probe_nudges_when_hidden(monkeypatch, capsys):
    monkeypatch.setattr(engine_main, "_MOTION_SETTLE", 0)
    win = _ProbeWindow([{"v": "hidden", "r": False},
                        {"v": "visible", "r": False}])
    engine_main._motion_probe(win)
    out = capsys.readouterr().out
    assert "orderFront_" in [c[0] for c in win.native.calls]
    assert "after nudge" in out and "visible" in out


def test_probe_script_reads_both_switches():
    src = MAIN[MAIN.find("def _motion_probe"):]
    src = src[:src.find("\ndef ")]
    assert "visibilityState" in src
    assert "prefers-reduced-motion" in src


def test_ready_path_starts_the_probe_and_wires_the_action():
    assert "_start_motion_probe(window)" in MAIN
    assert "threading.Thread" in MAIN
    assert '"minimize": _minimize_action(window' in MAIN


# ---------- the UI side: label, the note, its wiring ----------
def test_minimize_button_says_what_it_does():
    i = HTML.find('id="minBtn"')
    assert 'aria-label="Minimize to tray"' in HTML[i:i + 300]
    assert 'title="Minimize to tray"' in HTML[i:i + 300]


def test_the_motion_note_lives_in_appearance():
    assert 'id="motionNote"' in HTML
    i = HTML.find('id="motionNote"')
    assert "hidden" in HTML[i:i + 120]
    assert HTML.find('id="schemeSwatches"') < i < HTML.find('id="setDir"')


def test_motion_note_reads_both_switches_and_is_wired():
    assert "function wireMotionNote" in APP
    assert "wireMotionNote()" in APP
    fn = APP[APP.find("function wireMotionNote"):]
    fn = fn[:fn.find("\nfunction ")]
    assert "prefers-reduced-motion" in fn
    assert "visibilityState" in fn
    assert "Reduce motion" in fn
    assert "addEventListener" in fn
