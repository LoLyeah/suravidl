"""v0.42.1 "the glide" — the motion audit's confirmed findings, fixed; and
spent update files are cleaned up on every platform.

The motion pass (every finding verified against the tree before patching;
finding #1 — the scope power-on's 620ms — stays out by the user's call):

2.  the armed strip folds open instead of shoving the formats table down
3.  subtitle chips, the tab's dirty dot and the queue badge transition now
4.  the courier row refreshes with one house fade, on a real state change
    only — progress numbers stay crisp
5.  the modal exit accelerates out (--e-in); it no longer lingers
6.  the receipt fold rides the house tokens, not near-miss literals
7.  two JS fallbacks honour prefers-reduced-motion (motionMs)
8.  the queue sieve glides rows out (and reverses cleanly), and the FAQ
    folds like the deck's bay door

Housekeeping ("did the downloaded update file get deleted?"): a staged
update is only actionable inside the engine session that staged it — the
state is in-memory. So nothing may linger afterwards: the Windows chain
deletes the spent setup, the macOS swap deletes the spent zip, and every
boot sweeps whatever an older session (or the version that just replaced
itself) left behind.
"""
import inspect
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()
SWAP = (ROOT / "src" / "suravidl_engine" / "macos_swap.sh").read_text()
YML = (ROOT / ".github" / "workflows" / "release.yml").read_text()


def _fn(name):
    i = APP.index("function " + name)
    return APP[i:].split("\nfunction ", 1)[0]


# ---------- 2. the armed strip folds ----------

def test_the_armed_strip_folds_through_grid_rows():
    i = CSS.index("#armedBar {")
    seg = CSS[i:i + 1800]
    assert "grid-template-rows: 0fr" in seg
    assert "#armedBar.armed-open { grid-template-rows: 1fr; }" in seg
    assert ".armed-clip" in seg and "overflow: hidden" in seg
    assert "visibility: hidden" in seg, \
        "folded content must leave the tab order and the a11y tree"
    # the bar itself is the grid now — the flex row moved inside
    assert "display: flex" not in CSS[i:CSS.index("}", i)]


def test_the_fold_item_is_bare_so_old_engines_reach_zero():
    """Older grid engines size a 0fr track to the item's outer minimum —
    a padded or bordered grid item leaves a sliver unfolded on old WebViews
    (measured live: pad+border+margin read as 26px in the era engine used
    for the v0.42.1 check). Every visual lives on .armed-strip, INSIDE."""
    i = CSS.index("#armedBar .armed-clip {")
    clip_rule = CSS[i:CSS.index("}", i)]
    for prop in ("padding", "border", "margin"):
        assert prop not in clip_rule, f"the clip must stay bare ({prop} leaks)"
    j = CSS.index("#armedBar .armed-strip {")
    strip_rule = CSS[j:CSS.index("}", j)]
    assert "padding" in strip_rule and "border" in strip_rule and "margin" in strip_rule


def test_the_strip_markup_carries_the_clip():
    assert '<div id="armedBar" role="status">' in HTML
    assert '<div class="armed-clip">' in HTML
    assert '<div class="armed-strip">' in HTML
    assert 'id="armedText"' in HTML and 'id="armedClear"' in HTML


# ---------- 3. the snaps get transitions ----------

def test_a_chip_pick_glides():
    i = CSS.index(".chip {")
    assert "transition" in CSS[i:i + 700]


def test_the_dirty_dot_scales_in():
    i = CSS.index(".tab .tab-lbl::after")
    seg = CSS[i:i + 500]
    assert "scale(0)" in seg and "transition" in seg
    assert ".tab.has-dirty .tab-lbl::after { transform: scale(1); opacity: 1; }" in CSS


def test_the_queue_badge_pops_in_only_when_it_appears():
    assert ".badge.badge-in" in CSS and "@keyframes badgeIn" in CSS
    body = _fn("renderQueueBadge")
    assert 'const was = !badge.classList.contains("hidden")' in body
    assert "if (active && !was)" in body
    assert 'badge.classList.add("badge-in")' in body
    assert "void badge.offsetWidth" in body, "retrigger needs the reflow"


# ---------- 4. the courier row fades on state changes only ----------

def test_the_courier_row_refreshes_on_state_changes_only():
    assert "function _restartSwap(" in APP
    row = _fn("renderCourierRow")
    assert "UPD_LAST_BUCKET !== null && st.status !== UPD_LAST_BUCKET" in row
    assert "_restartSwap(state.parentElement)" in row
    assert "_restartSwap(meta)" in row
    # the guard precedes the text mutations, and a progress tick (same
    # status, new numbers) never reaches it
    assert row.index("UPD_LAST_BUCKET") < row.index("state.textContent")


# ---------- 5/6. tokens, not near-misses ----------

def test_the_modal_exit_accelerates_out():
    i = CSS.index(".overlay.closing {")
    seg = CSS[i:i + 600]
    assert seg.count("var(--e-in)") == 3, \
        "the veil and the card both accelerate out now"


def test_the_receipt_fold_rides_the_house_tokens():
    assert ".28s" not in CSS
    assert "cubic-bezier(.2,.7,.3,1)" not in CSS
    i = CSS.index(".jdetails {")
    assert "var(--t-base) var(--e-out)" in CSS[i:i + 300]
    i = CSS.index("transition: padding-top")
    assert "var(--t-base) var(--e-out)" in CSS[i:i + 130]


def test_the_js_fallbacks_honour_reduced_motion():
    lr = _fn("leaveRow")
    assert "motionMs(400)" in lr, "the 400ms fallback must clamp to zero"
    assert "motionMs(500)" in _fn("wireBayDoor"), \
        "the door's never-jam fallback must clamp to zero"


# ---------- 8. the sieve glides; the FAQ folds ----------

def test_the_filter_glides_rows_out_and_reverses():
    seg = _fn("applyQueueFilter")
    assert 'classList.add("leaving")' in seg
    assert "row._hideT" in seg and "motionMs(280)" in seg
    assert 'classList.add("hidden")' in seg
    assert 'classList.add("swap")' in seg, "a returning row arrives softly"
    assert "const matches = QFILTER" in seg, "the flip-back re-checks the filter"
    assert 'classList.toggle("hidden", !show)' not in seg, \
        "the instant toggle WAS the finding"


def test_the_faq_rides_the_bay_door():
    assert ".faq-body" in CSS and ".faq-item[open] .faq-body" in CSS
    assert 'wrap.className = "faq-body"' in APP
    assert 'wireBayDoor(it, it.querySelector(".faq-body"))' in APP
    assert "function wireBayDoor(d, bodyEl)" in APP
    assert 'const body = bodyEl || d.querySelector(".bay-body")' in APP


# ---------- housekeeping: spent update files are deleted ----------

def test_the_windows_chain_deletes_the_spent_setup():
    import base64

    from suravidl_engine.__main__ import _windows_apply_command

    argv = _windows_apply_command(r"C:\Temp\suravidl-setup.exe",
                                  r"C:\App\suravidl.exe")
    script = base64.b64decode(argv[-1]).decode("utf-16-le")
    assert "Remove-Item -LiteralPath 'C:\\Temp\\suravidl-setup.exe'" in script
    # it runs AFTER the installer exits, BEFORE the relaunch
    assert script.index("Remove-Item") > script.index("/CLOSEAPPLICATIONS")
    assert script.index("Remove-Item") < script.index(
        "Start-Process -FilePath 'C:\\App\\suravidl.exe'")
    lone = base64.b64decode(
        _windows_apply_command(r"C:\Temp\setup.exe", None)[-1]).decode("utf-16-le")
    assert "Remove-Item" in lone, "no relaunch still cleans up"


def test_the_mac_swap_consumes_the_zip():
    i = SWAP.index('if mv "$NEW" "$APP"; then')
    seg = SWAP[i:i + 400]
    assert 'rm -f "$ZIP"' in seg, "zip removal rides the success branch"


def test_the_ci_dry_run_watches_the_carrier():
    assert 'test ! -e "$WORK/update.zip"' in YML, "swap consumed the carrier"
    assert 'test -f "$WORK/bad.zip"' in YML, "a failed swap keeps it"


def test_the_sweep_removes_orphans_and_keeps_live_files(tmp_path):
    from suravidl_engine import updater

    updater.reset_update_state()
    try:
        (tmp_path / "old-setup.exe").write_bytes(b"x")
        (tmp_path / "half.part").write_bytes(b"y")
        assert updater.sweep_stale_downloads(tmp_path) == 2
        assert list(tmp_path.iterdir()) == []

        keep = tmp_path / "app-release.apk"
        keep.write_bytes(b"z")
        updater.reset_update_state(status="ready", path=str(keep))
        assert updater.sweep_stale_downloads(tmp_path) == 0
        assert keep.exists(), "a ready stage is still actionable — it stays"

        updater.reset_update_state(status="downloading", name="app-release.apk")
        (tmp_path / "app-release.apk.part").write_bytes(b"p")
        (tmp_path / "leftover.bin").write_bytes(b"q")
        assert updater.sweep_stale_downloads(tmp_path) == 1
        assert (tmp_path / "app-release.apk.part").exists(), \
            "an active download's .part is not an orphan"
        assert keep.exists()
    finally:
        updater.reset_update_state()


def test_a_fresh_download_clears_an_older_sessions_stage(tmp_path):
    from suravidl_engine import updater

    stale = tmp_path / "previous-session.bin"
    stale.write_bytes(b"old")
    updater.reset_update_state()
    try:
        updater.start_update_download(
            "0.41.0",
            manifest_fn=lambda repo: {
                "version": "99.0.0", "tag": "v99.0.0",
                "repo": "LoLyeah/suravidl",
                "assets": {"suravidl-linux-x64.AppImage": {
                    "url": "https://github.com/LoLyeah/suravidl/releases/"
                           "download/v99.0.0/suravidl-linux-x64.AppImage",
                    "size": 1, "sha256": "ab" * 32}},
                "roles": {"linux_appimage": "suravidl-linux-x64.AppImage"}},
            download_fn=lambda url, sha, name, dest: {
                "status": "ready", "path": str(dest / name),
                "sha256_ok": True, "bytes": 1, "total": 1, "name": name,
                "error": None},
            dest_dir=tmp_path)
        for _ in range(100):
            if updater.update_status()["status"] != "downloading":
                break
            threading.Event().wait(0.05)
        assert updater.update_status()["status"] == "ready"
        assert not stale.exists(), \
            "the old stage must go the moment a fresh download starts"
    finally:
        updater.reset_update_state()


def test_every_boot_sweeps_what_the_last_session_left():
    from suravidl_engine import __main__ as launcher

    src = inspect.getsource(launcher.start_server)
    assert "sweep_stale_downloads" in src
    assert src.index("sweep_stale_downloads") < src.index("import uvicorn"), \
        "the sweep lands before the server takes its first request"
