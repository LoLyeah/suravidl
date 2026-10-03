"""v0.40.6 "the tally" — the queue, readable from outside the window.

macOS paints the Dock tile's badge label, Linux docks that speak Unity's
LauncherEntry protocol get a count, and every other desktop wears it in
the window title. A failed read is silence — never a crash, and never a
zero: "unknown" must not clear a truthful badge.
"""
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text()

from suravidl_engine import __main__ as shell


class FakeWindow:
    """A window that remembers every title it was given."""

    def __init__(self):
        self.writes = []

    @property
    def title(self):
        return self.writes[-1] if self.writes else "suravidl"

    @title.setter
    def title(self, value):
        self.writes.append(value)


@pytest.fixture()
def jobs_server():
    state = {"count": 2, "auth": "Bearer testtoken"}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if (self.path != "/jobs"
                    or self.headers.get("Authorization") != state["auth"]):
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps(
                {"jobs": [{"status": "downloading"}] * state["count"]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: D102 - quiet test server
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", state
    server.shutdown()


def test_badge_text_clears_and_caps():
    assert shell.badge_text(0) == ""
    assert shell.badge_text(-1) == ""
    assert shell.badge_text(3) == "3"
    assert shell.badge_text(99) == "99"
    assert shell.badge_text(100) == "99+"


def test_only_going_jobs_count():
    jobs = [
        {"status": "downloading"}, {"status": "queued"}, {"status": "merging"},
        {"status": "done"}, {"status": "error"}, {"status": "paused"}, {},
    ]
    assert shell.active_count(jobs) == 3
    assert shell.active_count([]) == 0


def test_the_title_speaks_grammar_and_rests_when_clear():
    assert shell.title_for(0) == "suravidl"
    assert shell.title_for(1) == "suravidl — 1 job"
    assert shell.title_for(2) == "suravidl — 2 jobs"
    assert shell.title_for(150) == "suravidl — 99+ jobs"


def test_reads_the_engines_own_count(jobs_server):
    base, state = jobs_server
    assert shell.read_active(base, "testtoken") == 2
    state["count"] = 0
    assert shell.read_active(base, "testtoken") == 0
    assert shell.read_active(base, "wrong-token") is None
    assert shell.read_active("http://127.0.0.1:1", "testtoken") is None


def test_one_step_reads_then_repaints_only_on_change(jobs_server, monkeypatch):
    base, state = jobs_server
    window = FakeWindow()
    shell._BADGE["last"] = None
    monkeypatch.setattr(sys, "platform", "win32")  # the title floor, determinstic

    shell._badge_once(window, base, "testtoken")
    assert window.title == "suravidl — 2 jobs"
    n = len(window.writes)
    shell._badge_once(window, base, "testtoken")   # same count: no repaint
    assert len(window.writes) == n

    state["count"] = 0
    shell._badge_once(window, base, "testtoken")
    assert window.title == "suravidl"

    state["count"] = 5
    shell._badge_once(window, base, "testtoken")
    assert window.title == "suravidl — 5 jobs"
    monkeypatch.setattr(shell, "read_active", lambda *a, **k: None)
    shell._badge_once(window, base, "testtoken")   # unknown: silence
    assert window.title == "suravidl — 5 jobs", \
        "unknown must not clear a truthful badge"


def test_the_dock_badge_paints_and_clears(monkeypatch):
    recorded = []

    class DockTile:
        def setBadgeLabel_(self, value):  # noqa: N802 - the AppKit spelling
            recorded.append(value)

    class Application:
        @staticmethod
        def sharedApplication():  # noqa: N802
            return type("A", (), {"dockTile": staticmethod(lambda: DockTile())})()

    fake_appkit = type("K", (), {"NSApplication": Application})()
    monkeypatch.setattr(shell, "_import_appkit", lambda: (fake_appkit, None))
    assert shell._set_dock_badge("3") is True
    assert shell._set_dock_badge("") is True
    assert recorded == ["3", None], "empty clears the tile with None"


def test_a_mac_without_appkit_degrades(monkeypatch):
    monkeypatch.setattr(shell, "_import_appkit", lambda: (None, None))
    assert shell._set_dock_badge("3") is False


def test_the_poller_is_wired_and_daemonic():
    assert "_start_badge_poller(window, url, token)" in MAIN
    block = MAIN.split("def _start_badge_poller")[1][:400]
    assert "daemon=True" in block, "the watch sleeps; the app must not"
    assert "com.canonical.Unity.LauncherEntry" in MAIN
    assert "setBadgeLabel_" in MAIN
    assert "_BADGE_EVERY = 2.5" in MAIN
