"""Desktop window controls: /app/info, /app/minimize, /app/quit, reveal-on-complete."""
import http.server
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine.api import create_app

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer t"}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(FIXTURES), **kw)

    def log_message(self, *a):
        pass


def make_app(tmp_path, **kw):
    return create_app(download_dir=tmp_path / "dl", auth_token="t",
                      db_path=tmp_path / "jobs.db", **kw)


def test_app_info_no_desktop(tmp_path):
    c = TestClient(make_app(tmp_path))
    info = c.get("/app/info", headers=AUTH).json()
    assert info == {"desktop": False, "can_minimize": False}


def test_window_actions_501_without_desktop(tmp_path):
    c = TestClient(make_app(tmp_path))
    assert c.post("/app/minimize", headers=AUTH).status_code == 501
    assert c.post("/app/quit", headers=AUTH).status_code == 501


def test_window_actions_invoke_hooks(tmp_path):
    calls = []
    actions = {"minimize": lambda: calls.append("min"),
               "quit": lambda: calls.append("quit")}
    c = TestClient(make_app(tmp_path, desktop_actions=actions))
    info = c.get("/app/info", headers=AUTH).json()
    assert info == {"desktop": True, "can_minimize": True}
    assert c.post("/app/minimize", headers=AUTH).status_code == 200
    assert c.post("/app/quit", headers=AUTH).status_code == 200
    assert calls == ["min", "quit"]


def test_window_actions_need_auth(tmp_path):
    actions = {"minimize": lambda: None, "quit": lambda: None}
    c = TestClient(make_app(tmp_path, desktop_actions=actions))
    assert c.get("/app/info").status_code == 401
    assert c.post("/app/minimize").status_code == 401
    assert c.post("/app/quit").status_code == 401


def test_reveal_on_complete(tmp_path):
    """With the option on, a finished job reveals its file (desktop only)."""
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        revealed = []
        actions = {"reveal": revealed.append}
        c = TestClient(make_app(tmp_path, desktop_actions=actions))
        c.post("/settings", headers=AUTH, json={"open_dir_on_complete": True})
        job = c.post("/jobs", headers=AUTH,
                     json={"url": f"http://127.0.0.1:{srv.server_address[1]}/tiny.mp4"}).json()
        deadline = time.time() + 30
        while time.time() < deadline:
            status = c.get(f"/jobs/{job['id']}", headers=AUTH).json()["status"]
            if status in ("completed", "error"):
                break
            time.sleep(0.2)
        assert status == "completed"
        deadline = time.time() + 5
        while not revealed and time.time() < deadline:
            time.sleep(0.05)
        assert revealed and revealed[0].endswith("tiny.mp4")
    finally:
        srv.shutdown()
