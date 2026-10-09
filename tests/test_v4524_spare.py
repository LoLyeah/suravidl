"""v0.45.24 "the spare" — a stalled worker is replaced, not mourned.

The v0.45.22 watchdog made a stalled download's ROW honest, but its
worker thread stays wedged in a read Python cannot interrupt — and its
capacity slot stayed eaten for the life of the process. Two stalls on a
phone (capacity 2) and the queue goes permanently dead: jobs sit at
"queued" and nothing ever runs them. That is the exact shape the field
report showed (2026-10-08: a fresh job queued and never started, while
the engine still answered).

Now the stall watch frees the slot and puts a spare worker on duty; the
zombie thread stays parked (one thread, one socket) and its own exit
path is idempotent, so a slot is never counted twice.
"""
import socket
import threading
import time

from suravidl_engine import jobs as jobs_mod
from suravidl_engine.jobs import JobManager


def _drip_server():
    """Accepts connections; sends nothing, ever."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    held = []
    stop = threading.Event()

    def run():
        srv.settimeout(0.5)
        while not stop.is_set():
            try:
                c, _ = srv.accept()
                held.append(c)
            except socket.timeout:
                continue
            except OSError:
                return

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], stop, held


def test_a_stalled_worker_is_replaced_so_the_queue_keeps_moving(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_mod, "STALL_LIMIT", 2.5)
    monkeypatch.setattr(jobs_mod, "STALL_POLL", 0.4)
    port, stop, held = _drip_server()
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db",
                     auto_resume=True, max_concurrent=1)

    a = mgr.create(f"http://127.0.0.1:{port}/first.mp4")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and mgr.get(a["id"])["status"] != "error":
        time.sleep(0.2)
    assert mgr.get(a["id"])["status"] == "error", "the stall must land"

    # the slot must be free now — with it still eaten, B can never be
    # claimed and sits at "queued" forever (the phone's dead-queue shape)
    b = mgr.create(f"http://127.0.0.1:{port}/second.mp4")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if mgr.get(b["id"])["status"] == "downloading":
            break
        time.sleep(0.2)
    assert mgr.get(b["id"])["status"] == "downloading", \
        "a spare worker must pick the next job up"
    stop.set()
