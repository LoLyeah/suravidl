"""v0.47.28 "the tap" — one-tap download, and a notification that says something.

Feature #1 and #2 from docs/FEATURES-NEXT.md: the two things every comparable
app (YTDLnis, Seal, cobalt) does that suravidl made you work for — the format
list on every link, and a notification that only knows how to count.
"""
import pathlib

from suravidl_engine import __version__
from suravidl_engine.settings import DEFAULTS
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
HTML = (WEB / "index.html").read_text()
APP = (WEB / "app.js").read_text()
CSS = (WEB / "style.css").read_text()
SERVICE = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
           "suravidl" / "app" / "EngineService.kt").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.47.28"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the tap"
    assert len(ENTRIES) == 10
    for item in ENTRIES[0]["items"]:
        assert 0 < len(item) <= 220


def test_the_button_is_there_and_wired():
    assert 'id="quickBtn"' in HTML
    assert 'data-i18n="Download now"' in HTML
    assert 'if ($("quickBtn")) $("quickBtn").onclick = quickStart;' in APP
    assert "async function quickStart()" in APP
    body = APP[APP.index("async function quickStart()"):]
    body = body[:body.index("\n}\n") + 3]
    assert "startJob(url" in body and 'showTab("queue")' in body


def test_the_paste_row_survives_two_buttons():
    assert ".paste { display: flex; gap: 10px; flex-wrap: wrap; }" in CSS
    assert "@media (max-width: 560px) { .paste .btn { flex: 1 1 auto; } }" in CSS


def test_a_share_can_skip_the_format_list():
    assert "quick_share" in APP
    body = APP[APP.index("window.suravidlShared"):]
    body = body[:body.index("\n};") + 3]
    assert "SETTINGS_SNAPSHOT.quick_share" in body
    assert "quickStart()" in body


def test_the_setting_exists_and_is_off_by_default():
    assert DEFAULTS.get("quick_share") is False
    assert 'id="setQuickShare"' in HTML
    assert "quick_share: !!($(\"setQuickShare\")" in APP


def test_the_notification_reports_progress_and_can_cancel():
    assert "private fun activeJobs()" in SERVICE
    assert "private fun buildProgress(" in SERVICE
    assert "setProgress(100, j.pct, false)" in SERVICE
    assert "addAction(android.R.drawable.ic_menu_close_clear_cancel" in SERVICE
    assert "fun speedText(" in SERVICE and "fun etaText(" in SERVICE


def test_cancel_is_answered_before_the_engine_guard():
    body = SERVICE[SERVICE.index("override fun onStartCommand"):]
    body = body[:body.index("engineStarted = true")]
    assert "ACTION_CANCEL" in body
    assert "cancelJob(" in body
    assert "/jobs/$id/cancel" in SERVICE


def test_quick_share_round_trips_and_stays_app_level(tmp_path):
    """A setting the UI writes must survive a POST, and a JOB must not be able
    to set it for itself."""
    from fastapi.testclient import TestClient

    from suravidl_engine import api, settings

    assert "quick_share" in settings.PER_JOB_DENIED
    app = api.create_app(download_dir=tmp_path / "dl", auth_token="t",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        h = {"Authorization": "Bearer t"}
        assert c.get("/settings", headers=h).json()["quick_share"] is False
        assert c.post("/settings", headers=h, json={"quick_share": True}).status_code == 200
        assert c.get("/settings", headers=h).json()["quick_share"] is True
