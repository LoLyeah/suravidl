"""v0.41.1 "the delivery" — the audit fixes (impeccable + antislop passes).

Every finding arrived as a hypothesis and was checked against the real
tree before anything changed; these pins hold only what was confirmed and
fixed. Rejected-as-audited (with evidence) is recorded in the session
report, not here.

Confirmed and fixed:
- an update download can be cancelled mid-stream (engine flag + row button)
- a failed background download raises a toast wherever the user is
- the ready state announces itself with the real install door (restarting
  the app alone installs nothing — the old copy implied it did)
- Settings keeps "Skip this version" reachable; the manual release door is
  its own button and only shows in the resting states
- Android install failures say what happened instead of silently ejecting
  to a browser; the permission detour greets the user on return
- "Check now" hides while an update is already offered (row crowding)
- the toast lane composes its measured lift over the safe-area inset
- a hidden page stops polling the queue and re-syncs on return
- the tab bar precedes the panels in the DOM (keyboard order == paint)
- the tour is escapable and holds Tab inside its card
- iOS's under-16px input auto-zoom is gated to iOS, not Android/desktop
- .linkbtn is inline-flex so the 44px touch rule actually bites
- one lamp per region: "Get it" and "Download playlist" step off prime
- the stale "Nova Rose" comment name is gone
"""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine import updater

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
HTML = (WEB / "index.html").read_text()
APP = (WEB / "app.js").read_text()
CSS = (WEB / "style.css").read_text()


def _fn(start, end):
    return APP.split(start, 1)[1].split(end, 1)[0]


def _client(tmp_path):
    from suravidl_engine.api import create_app

    app = create_app(download_dir=str(tmp_path), auth_token="t",
                     db_path=":memory:")
    return TestClient(app), {"Authorization": "Bearer t"}


# --- engine: cancel ---------------------------------------------------------


def test_the_engine_cancels_a_stream_mid_flight(tmp_path):
    """A cancel lands between chunks: nothing staged, nothing left over,
    and the state ends idle — not failed (the user asked for this)."""
    payload = os.urandom(1024 * 1024)          # 16 x 64KB, 0.08s apart

    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            for i in range(0, len(payload), 65536):
                try:
                    self.wfile.write(payload[i:i + 65536])
                    self.wfile.flush()
                except OSError:
                    return
                time.sleep(0.08)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = ("http://127.0.0.1:%d/app-release.apk"
               % srv.server_address[1])
        updater.reset_update_state()
        th = threading.Thread(target=lambda: updater.download_asset(
            url, "f" * 64, "app-release.apk", tmp_path))
        th.start()
        st = {}
        deadline = time.time() + 8
        while time.time() < deadline:
            st = updater.update_status()
            if st["status"] == "downloading" and st["bytes"] > 0:
                break
            time.sleep(0.05)
        assert st.get("status") == "downloading", "the stream never started"
        updater.cancel_update_download()
        th.join(timeout=10)
        assert not th.is_alive(), "the worker must observe the flag and stop"
        st = updater.update_status()
        assert st["status"] == "idle", "a cancel is voluntary, not a failure"
        assert st["cancel"] is False, "the flag resets with the state"
        assert not (tmp_path / "app-release.apk").exists()
        assert not list(tmp_path.glob("*.part"))
    finally:
        srv.shutdown()


def test_cancel_with_nothing_running_is_a_noop():
    updater.reset_update_state()
    assert updater.cancel_update_download()["status"] == "idle"


def test_the_api_exposes_cancel_behind_auth(tmp_path):
    c, h = _client(tmp_path)
    updater.reset_update_state()
    assert c.post("/update/cancel").status_code == 401
    r = c.post("/update/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "idle"


# --- UI: the courier row ----------------------------------------------------


def test_the_row_can_cancel_and_speaks_up():
    row = _fn("function renderCourierRow", "async function syncStagedUpdate")
    assert '"Cancel download"' in row and "cancelUpdateDownload" in row
    assert 'api("/update/cancel"' in APP
    assert "downloading the update in the background" in APP
    poll = _fn("function pollUpdateStatus", "\n/** The ready door")
    assert "the update download failed" in poll
    assert "humanErr(UPD_DL.error" in poll


def test_the_ready_notice_carries_the_door():
    """The old copy said 'restart when you're ready' — restarting the app
    installs nothing on either platform. The notice carries the button."""
    assert "announceUpdateReady" in APP and "update-ready" in APP
    assert '"Restart when' not in APP and "restart when you" not in APP
    door = _fn("function announceUpdateReady", "\n}")
    assert "installStagedUpdate" in door
    assert 'ANDROID() ? "Install now" : "Restart & Install"' in door
    sync = _fn("async function syncStagedUpdate", "/** force")
    assert "announceUpdateReady()" in sync, "a reload must keep the door"


def test_settings_keeps_its_skip_toggle_and_owns_a_manual_door():
    row = _fn("function renderCourierRow", "async function syncStagedUpdate")
    assert '"Skip this version"' in row and "Stop skipping" in row
    assert 'id="updManual"' in HTML
    assert ">Download manually</button>" in HTML
    assert 'chk.classList.toggle("hidden"' in APP, \
        "Check now must step aside while an update is already offered"


def test_android_install_never_ejects_silently():
    door = _fn("async function installStagedUpdate", "function renderCourierRow")
    assert "could not launch the installer" in door
    assert "UPD_PERM_WAIT = true" in door
    assert "function checkUpdatePermResume()" in APP
    assert "checkUpdatePermResume();" in APP.split(
        'document.addEventListener("visibilitychange", () => {',
        1)[1].split("});", 1)[0]


# --- UI: layout and behaviour -----------------------------------------------


def test_a_hidden_page_stops_polling_the_queue():
    fn = _fn("async function refreshJobs", "JOBS_BUSY = true")
    assert "document.hidden" in fn
    vis = APP.split('document.addEventListener("visibilitychange", () => {',
                    1)[1]
    assert "refreshJobs();" in vis.split("});", 1)[0], \
        "the queue must be current the moment the page is visible again"


def test_the_tab_bar_precedes_the_panels_in_the_dom():
    """Keyboard order follows the DOM; the paint order stays the
    stylesheet's business via flex `order`."""
    assert HTML.index('id="tabs"') < HTML.index('id="panels"')
    assert ".tabs { order: 2; }" in CSS and "order: 4" in CSS


def test_the_tour_is_escapable_and_traps_tab():
    assert 'if (e.key === "Escape") { e.preventDefault(); tourEnd(); return; }' in APP
    assert '$("tourCard").querySelectorAll("button")' in APP
    assert '$("tourNext").focus({ preventScroll: true })' in APP


def test_the_toast_lift_composes_with_the_safe_area():
    assert "bottom: calc(24px + var(--toast-lift, 0px));" in CSS
    assert ("env(safe-area-inset-bottom) + var(--toast-lift, 0px));" in CSS)
    fn = _fn("function syncToastLane", "\n}")
    assert 'host.style.setProperty("--toast-lift"' in fn
    assert 'host.style.removeProperty("--toast-lift")' in fn


def test_ios_zoom_gate_linkbtn_and_the_failed_row():
    assert "@supports (-webkit-touch-callout: none)" in CSS
    blk = CSS.split(".linkbtn {", 1)[1].split("}", 1)[0]
    assert "inline-flex" in blk, "inline boxes ignored the 44px touch rule"
    assert ".updmeta.bad { color: var(--err); }" in CSS


def test_type_scale_one_lamp_and_no_stale_names():
    assert "header h1 { font-size: 18px;" in CSS
    assert ".card h2 { margin: 0 0 12px; font-size: 16px;" in CSS
    assert "Nova Rose" not in APP, "the stale palette name is gone"
    # one lamp: Get it and Download playlist step off prime
    assert 'id="updGet" class="btn sm hidden"' in HTML
    assert 'id="playlistBtn" class="btn sm"' in HTML
