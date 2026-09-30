"""v0.37.6 — the board reads at phone width.

Three device reports off the 2026-10-01 photos:

1. "the blur still not applied ... behind 'best available' it's still crisp"
   — proven now in BOTH geometries: fixed (v0.37.1-4) and sticky in-flow
   (v0.37.5) put crisp page text through the bar on the device. The shell is
   hardware-accelerated (no setLayerType, manifest default), so the WebView
   simply does not composite the backdrop pass for these floating plates.
   The blur declarations STAY — a WebView that composites lights them up —
   but the plate stops depending on it: a dense smoked pour (85% panel-solid)
   keeps the readout's pixels its own. The full-page overlay veil returns to
   the v0.36-proven rgba(3,5,12,.72) on this host.
2. "after probing the list goes overflow" — the four-column format table
   (quality / format / size / Take) cannot fit 393px: the Take buttons ran
   off the right edge. On phones each row re-stacks: quality + Take on the
   first line, the format beneath it, the size last.
3. "when there's updates or toast, it appears to the center instead of after
   the bottom bar" — the settings tab pushed the toast lane 150px up (the
   desktop rule mirrored with the tab bar added), floating it over the
   panel's content. One lane on the phone now: tab bar + 84px — it clears
   the sticky Save strip (top edge tab bar + ~72px) and docks right above
   the bar.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text(encoding="utf-8")


def _block(marker, text=CSS):
    i = text.index(marker)
    start = text.index("{", i)
    depth, j = 0, start
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces after " + marker)


def _mobile_seg(text=CSS, want=".transport {"):
    parts = text.split("@media (max-width: 899px)")
    for i in range(1, len(parts)):
        seg = parts[i].split("\n@media", 1)[0]
        if want in seg:
            return seg
    return parts[1].split("\n@media", 1)[0]


def test_the_probed_list_stacks_instead_of_overflowing():
    """The Take buttons ran off the right edge on a 393px phone — the four
    columns re-stack per row, header hidden."""
    seg = _mobile_seg(want="#formats thead")
    assert "#formats thead" in seg and "display: none" in seg
    tr = _block("#formats tbody tr", seg)
    assert "display: grid" in tr
    assert "minmax(0, 1fr)" in tr
    assert _block("#formats td:last-child", seg)  # the Take parks top-right
    assert _block("#formats td.fmt-c", seg)       # format gets its own line
    assert _block("#formats td.fmt-s", seg)       # size gets its own line


def test_the_phone_toast_docks_above_the_tab_bar():
    """One lane on the phone — the settings tab no longer shoves the toast
    into the middle of the panel (the Save strip clears at +72px)."""
    seg = _mobile_seg(want="#toasts")
    assert 'body[data-tab="settings"] #toasts' not in seg
    lane = _block("#toasts {", seg)
    assert "--tabbar-h" in lane


def test_the_phone_transport_pours_dense():
    """The readout never shares pixels with the page again: the android bar
    pours 85% panel-solid — and the blur declarations stay for WebViews
    that composite."""
    pour = _block('html[data-host="android"] .transport {')
    assert "color-mix" in pour and "85%" in pour
    base = _block(".transport {")
    assert "backdrop-filter: var(--glass-blur)" in base
    assert "-webkit-backdrop-filter: var(--glass-blur)" in base


def test_the_android_overlay_keeps_the_proven_veil():
    """This device never frosted the full-page veil either — the dense
    v0.36 veil returns; the frost stays declared on the base rule."""
    veil = _block('html[data-host="android"] .overlay {')
    assert "rgba(3, 5, 12, .72)" in veil
    base = _block(".overlay {")
    assert "backdrop-filter: blur(10px) saturate(120%)" in base