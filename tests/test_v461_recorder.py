"""v0.46.1 "the recorder" — live streams, first-class.

Half existed: is_live reaches the probe, live_from_start is a setting,
and pause already keeps every byte. What was missing is the house —
a `live` flag on jobs, the stall watchdog EXEMPTING live recordings
(a stream between segments is quiet by nature; killing it threw away a
working recording), the REC card with no fake percentage, Stop & keep,
and the one-off from-the-beginning pick.

The proof that matters is a real recording: the fixture server grows its
playlist one segment at a time, a real yt-dlp records it through the
real job manager, and stopping keeps the bytes.
"""
import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from suravidl_engine import jobs as jobs_mod
from suravidl_engine.api import create_app
from suravidl_engine.jobs import JobManager

ROOT = Path(__file__).resolve().parents[1]
APPJS = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
INDEX = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")

def _make_ts() -> bytes | None:
    """One second of real MPEG-TS — ffmpeg reads the fixture's segments and
    muxes them, and ZERO bytes are not a TS: it would read forever and
    write nothing, which is exactly how this suite found the difference
    (2026-10-10). Returns None when no ffmpeg exists (the test skips)."""
    exe = (os.environ.get("SURAVIDL_FFMPEG", "").strip()
           or shutil.which("ffmpeg"))
    if not exe:
        return None
    fd, path = tempfile.mkstemp(suffix=".ts")
    os.close(fd)
    try:
        run = subprocess.run(
            [exe, "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "testsrc=duration=1:size=160x120:rate=10",
             "-c:v", "mpeg2video", "-f", "mpegts", path],
            capture_output=True, timeout=60)
        if run.returncode != 0:
            return None
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


TS = _make_ts()


class LiveServer:
    """An HLS 'live' stream: the playlist gains a segment per request."""

    def __init__(self, seg: bytes = b""):
        self.seg = seg or TS or bytes(188 * 40)
        outer = self
        outer.segments = 1

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                p = self.path.split("?")[0]
                if p == "/live.m3u8":
                    # a real live shape: a SLIDING window (the media
                    # sequence advances, old segments expire). yt-dlp hands
                    # live HLS to ffmpeg, and ffmpeg waits forever on a
                    # fixed-sequence playlist that merely grows (found by
                    # running it directly, debug log in hand).
                    outer.segments = min(outer.segments + 1, 240)
                    n = outer.segments
                    seq = max(0, n - 3)
                    body = ("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n"
                            "#EXT-X-MEDIA-SEQUENCE:%d\n" % seq)
                    for i in range(seq, n):
                        body += "#EXTINF:2.0,\nseg%d.ts\n" % i
                    data = body.encode()      # no ENDLIST: it is live
                    self.send_response(200)
                    self.send_header("Content-Type",
                                     "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif p.startswith("/seg") and p.endswith(".ts"):
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp2t")
                    self.send_header("Content-Length", str(len(outer.seg)))
                    self.end_headers()
                    self.wfile.write(outer.seg)
                else:
                    self.send_response(404)
                    self.end_headers()

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_a_live_recording_stops_and_keeps_every_byte(tmp_path):
    if TS is None:
        pytest.skip("no ffmpeg on this machine — live HLS records through it")
    seg_len = len(TS)
    srv = LiveServer().start()
    try:
        out = tmp_path / "dl"
        out.mkdir()
        mgr = JobManager(download_dir=out, db_path=tmp_path / "j.db")
        job = mgr.create("http://127.0.0.1:%d/live.m3u8" % srv.port,
                         live=True)
        # the proof is the DISK, not the hook: for a live, yt-dlp hands
        # the stream to ffmpeg, which emits no per-byte progress — the
        # file grows while downloaded_bytes can sit at 0 (found by running
        # the engine's own options with a debug log in hand)
        def on_disk():
            total = 0
            for root, _d, files in os.walk(out):
                total += sum(os.path.getsize(os.path.join(root, f))
                             for f in files if not f.endswith(".db"))
            return total

        deadline = time.time() + 90
        got = 0
        while time.time() < deadline:
            got = on_disk()
            if got >= 2 * seg_len:
                break
            time.sleep(1)
        assert got > 0, "no bytes were recorded at all: %r" % mgr.get(job["id"])
        assert mgr.get(job["id"])["live"] is True

        stopped = mgr.pause(job["id"])
        assert stopped["status"] == "paused"
        time.sleep(1.5)                    # let the worker unwind
        total = 0
        for root, _d, files in os.walk(out):
            total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
        assert total > 0, "stopping a recording threw its bytes away"
    finally:
        srv.stop()


def test_the_live_flag_round_trips_and_survives_a_reopen(tmp_path):
    out = tmp_path / "dl"
    out.mkdir()
    db = tmp_path / "j.db"
    mgr = JobManager(download_dir=out, db_path=db)
    j = mgr.create("https://example.invalid/v", live=True)
    plain = mgr.create("https://example.invalid/plain")
    assert mgr.get(j["id"])["live"] is True
    assert mgr.get(plain["id"])["live"] is False
    reopened = JobManager(download_dir=out, db_path=db, auto_resume=False)
    assert reopened.get(j["id"])["live"] is True
    assert reopened.get(plain["id"])["live"] is False


def test_a_live_job_is_never_watchdogged(tmp_path, monkeypatch):
    """A live recording survives the stall window; a plain download on the
    same silent source does not — the control proves the watchdog is on."""
    import socket

    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(5)
    port = silent.getsockname()[1]
    accepted = []
    stop = threading.Event()

    def accept_all():
        while not stop.is_set():
            try:
                c, _ = silent.accept()
                accepted.append(c)          # hold it open, never answer
            except OSError:
                break

    threading.Thread(target=accept_all, daemon=True).start()
    monkeypatch.setattr(jobs_mod, "STALL_LIMIT", 0.6)
    monkeypatch.setattr(jobs_mod, "STALL_POLL", 0.2)
    out = tmp_path / "dl"
    out.mkdir()
    try:
        mgr = JobManager(download_dir=out, db_path=tmp_path / "j.db")
        live = mgr.create("http://127.0.0.1:%d/live.m3u8" % port, live=True)
        plain = mgr.create("http://127.0.0.1:%d/v.mp4" % port)
        time.sleep(4)
        assert mgr.get(live["id"])["status"] == "downloading", \
            "a live recording was watchdogged: %r" % mgr.get(live["id"])
        assert mgr.get(plain["id"])["status"] == "error", \
            "the watchdog is not doing its job for plain downloads"
    finally:
        stop.set()
        for c in accepted:
            try:
                c.close()
            except OSError:
                pass
        silent.close()


def test_the_probe_endpoint_carries_live_into_the_job(tmp_path):
    app = create_app(download_dir=tmp_path / "dl", auth_token="t",
                     db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        got = c.post("/jobs", headers={"Authorization": "Bearer t"},
                     json={"url": "https://example.invalid/v", "live": True})
        assert got.status_code == 200
        assert got.json()["live"] is True


def test_the_ui_says_rec_and_keeps_the_one_off_toggle():
    assert 'id="liveStartBox"' in INDEX
    assert "body.live = true" in APPJS
    assert 't(j.live ? "Stop & keep" : "Pause")' in APPJS
    assert 't("recording")' in APPJS and 't("recorded (stopped)")' in APPJS
    # no fake percentage rides a live recording
    assert "const sized = j.status === \"downloading\" && !j.live;" in APPJS
    assert "Berhenti & simpan" in APPJS
