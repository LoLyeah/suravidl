"""v0.47.22 "the redo" — a retry has to remember where the link came from.

The report: tap "Retry without certificate check" on the certificate row and
the row comes back as "the site's media server refuses requests that do not
come from its page". That is exactly what happened — the button built a NEW
job from `j.url` and dropped the referer the first job carried, so the CDN
answered /404.html. It now retries the JOB, which clones its headers.
"""
import pathlib
import time

from suravidl_engine import __version__, api
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
BROWSER = (ROOT / "android" / "app" / "src" / "main" / "java" / "com" /
           "suravidl" / "app" / "BrowserActivity.kt").read_text()
AUTH = {"Authorization": "Bearer testtoken"}


def test_the_notes_name_this_release():
    assert __version__ == "0.47.22"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the redo"
    assert len(ENTRIES) == 10


def test_the_button_retries_the_job_not_a_bare_url():
    block = APP[APP.index('t("Retry without certificate check")'):]
    block = block[:block.index("r.append(loose)")]
    assert "`/jobs/${j.id}/retry`" in block
    assert 'api("/jobs", { method: "POST"' not in block, (
        "a new job drops the referer the original carried")


def test_an_incomplete_chain_is_not_called_self_signed():
    assert "/self-signed/i" in APP
    assert "/local issuer|unknown ca|unable to (get|verify)/i" in APP
    assert "did not send the intermediate certificate" in APP


def test_the_webview_allows_script_started_playback():
    assert "mediaPlaybackRequiresUserGesture = false" in BROWSER


def test_a_retry_keeps_the_referer_and_takes_the_override(tmp_path):
    """The engine half: retry clones the row (headers included)."""
    d = pathlib.Path(tmp_path)
    app = api.create_app(download_dir=d / "dl", auth_token="testtoken",
                         db_path=d / "jobs.db")
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        made = c.post("/jobs", headers=AUTH, json={
            "url": "http://127.0.0.1:9/nothing.mp4",
            "headers": {"referer": "https://site.example/watch/x/"},
        })
        assert made.status_code == 200, made.text
        jid = made.json()["id"]
        for _ in range(80):
            if c.get(f"/jobs/{jid}", headers=AUTH).json()["status"] in (
                    "error", "completed", "cancelled"):
                break
            time.sleep(0.05)
        again = c.post(f"/jobs/{jid}/retry", headers=AUTH,
                       json={"overrides": {"no_check_certificates": True}})
        assert again.status_code == 200, again.text
        new = again.json()
        assert new["overrides"]["no_check_certificates"] is True
        assert (new.get("headers") or {}).get("referer") == "https://site.example/watch/x/"
