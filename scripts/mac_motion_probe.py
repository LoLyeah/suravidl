#!/usr/bin/env python3
"""The macOS motion probe — a one-minute check for the frozen-animation lead.

The report (v0.38.7, still open): the desktop app's CSS animations don't
play on the MacBook Air. The lead: WebKit pauses CSS transitions, rAF and
DOM timers whenever it decides a view is not visible, and an alpha-0 /
transparent window — exactly what the v0.38.4 macOS shell is — is known to
report itself occluded.

This probe answers it on the real hardware, without shipping a fix. It
opens the SAME window recipe the app uses (transparent on darwin), runs a
CSS transition, a rAF counter and a 100 ms timer chain for ~3 seconds, then
prints a verdict block to paste back into the chat. The occlusion SPI
(`_setWindowOcclusionDetectionEnabled:`) is checked for availability but
never called — diagnose, don't treat.

Run on the MacBook Air (no repo clone needed, pywebview is the only dep):

    pip3 install pywebview   # if missing
    python3 mac_motion_probe.py
"""
import json
import re
import sys
import time

RAF_WINDOW_MS = 3000

PAGE = """<!doctype html><meta charset="utf-8">
<style>
html,body{margin:0;background:transparent;font:13px -apple-system,Helvetica,sans-serif;color:#e8e4da}
#stage{padding:16px}
#box{width:60px;height:60px;border-radius:14px;background:#7bb27a;
     transform:translateX(0);transition:transform 1.4s linear}
#box.go{transform:translateX(220px)}
</style>
<div id="stage"><div id="box"></div><p id="say">measuring…</p></div>
<script>
const P = window.__probe = {
  visibility: document.visibilityState, hidden: document.hidden,
  raf: [], timers: [], samples: [],
};
const box = document.getElementById('box');
const t0 = performance.now();
/* the before-state, before any class — the start point the transition needs */
P.samples.push([0, getComputedStyle(box).transform, document.visibilityState]);
requestAnimationFrame(function first() {
  getComputedStyle(box).transform;   /* flush the before-style */
  box.classList.add('go');           /* the transition starts on a settled frame */
  requestAnimationFrame(function loop() {
    P.raf.push(Math.round(performance.now() - t0));
    if (performance.now() - t0 < 3000) requestAnimationFrame(loop);
  });
});
let n = 0;
(function tick() {
  const t = Math.round(performance.now() - t0);
  P.timers.push(t);
  P.samples.push([t, getComputedStyle(box).transform, document.visibilityState]);
  if (++n < 34) setTimeout(tick, 100);
  else document.getElementById('say').textContent = 'done — you can close this';
})();
</script>
"""

SPI_WK = "_setWindowOcclusionDetectionEnabled:"
SPI_WIN = "_setOcclusionDetectionEnabled:"
OCCLUSION_VISIBLE = 2  # NSWindowOcclusionStateVisible = 1 << 1


def _find_webview_view(root):
    """Depth-first for the WKWebView pywebview wrapped (same walk as the app).

    pywebview wraps WKWebView in a `WebKitHost` subclass, so a bare name
    check never matches (the probe's own SPI line printed `?` until this
    fix). isKindOfClass covers the wrapper; the name check stays as the
    fallback."""
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


def _tx(sample_row):
    """`matrix(1, 0, 0, 1, 220, 0)` -> 220.0 (the translateX), else None."""
    m = re.search(r"matrix\(([^)]+)\)", str(sample_row[1] if len(sample_row) > 1 else ""))
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) < 6:
        return None
    try:
        return float(parts[4])
    except ValueError:
        return None


def analyse(payload: dict) -> list:
    """Turn a collected payload into the paste-back verdict lines."""
    lines = []
    vis = payload.get("visibility")
    late = payload.get("lateVisibility")
    hidden = (vis == "hidden") or (late == "hidden") or any(
        len(s) > 2 and s[2] == "hidden" for s in payload.get("samples") or [])
    lines.append("visibility: %s -> late %s  (page hidden: %s)"
                 % (vis, late, "YES" if hidden else "no"))

    raf = [t for t in payload.get("raf") or [] if isinstance(t, (int, float))]
    if len(raf) >= 5 and raf[-1] > raf[0]:
        rate = (len(raf) - 1) * 1000.0 / (raf[-1] - raf[0])
        lines.append("rAF: %d ticks ~ %.0f/s  (%s)"
                     % (len(raf), rate, "alive" if rate >= 5 else "FROZEN"))
    else:
        lines.append("rAF: %d ticks in %dms  (FROZEN — loop never advanced)"
                     % (len(raf), RAF_WINDOW_MS))

    timers = [t for t in payload.get("timers") or [] if isinstance(t, (int, float))]
    if len(timers) >= 5 and timers[-1] > timers[0]:
        trate = (len(timers) - 1) * 1000.0 / (timers[-1] - timers[0])
        lines.append("timers(100ms): %d fires ~ %.1f/s  (%s)"
                     % (len(timers), trate,
                        "alive" if trate >= 5 else "THROTTLED (the hidden-page shape)"))
    else:
        lines.append("timers(100ms): %d fires (THROTTLED)" % len(timers))

    samples = payload.get("samples") or []
    txs = [(_tx(s), s[0] if len(s) > 0 else None) for s in samples]
    txs = [(x, t) for (x, t) in txs if x is not None]
    moved = None
    if len(txs) >= 3:
        xs = [x for (x, _) in txs]
        mid_pairs = [(xs[i], xs[i + 1], txs[i + 1][1]) for i in range(len(xs) - 2)]
        stepped = any(b - a > 0.5 for (a, b, _) in mid_pairs)
        jumped = xs[-1] - xs[0] > 1.0 and not stepped
        stuck = abs(xs[-1] - xs[0]) <= 1.0
        moved = ("animating — transform advanced %g -> %g" % (xs[0], xs[-1])
                 if stepped else
                 "FROZEN-THEN-JUMP — mid-samples stuck at %g, end at %g"
                 % (xs[0], xs[-1]) if jumped else
                 "STUCK — transform never left %g" % xs[0])
    lines.append("CSS transition: %s" % (moved or "not measured"))

    occ = payload.get("occ")
    if occ is None:
        lines.append("window occlusion state: n/a (native window unavailable)")
    else:
        lines.append("window occlusion state: %s (raw %s; VISIBLE bit %s)"
                     % ("VISIBLE" if occ & OCCLUSION_VISIBLE else "NOT VISIBLE",
                        occ, "on" if occ & OCCLUSION_VISIBLE else "OFF"))
    wk = payload.get("spiWk")
    lines.append("webview walk: %s%s"
                 % ("found" if wk is not None else "MISS",
                    ("" if not payload.get("views")
                     else " — views at contentView: "
                     + ", ".join(payload.get("views")))))
    lines.append("WKWebView %s available: %s  (the candidate fix)"
                 % (SPI_WK, "YES" if wk else "no" if wk is False else "?"))
    if payload.get("spiWin"):
        lines.append("NSWindow-level spelling %s also answers: YES"
                     % payload.get("spiWin"))
    if payload.get("err"):
        lines.append("native-side probe error: %s" % payload.get("err"))

    samples = payload.get("samples") or []
    vis_seq = [s[2] for s in samples if len(s) > 2]
    n_hidden = sum(1 for v in vis_seq if v == "hidden")
    n_vis = len(vis_seq) - n_hidden
    if vis_seq:
        flip = None
        if vis_seq[0] == "hidden" and n_vis:
            flip = vis_seq.index("visible")
        lines.append("visibility over samples: hidden x%d, visible x%d%s"
                     % (n_hidden, n_vis,
                        "" if flip is None
                        else " (flipped to visible at ~%dms)"
                        % (samples[flip][0] if len(samples[flip]) > 0 else 0)))

    verdict = "FROZEN"
    if moved and "animating" in moved and not hidden:
        verdict = "animating"
    elif vis_seq and vis_seq[0] == "hidden" and n_vis:
        # the probe's own first run (2026-10-02): page born hidden, later
        # samples visible, transition already skipped — boot-window shape
        verdict = ("hidden at load only — the boot window was born unseen and "
                   "the load-time transition got skipped; re-run against the "
                   "running app to check the steady state")
    elif vis_seq and n_hidden == len(vis_seq):
        verdict = "FROZEN — persistently hidden (the occlusion lead confirmed)"
    elif hidden and (moved is None or "animating" not in moved):
        verdict = "FROZEN — WebKit thinks the page is hidden (the occlusion lead)"
    elif moved and "FROZEN" in moved and not hidden:
        verdict = "frozen while visible — not the occlusion lead; paste this back"
    lines.append("VERDICT: %s" % verdict)
    return lines


def main() -> None:
    import webview

    win = webview.create_window(
        "suravidl motion probe", html=PAGE, width=430, height=560,
        transparent=sys.platform == "darwin",
    )
    spi: dict = {"wk": None, "win": None, "occ": None}

    def run() -> None:
        time.sleep(1.2)
        try:
            native = getattr(win, "native", None)
            if native is not None:
                spi["occ"] = int(native.occlusionState())
                # pywebview parents the webview at first-load, not at
                # GUI-start — walk with a retry until it shows up (v0.39.10)
                views: list = []
                for attempt in range(8):   # ~4s of retry
                    wk = _find_webview_view(native.contentView())
                    if wk is not None:
                        break
                    try:
                        content = native.contentView()
                        views = [type(content).__name__] + [
                            type(v).__name__ for v in content.subviews()]
                    except Exception:  # noqa: BLE001 - evidence only
                        views = []
                    time.sleep(0.5)
                spi["views"] = views[:5]
                if wk is not None and wk.respondsToSelector_(SPI_WK):
                    spi["wk"] = True
                elif wk is not None:
                    spi["wk"] = False
                if native.respondsToSelector_(SPI_WIN):
                    spi["win"] = SPI_WIN
        except Exception as err:  # noqa: BLE001 - the probe never dies angry
            spi["err"] = repr(err)
        time.sleep(3.2)
        raw = None
        if win is not None:
            raw = win.evaluate_js("JSON.stringify(window.__probe)")
        raw = raw or "{}"
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {}
        payload.update(spi)
        print("")
        print("---- paste everything below ----")
        for line in analyse(payload):
            print(line)
        print("pywebview %s / python %s / %s"
              % (getattr(webview, "__version__", "?"), sys.version.split()[0],
                 sys.platform))
        print("---- paste everything above ----")

    try:
        webview.start(run)
    except Exception as err:  # noqa: BLE001 - e.g. no display on a headless box
        print("couldn't open a window here (%r) — run this on the MacBook Air"
              % (err,))
        print("sys.platform =", sys.platform)


if __name__ == "__main__":
    main()
