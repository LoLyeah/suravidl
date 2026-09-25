"""The UI/UX + motion pass, pinned.

The rule under test, for every one of these: motion exists to make the app's
state legible, so it has to survive a reduced-motion setting, cover the states
that used to be silent (queued, merging, deleting, unsaved), and never fight
the layout. Each assertion names the failure it prevents.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()

def _grab(pattern, text=CSS):
    m = re.search(pattern, text)
    assert m, f"pattern not found: {pattern}"
    return m.group(1)


POLL_MS = int(_grab(r"setInterval\(refreshJobs, (\d+)\)", APP))


def _block(marker, text=CSS):
    """The text from `marker` through its matching closing brace — counted, so
    a brace inside the block cannot truncate it the way `split("}")` does."""
    i = text.index(marker)
    start = text.index("{", i)
    depth, j = 0, start
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[start:j]


def test_reduced_motion_actually_stops_infinite_animations():
    """The old block set `animation-duration: .001s !important` — which does not
    stop an infinite animation, it runs it a thousand times a second. Measured
    live: the empty-state box was spinning `floaty` at ~1kHz."""
    block = _block("@media (prefers-reduced-motion: reduce)")
    # one iteration is the part that actually stops a loop; a tiny duration
    # alone just makes it faster
    assert "animation-iteration-count: 1 !important" in block
    assert "infinite" not in block


def test_reduced_motion_covers_pseudo_elements():
    """`*` does not match `::before`/`::after`, so the shimmer on the progress
    bar's `::after` kept running at full speed with reduced motion on."""
    block = _block("@media (prefers-reduced-motion: reduce)")
    assert "*::before" in block and "*::after" in block


def test_the_progress_glide_is_paired_with_the_poll_interval():
    """A 220ms width transition against a 1200ms poll animates, then sits dead
    for a second — a stalled-looking download. The glide has to span the whole
    window, which only stays true if the two numbers move together."""
    assert ".bar .fill.active {" in CSS
    seg = _block(".bar .fill.active {")
    assert "var(--t-poll)" in seg and "linear" in seg
    token = float(_grab(r"--t-poll:\s*([\d.]+)s"))
    assert 0.8 * POLL_MS / 1000 <= token <= POLL_MS / 1000, token


def test_queued_and_merging_get_an_indeterminate_bar():
    """They showed nothing at all — and merging is a 15-45s ffmpeg mux, long
    enough to read as a hung engine."""
    assert 'const downloading = j.status === "downloading"' in APP
    assert '"fill active" + (downloading ? "" : " indet")' in APP
    assert ".bar .fill.indet" in CSS
    # and the poll must not overwrite the indeterminate width with a "0%"
    assert 'fill && !fill.classList.contains("indet")' in APP


def test_a_queued_job_does_not_print_zero_percent():
    """`0%` next to a moving bar reads as a stall."""
    seg = APP.split("function metaParts(j)")[1].split("\n}")[0]
    assert '...(downloading ? [pct + "%"] : [])' in seg


def test_rows_leave_instead_of_blinking_out():
    """Every disappearance was `innerHTML = ""`; there was no exit anywhere."""
    assert "function leaveRow(" in APP
    assert 'classList.add("leaving")' in APP
    assert "@keyframes leave" in CSS
    assert "animationend" in APP and "remove()" in APP.split("function leaveRow(")[1][:900]


def test_the_exit_animates_transform_and_opacity_only():
    """A max-height/padding collapse would relayout the whole queue every frame
    — the constraint the queue's entrance animation already obeys."""
    seg = _block("@keyframes leave")
    assert ".leaving { animation: leave" in CSS      # and something uses it
    assert "transform" in seg and "opacity" in seg
    for layout_prop in ("height", "max-height", "padding"):
        assert layout_prop not in seg


def test_the_row_swap_does_not_move_the_row():
    """`.swap` fired on every poll that changed anything (queued -> downloading
    -> merging -> done) and dropped the whole row 6px each time."""
    seg = _block("@keyframes swapIn")
    assert "translate" not in seg
    assert "opacity" in seg


def test_the_dialog_exit_lands_on_zero_opacity():
    """It transitioned to `opacity: .5` while closeModal() hid the overlay at
    170ms — every dialog was cut off half-visible."""
    seg = _block(".overlay.closing .modal {")
    assert "opacity: 0" in seg


def test_the_player_closes_like_every_other_dialog():
    seg = APP.split("function closePlayer()")[1].split("\n}")[0]
    assert "closeModal(" in seg


def test_android_freezes_the_aurora():
    """Three radial gradients under a 70px blur, re-rastered every frame, on a
    phone — battery spent on decoration while a download is the job."""
    seg = _block('html[data-host="android"] body::before')
    assert "animation: none !important" in seg


def test_a_start_disables_its_button():
    """A start can take most of a second; a button that does not move invites a
    second tap, and the first click had already queued the job."""
    seg = APP.split("async function startJob(url, fmt, preset, playlist, triggerBtn)")[1]
    assert "triggerBtn.disabled = true" in seg.split("try {")[0]
    assert "triggerBtn.disabled = false" in seg
    # every real trigger passes itself in
    assert APP.count(", btn)") >= 2
    for call in ('$("bestBtn")', '$("playlistBtn")', '$("audioMore")'):
        assert call + ")" in APP


def test_a_start_with_no_link_says_so():
    seg = APP.split("async function startJob(")[1].split("try {")[0]
    assert "paste a video link first" in seg


def test_deleting_says_deleting():
    """The settle loop runs up to ~3s after the confirm dialog has gone; the row
    looked untouched the whole time."""
    assert '.job.pending {' in CSS
    seg = APP.split("await settleThenDelete(j)")[0][-900:]
    assert 'classList.add("pending")' in seg
    assert '"deleting…"' in seg and '"stopping…"' in seg
    # and a failed delete must not leave the row stuck in that state
    assert 'row.classList.remove("pending")' in APP


def test_settings_edits_are_visible_from_anywhere():
    assert "function markSettingsDirty(on)" in APP
    assert 'classList.toggle("has-dirty", on)' in APP
    assert ".tab.has-dirty .tab-lbl::after" in CSS
    assert "markSettingsDirty(true)" in APP and "markSettingsDirty(false)" in APP


def test_the_option_catalogue_is_reachable_from_a_keyboard():
    """300+ click-only `div`s: the whole yt-dlp option browser was unreachable."""
    assert "function makeOptionRowReachable(" in APP
    assert "makeOptionRowReachable(row, add)" in APP
    assert "function initOptionListKeyboard(" in APP
    assert "initOptionListKeyboard();" in APP
    # roving tabindex: exactly one stop, arrows move inside
    assert 'row.tabIndex = -1' in APP
    assert 'ArrowDown' in APP and 'ArrowUp' in APP
    assert ".optrow:focus-visible" in CSS


def test_focus_keeps_the_field_above_the_sticky_bars():
    """On a phone the keyboard shrinks the viewport and the field being typed
    into ended up under the pinned footer."""
    seg = APP.split('document.addEventListener("focusin"')[1].split("});")[0]
    assert "scrollIntoView" in seg
    assert "getBoundingClientRect" in seg          # only when actually obscured
    assert "prefers-reduced-motion" in seg         # smooth scroll is motion too
