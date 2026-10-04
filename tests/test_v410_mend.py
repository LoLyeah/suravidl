"""v0.40.10 "the mend" — the audit findings, closed with reproductions.

Two independent audits (impeccable critique + code audit) ran against v0.40.9;
every finding here was re-verified against the tree before the fix. Sections:
engine reproductions (end-to-end where possible), web-UI pins, Android pins,
and the small documented decisions that stay as they are.
"""
import functools
import http.server
import re
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]
APPJS = (ROOT / "src/suravidl_engine/web/app.js").read_text()
INDEX = (ROOT / "src/suravidl_engine/web/index.html").read_text()
STYLE = (ROOT / "src/suravidl_engine/web/style.css").read_text()
POPUP = (ROOT / "extension/popup.css").read_text()
APIPY = (ROOT / "src/suravidl_engine/api.py").read_text()
JOBS = (ROOT / "src/suravidl_engine/jobs.py").read_text()


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def wait_done(mgr, job_id, timeout=30):
    for _ in range(int(timeout * 10)):
        j = mgr.get(job_id)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.1)
    return mgr.get(job_id)


# -- engine: the deletion bug ------------------------------------------------

def test_resumed_stale_row_deletion_keeps_the_finished_file(tmp_path, fixture_server):
    """Resume makes a new row; the old paused card must stop owning the file.

    Reproduction of the audit's worst finding: pause a job (row keeps the
    named target), resume it as a new row, let THAT finish, then trash the
    stale card — the finished file must survive.
    """
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create(f"{fixture_server}/tiny.mp4")
    j = wait_done(mgr, job["id"])
    assert j["status"] == "completed", j
    final = Path(j["filepath"])
    assert final.exists()

    # the exact state a mid-download pause records: named targets, no `files`
    with mgr._lock:                       # noqa: SLF001 - simulating the hook
        row = mgr._jobs[job["id"]]        # noqa: SLF001
        row["status"] = "paused"
        row["files"] = None
    mgr._save(row)

    resumed = mgr.resume(job["id"])
    done = wait_done(mgr, resumed["id"])
    assert done["status"] == "completed", done
    assert final.exists(), "the resumed job's own download must land"

    mgr.delete_job(job["id"])             # the stale card, trashed late
    assert final.exists(), "trashing the stale row removed the finished file"
    assert mgr.get(resumed["id"])["status"] == "completed"


def test_paused_row_never_resumed_still_cleans_its_part(tmp_path):
    """The fix must not over-reach: a truly abandoned pause still cleans up."""
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create("http://127.0.0.1:1/never.mp4")
    with mgr._lock:                       # noqa: SLF001
        row = mgr._jobs[job["id"]]        # noqa: SLF001
        row["status"] = "paused"
        row["filepath"] = str(tmp_path / "movie.mp4")
        row["partials"] = [str(tmp_path / "movie.mp4")]
        row["progress"] = dict(row["progress"])
    mgr._save(row)
    part = tmp_path / "movie.mp4.part"
    part.write_bytes(b"half")

    mgr.delete_job(job["id"])
    assert not part.exists(), "an abandoned pause keeps its cleanup duty"
    with pytest.raises(KeyError):
        mgr.get(job["id"])


def test_requeue_strips_the_source_of_its_claim(tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    job = mgr.create("http://127.0.0.1:1/x.mp4")
    with mgr._lock:                       # noqa: SLF001
        row = mgr._jobs[job["id"]]        # noqa: SLF001
        row["status"] = "paused"
        row["filepath"] = str(tmp_path / "x.mp4")
        row["partials"] = [str(tmp_path / "x.mp4")]
    mgr._save(row)

    mgr.resume(job["id"])
    live = mgr.get(job["id"])
    assert live["filepath"] is None and not live["partials"]
    assert "deleted" not in str(live.get("error") or "")


# -- engine: raw-args denylist ----------------------------------------------

def test_raw_args_denies_the_print_to_file_family():
    from suravidl_engine.download_opts import parse_raw_args

    for raw, marker in (
        ("--print-to-file '%(id)s' /tmp/out.txt", "--print-to-file"),
        ("--print '%(id)s'", "--print"),
        ("--postprocessor-args 'ffmpeg:-y'", "--postprocessor-args"),
        ("--ppa 'ffmpeg:-y'", "--ppa"),
    ):
        with pytest.raises(ValueError) as err:
            parse_raw_args(raw)
        assert marker in str(err.value), (raw, str(err.value))


# -- engine: SSRF guard spellings --------------------------------------------

def test_ssrf_guard_canonicalizes_alternate_ip_spellings():
    from suravidl_engine.classify import blocked_reason

    for spell in ("http://2852039166/",                 # decimal dword
                  "http://0xa9.0xfe.0xa9.0xfe/",        # hex octets
                  "http://[::ffff:169.254.169.254]/",   # IPv4-mapped IPv6
                  "http://169.254.169.254/"):           # the plain one
        assert blocked_reason(spell), spell
    assert blocked_reason("http://metadata.google.internal/")
    assert blocked_reason("http://[fd00:ec2::254]/")
    # the intentional freedoms stay free: a LAN NAS, loopback, the open net
    assert blocked_reason("http://192.168.1.8/nas.mp4") == ""
    assert blocked_reason("http://127.0.0.1:8787/") == ""
    assert blocked_reason("https://video.example.com/watch?v=1") == ""


# -- engine: updater tells the truth about bundled builds --------------------

def test_updater_sends_bundled_builds_to_the_wheel_path(monkeypatch):
    """v0.40.10 said "no pip, no update"; v0.43.0 gave those builds the
    PyPI wheel path instead, so pip-absence now routes there. The bundled
    flag keeps describing the build — it is no longer a dead end."""
    from suravidl_engine import updater, ytdlp_update

    monkeypatch.setattr(updater, "updates_possible", lambda: False)
    monkeypatch.setattr(ytdlp_update, "stage_update",
                        lambda db_path=None, before=None: {
                            "ok": False, "updated": False, "bundled": True,
                            "before": before, "after": before,
                            "detail": "couldn't reach PyPI: no network"})
    r = updater.self_update()
    assert r["ok"] is False and r["bundled"] is True


def test_this_venv_can_update(monkeypatch):
    from suravidl_engine import updater

    assert updater.updates_possible() is True


def test_update_check_reports_bundled(tmp_path):
    from suravidl_engine.api import create_app

    app = create_app(download_dir=tmp_path, auth_token="t",
                     db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        r = c.get("/update-check", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200
        assert "bundled" in r.json()


# -- engine: archive forget holds the pen ------------------------------------

def test_archive_forget_keeps_unrelated_entries(tmp_path):
    from suravidl_engine.api import create_app

    db = tmp_path / "jobs.db"
    app = create_app(download_dir=tmp_path, auth_token="t", db_path=db)
    (tmp_path / "archive.txt").write_text("aaa\nbbb\nccc\n")
    with TestClient(app) as c:
        r = c.post("/archive/forget", json={"entry": "bbb"},
                   headers={"Authorization": "Bearer t"})
        assert r.status_code == 200, r.text
    text = (tmp_path / "archive.txt").read_text()
    assert "bbb" not in text and "aaa" in text and "ccc" in text
    assert "_ARCHIVE_LOCK" in APIPY, "the read-modify-replace needs its lock"


# -- engine: handoff bursts stay bounded -------------------------------------

def test_handoff_burst_is_bounded(tmp_path):
    from suravidl_engine.handoff import HandoffStore

    active = {"now": 0, "max": 0}
    guard = threading.Lock()

    def probe(url, headers):
        with guard:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.12)
        with guard:
            active["now"] -= 1
        return {"ok": True}

    store = HandoffStore(probe_fn=probe)
    for i in range(8):
        store.add(f"http://x.example/stream{i}.mp4")   # distinct: no dedupe
    time.sleep(1.6)
    assert active["max"] <= 3, f"probing ran {active['max']} at once"


# -- engine: filename template drives ----------------------------------------

def test_template_rejects_windows_drive_prefixes():
    from suravidl_engine.download_opts import validate_template

    with pytest.raises(ValueError):
        validate_template("D:sub/%(title)s.%(ext)s")
    assert validate_template("sub/%(title)s.%(ext)s")


# -- engine: the boundary message says what it protects ----------------------

def test_require_inside_speaks_of_touching_not_deleting(tmp_path):
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path / "dl")
    outside = tmp_path / "outside.mp4"
    with pytest.raises(PermissionError) as err:
        mgr._require_inside(outside, None)   # noqa: SLF001
    assert "outside the download folder" in str(err.value)
    assert "delete" not in str(err.value)


# -- web: one lamp per plate -------------------------------------------------

def test_one_lamp_rule_holds_in_the_paste_card():
    assert 'id="probeBtn" class="btn prime"' in INDEX
    assert 'id="browserOfferBtn" class="btn sm"' in INDEX, \
        "the browser offer must not be a second filled amber lamp"
    assert 'id="batchBtn" class="btn sm"' in INDEX, \
        "queue-all is contextual, not the plate's lamp"
    assert 'id="presetSave" class="btn sm"' in INDEX, \
        "the sticky Save is the Presets plate's lamp; the card's save steps back"
    assert 'id="setSave" class="btn prime"' in INDEX


# -- web: START reflects an empty forecourt ----------------------------------

def test_start_button_reflects_the_empty_forecourt():
    assert "function syncStartState(" in APPJS
    assert 'bestBtn").disabled = empty' in APPJS
    assert '$("url").addEventListener("input", syncStartState)' in APPJS
    assert "syncStartState();" in APPJS, "called once at boot"


# -- web: modal focus discipline ---------------------------------------------

def test_modals_trap_tab_and_return_focus():
    assert "function modalFocusables(" in APPJS
    assert "m._returnFocus" in APPJS
    assert "m._trap" in APPJS
    assert "back.focus()" in APPJS, "focus returns to the trigger"


# -- web: Escape belongs to the top card -------------------------------------

def test_escape_is_first_answered_by_the_player_and_sheet():
    assert 'if (!$("playModal").classList.contains("hidden")) return;' in APPJS
    assert 'if (!$("folderModal").classList.contains("hidden")) return;' in APPJS


# -- web: the light focus ring clears 3:1 ------------------------------------

def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def ch(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = ch(r), ch(g), ch(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_light_focus_ring_clears_three_to_one():
    block = re.search(r'html\[data-theme="light"\] \{([^}]*)\}', STYLE).group(1)
    bg = re.search(r"--bg:\s*(#[0-9a-fA-F]{6})", block).group(1)
    ring = re.search(r"--ring:\s*(#[0-9a-fA-F]{6})", block)
    assert ring, "the light room needs its own focus-ring colour"
    lo, hi = sorted((_lum(bg), _lum(ring.group(1))))
    ratio = (hi + 0.05) / (lo + 0.05)
    assert ratio >= 3.0, f"light focus ring {ring.group(1)} on {bg} = {ratio:.2f}:1"


# -- web: main tabs follow the APG pattern -----------------------------------

def test_main_tabs_follow_the_apg_pattern():
    for t in ("download", "queue", "settings", "ytdlp"):
        assert f'id="tab{t.capitalize()}"' in INDEX
        assert f'aria-controls="panel-{t}"' in INDEX
        assert f'aria-labelledby="tab{t.capitalize()}"' in INDEX
    assert INDEX.count('role="tabpanel"') >= 4
    assert "function syncTabA11y(" in APPJS
    i_tabs = APPJS.index("function syncTabA11y(")
    seg = APPJS[i_tabs:i_tabs + 1400]
    assert '"ArrowRight"' in seg and '"ArrowLeft"' in seg, "arrow keys move tabs"
    assert "syncTabA11y();" in APPJS


# -- web: a failed probe must not revive the onboarding ----------------------

def test_a_failed_probe_does_not_revive_the_onboarding():
    i = APPJS.index("probe failed: ")
    seg = APPJS[i:i + 1600]
    assert 'dlEmpty' in seg
    assert 'dlEmpty").classList.remove("hidden")' not in APPJS, \
        "the empty state is for empty decks, not for failures"


# -- web: playlist picks are tappable ----------------------------------------

def test_playlist_picks_grow_and_the_cell_works():
    assert "pick.onclick" in APPJS, "the whole number cell picks, not just the box"
    assert "box.checked = !box.checked" in APPJS
    coarse = STYLE[STYLE.index("@media (pointer: coarse)"):]
    assert ".plpick" in coarse, "coarse pointers get a grown check target"


# -- web: reduced motion keeps a static light --------------------------------

def test_reduced_motion_keeps_a_static_light():
    i = STYLE.index("prefers-reduced-motion")
    block = STYLE[i:i + 1400]
    assert "animation: none !important" in block
    assert ".btn.busy" in block, "a busy control must stay visibly busy"
    assert "animation-iteration-count: 1" in STYLE, "the original kill stays"


# -- web: nothing sharper than 8px -------------------------------------------

def test_nothing_sharper_than_eight_px():
    seg = STYLE[STYLE.index(".job .stamp, .stamp {"):][:400]
    assert "border-radius: 8px" in seg
    more = POPUP[POPUP.index(".more {"):][:400]
    assert "border-radius: 8px" in more
    assert "font-size: 11px" in more, "the 9.5px label grew to the floor"


# -- web: packaged builds update from PyPI now -------------------------------

def test_bundled_builds_no_longer_disable_the_update_button():
    """v0.40.10 greyed the button while there was nothing pip could do.
    v0.43.0 gave packaged builds the wheel path, so it stays live — the
    tooltip only says where an update comes from now."""
    assert "u.bundled" in APPJS
    seg = APPJS[APPJS.index("u.bundled"):][:600]
    assert ".disabled" not in seg
    assert "PyPI" in seg
    seg2 = APIPY[APIPY.index('@app.get("/update-check")'):][:900]
    assert '"bundled"' in seg2


# -- android: the session cookies leave with the service ---------------------

def test_service_wipes_session_cookies_on_destroy():
    src = (ROOT / "android/app/src/main/java/com/suravidl/app/EngineService.kt").read_text()
    i = src.index("override fun onDestroy()")
    seg = src[i:i + 700]
    assert "CookieVault.lockSession" in seg


def test_gallery_importer_covers_engine_formats():
    classify = (ROOT / "src/suravidl_engine/classify.py").read_text()
    engine = set(re.search(r"VIDEO_EXT = \(([^)]*)\)", classify)
                 .group(1).replace('"', "").replace(" ", "").split(","))
    kotlin = (ROOT / "android/app/src/main/java/com/suravidl/app/MediaImporter.kt").read_text()
    kset = set(re.findall(r'"([a-z0-9]+)"', re.search(
        r"VIDEO_EXT = setOf\(([^)]*)\)", kotlin, re.S).group(1)))
    assert engine <= kset, f"missing from the importer: {engine - kset}"
