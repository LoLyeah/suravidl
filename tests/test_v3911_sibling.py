"""v0.39.11: the sibling — the glass may never be a child of the page.

The screenshot that said "I can't see anything LOL" (2026-10-02, the
user's mac, v0.39.10): the whole desktop UI a blurry slab. The walkabout
made the native glass insert for the FIRST time — and exposed a geometry
bug from v0.38.4 that could never manifest before: pywebview makes the
WKWebView the contentView, so `content` and the webview are the SAME view
and `addSubview(below: webview)` degenerates into parenting the glass
INSIDE the webview — AppKit draws it over the page.

Fix: host the material in the webview's own SUPERVIEW (always a real
parent), framed to the webview's own frame. The probe serves its page
over a real URL too, because inline html loads may never trigger the
navigation that parents the webview (the probe's walk kept MISSing).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()
PROBE = (ROOT / "scripts" / "mac_motion_probe.py").read_text()
WHATSNEW = (ROOT / "src" / "suravidl_engine" / "whatsnew.py").read_text()

from suravidl_engine import __main__ as engine_main


class _FakeView:
    def __init__(self, name="NSView"):
        self.name = name
        self._subviews = []
        self._superview = None
        self._frame = None              # AppKit exposes frame() as a method
        self.added = []
        self.kv = {}

    def subviews(self):
        return list(self._subviews)

    def superview(self):
        return self._superview

    def frame(self):
        return self._frame

    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self

    def setFrame_(self, frame):
        self._frame = frame

    def setMaterial_(self, m):
        self.material = m

    def setBlendingMode_(self, b):
        self.blending = b

    def setState_(self, s):
        self.state = s

    def setAppearance_(self, a):
        self.appearance = a

    def addSubview_positioned_relativeTo_(self, sub, pos, rel):
        self.added.append((sub, pos, rel))

    def setValue_forKey_(self, v, k):
        self.kv[k] = v


class _FakeNative:
    def __init__(self, content):
        self._content = content

    def contentView(self):
        return self._content


class _FakeWindow:
    def __init__(self, native):
        self.native = native
        self.js = []

    def evaluate_js(self, code):
        self.js.append(code)
        return "dark"


def _fake_appkit(with_glass=True):
    class AppKit:
        NSWindowBelow = -1
        NSVisualEffectMaterialUnderWindowBackground = 6
        NSVisualEffectBlendingModeBehindWindow = 2
        NSVisualEffectStateActive = 1

    AppKit.NSVisualEffectView = type("NSVisualEffectView", (_FakeView,), {})
    AppKit.NSGlassEffectView = (
        type("NSGlassEffectView", (_FakeView,), {}) if with_glass else None)
    return AppKit


def test_the_material_is_a_sibling_hosted_in_the_webviews_parent():
    # the real mac shell: pywebview makes the WKWebView the contentView
    theme = _FakeView("NSThemeFrame")
    inner = type("WKWebView", (_FakeView,), {})()
    inner.setFrame_((0, 0, 800, 600))
    inner._superview = theme
    window = _FakeWindow(_FakeNative(inner))

    assert engine_main._install_material(window, _fake_appkit(True), None) is True
    assert theme.added and theme.added[0][2] is inner   # below the webview
    assert not inner.added                              # NEVER inside it
    assert theme.added[0][0].frame() == (0, 0, 800, 600)  # the webview's frame


def test_no_parent_means_no_material():
    inner = type("WKWebView", (_FakeView,), {})()   # no superview wired
    window = _FakeWindow(_FakeNative(inner))
    assert engine_main._install_material(window, _fake_appkit(True), None) is False


def test_the_code_pins_the_sibling_geometry():
    assert "webview_view.superview()" in MAIN
    assert "webview_view.frame()" in MAIN


def test_the_probe_serves_a_real_url():
    # inline html loads may never trigger the parenting navigation
    assert "ThreadingHTTPServer" in PROBE
    assert '"suravidl motion probe", url,' in PROBE


def test_whatsnew_has_the_sibling():
    assert '"version": "0.39.11"' in WHATSNEW
    assert "The sibling" in WHATSNEW