"""v0.39.12 "the comb" — the agy motion audit, confirmed finding by finding.

An external audit (agy, 2026-10-03) combed the motion system: the desktop
shell's calm/material machinery, the UI's transitions, and the mac motion
probe itself. Every finding arrived as a hypothesis; these tests pin the
ones that survived confirmation against the real tree — and each names the
failure it prevents. The two run-4 probe symptoms ("webview walk: MISS",
"available: ?") turned out to be a key-name mismatch inside the probe, not
a failed walk: the diagnostic had been reporting false negatives on the
exact machine it was written for.

Refuted, on the record: the motion note's "visibility paradox" — the note
is readable precisely when the freeze actually persists (the page stays
`hidden` while the window is on screen), and hides when the state is
healthy. Working as designed; no change.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()
PROBE = (ROOT / "scripts" / "mac_motion_probe.py").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
WHATSNEW = (ROOT / "src" / "suravidl_engine" / "whatsnew.py").read_text()

from suravidl_engine import __main__ as engine_main

sys.path.insert(0, str(ROOT / "scripts"))
from mac_motion_probe import _tx, analyse  # noqa: E402


# ---------- fixtures ---------------------------------------------------------

class _FakeView:
    def __init__(self, name="NSView"):
        self.name = name
        self._subviews = []
        self._superview = None
        self._frame = None
        self._ident = None
        self.autoresizing = None
        self.added = []
        self.kv = {}

    def subviews(self):
        return list(self._subviews)

    def superview(self):
        return self._superview

    def frame(self):
        return self._frame

    def identifier(self):
        return self._ident

    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self

    def setFrame_(self, frame):
        self._frame = frame

    def setIdentifier_(self, ident):
        self._ident = ident

    def setAutoresizingMask_(self, mask):
        self.autoresizing = mask

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
        self._subviews.append(sub)

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


def _dressed_window():
    theme = _FakeView("NSThemeFrame")
    inner = type("WKWebView", (_FakeView,), {})()
    inner.setFrame_((0, 0, 800, 600))
    inner._superview = theme
    return theme, inner, _FakeWindow(_FakeNative(inner))


# ---------- the material: titlebar vibrancy is not "dressed" -----------------

def test_a_titlebar_vibrancy_view_never_passes_for_a_dressed_window():
    """Every titled NSWindow carries an NSVisualEffectView for its titlebar.
    The class-name scan mistook it for our material and skipped the insert —
    page transparent, nothing behind it. Only OUR identifier may count."""
    theme, inner, window = _dressed_window()
    vib = type("NSVisualEffectView", (_FakeView,), {})()  # the titlebar's vibrancy
    theme._subviews.append(vib)
    vib._superview = theme

    assert engine_main._install_material(
        window, _fake_appkit(True), None) is True
    assert theme.added, "the titlebar's vibrancy is not a dressed window"
    assert not inner.added                          # still never inside it


def test_the_material_carries_our_identifier():
    theme, inner, window = _dressed_window()
    engine_main._install_material(window, _fake_appkit(True), None)
    mat = theme.added[0][0]
    assert mat.identifier() == "suravidl.material"


def test_the_material_tracks_the_window_on_resize():
    """A bare NSView is not sizable by default: the glass froze at boot
    geometry and resizing left the page on bare window for the rest."""
    theme, inner, window = _dressed_window()
    engine_main._install_material(window, _fake_appkit(True), None)
    mat = theme.added[0][0]
    assert mat.autoresizing == (2 | 16)             # width + height sizable


# ---------- threading: mutations on main, JS never there ---------------------

def test_the_material_insert_rides_the_main_thread_but_never_js():
    """AppKit mutations off-main are how silent drawing failures start; and
    evaluate_js marshals to the main loop and WAITS — calling it there
    would deadlock the app (read in pywebview's cocoa path)."""
    assert "_on_main(perform)" in MAIN
    seg = MAIN.split("def perform():")[1].split("_on_main(perform)")[0]
    assert "addSubview_positioned_relativeTo_" in seg
    assert "setAutoresizingMask_" in seg
    assert "evaluate_js" not in seg                 # would deadlock the loop


def test_the_calm_flips_once_and_nudges_the_window():
    """Turning occlusion detection off does not un-hide a page WebKit
    already marked hidden; ordering the window in again makes it
    re-evaluate — and none of it may run twice or off-main."""
    assert "_CALM_DONE" in MAIN
    seg = MAIN.split("def _calm_page_visibility(")[1].split("def _dress(")[0]
    assert "_on_main(_flip)" in seg
    assert "orderFront_" in seg


def test_focus_activation_rides_the_main_thread():
    """`/app/focus` arrives on an HTTP worker thread; NSApplication calls
    from there are AppKit violations."""
    seg = MAIN.split("def _focus_window(")[1].split("actions = {")[0]
    assert "_on_main(_activate)" in seg


def test_the_ctypes_bridge_is_correct_and_falls_back():
    """c_void_p for a void method is wrong on principle, and find_library
    can return None inside frozen bundles: LoadLibrary(None) raises."""
    assert "None, ctypes.c_void_p" in MAIN         # void restype
    assert "CDLL(None)" in MAIN                     # already-loaded symbols first
    assert "/usr/lib/libobjc.A.dylib" in MAIN       # the guaranteed path last


# ---------- the probe: it must report what it collected ----------------------

def test_the_probe_reports_what_it_collected():
    """The runner wrote spi["wk"]/spi["win"] while analyse() read
    "spiWk"/"spiWin" — so every run printed "walk: MISS" and "?" no matter
    what was found. The keys are one name now."""
    assert '"spiWk": None' in PROBE and '"spiWin": None' in PROBE
    assert 'spi["spiWk"] =' in PROBE and 'spi["spiWin"] =' in PROBE
    assert 'payload.get("spiWk")' in PROBE
    assert '"wk":' not in PROBE and '"win":' not in PROBE


def test_tx_reads_identity_as_zero():
    """WebKit reports an at-rest transform as "none"; dropping those samples
    made a frozen-at-origin transition read as "not measured"."""
    assert _tx([0, "none", "visible"]) == 0.0
    assert _tx([0, "matrix(1, 0, 0, 1, 220, 0)", "visible"]) == 220.0
    assert _tx([0, "matrix(1, 0, 0, 1, 0, 0)", "visible"]) == 0.0


def _payload(samples, vis="visible"):
    return {"visibility": vis, "lateVisibility": None,
            "raf": list(range(0, 100, 16)), "timers": list(range(0, 500, 100)),
            "samples": samples, "occ": 8194, "spiWk": True, "spiWin": None}


def test_a_smooth_transition_is_never_verdict_skipped():
    """The probe's own runs kept crying "the transition got skipped" over a
    transition that advanced 0 -> 220 px — the load-transient hidden sample
    outweighed the animation evidence."""
    samples = [[0, "matrix(1, 0, 0, 1, 0, 0)", "hidden"],
               [100, "matrix(1, 0, 0, 1, 82, 0)", "visible"],
               [200, "matrix(1, 0, 0, 1, 155, 0)", "visible"],
               [300, "matrix(1, 0, 0, 1, 220, 0)", "visible"]]
    verdict = [ln for ln in analyse(_payload(samples)) if ln.startswith("VERDICT")][0]
    assert "animating" in verdict
    assert "skipped" not in verdict


def test_a_skipped_transition_still_gets_the_load_verdict():
    """Stuck at origin + born hidden IS the boot-window shape: keep naming it."""
    samples = [[0, "none", "hidden"], [100, "none", "hidden"],
               [200, "none", "visible"], [300, "none", "visible"]]
    lines = analyse(_payload(samples, vis="hidden"))
    verdict = [ln for ln in lines if ln.startswith("VERDICT")][0]
    assert "skipped" in verdict or "persistently hidden" in verdict
    assert "STUCK" in "\n".join(lines)              # and the raw shape is visible


# ---------- the UI: door, toasts, timers, player, fold -----------------------

def test_the_bay_door_disarms_before_it_reruns():
    """A second click mid-close re-ran the close AND the first listener
    sealed on the new transition — the door slammed instead of reversing."""
    assert "const disarm = () => {" in APP
    assert "body._doorEnd" in APP                   # one live listener at a time


def test_the_toast_lane_measures_at_most_once_a_frame():
    """An unthrottled scroll listener ran getBoundingClientRect over the
    docked furniture on every scroll tick — forced layout per frame."""
    import re
    assert re.search(r"toastLaneRaf = requestAnimationFrame", APP)


def test_reduced_motion_timers_do_not_outlive_the_transition():
    """The CSS snaps in 1ms under reduce; the JS timers kept invisible
    overlays intercepting pointer events for 170-460ms anyway."""
    assert "function motionMs(ms)" in APP
    for ms in ("170", "180", "260", "460"):
        assert "motionMs(%s)" % ms in APP, ms
    i = CSS.index("@media (prefers-reduced-motion: reduce)")
    block = CSS[i:i + 700]
    assert "animation-delay: 0s !important" in block
    assert "transition-delay: 0s !important" in block


def test_the_player_opens_through_the_modal_lifecycle():
    """openPlayerSrc added .hidden's opposite by hand: a pending close timer
    from 170ms ago could execute and hide the just-opened player."""
    assert 'openModal($("playModal"))' in APP
    assert '$("playModal").classList.remove("hidden")' not in APP


def test_the_fold_no_longer_needs_has():
    """`:has()` gates the whole rule on engines without it — the receipt
    could never expand. An explicit row class works everywhere."""
    assert ":has(" not in CSS
    assert 'row.classList.toggle("open"' in APP


def test_the_receipt_survives_a_poll_rebuild():
    """The 1200ms poll rebuilds a row on status change; an open receipt
    slammed shut because the fresh row was born folded."""
    assert 'fresh.classList.add("open")' in APP
    assert 'querySelector(".jobtitle.open")' in APP


def test_the_subtab_arrival_drops_its_transform():
    """A transform on the panel makes it a containing block for the fixed
    transport — the exact v0.37.3 tabIn law, overlooked for spanelIn."""
    assert "@keyframes spanelIn { from { opacity: 0; } }" in CSS
    assert "translateY(3px)" not in CSS


def test_whatsnew_has_the_comb():
    assert '"version": "0.39.12"' in WHATSNEW
    assert "The comb" in WHATSNEW
