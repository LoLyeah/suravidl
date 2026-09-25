"""Live smoke test: real engine process + real HTTP + real download."""
import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PY = ROOT / ".venv" / "bin" / "python"
TOKEN = "smoketoken123"


def req(method, url, body=None, token=TOKEN):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    # local fixture server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(FIXTURES))
    fs = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=fs.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{fs.server_address[1]}"

    dl_dir = Path(tempfile.mkdtemp(prefix="suravidl_smoke_"))
    home = Path(tempfile.mkdtemp(prefix="suravidl_smoke_home_"))
    env = dict(os.environ, SURAVIDL_TOKEN=TOKEN, HOME=str(home))
    eng = subprocess.Popen(
        [str(PY), "-m", "suravidl_engine.api", "--port", "8799",
         "--download-dir", str(dl_dir)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        # wait for health
        for _ in range(50):
            try:
                h = req("GET", "http://127.0.0.1:8799/health", token="")
                break
            except Exception:
                time.sleep(0.2)
        else:
            print("ENGINE_FAILED_TO_START")
            sys.exit(1)

        info = req("POST", "http://127.0.0.1:8799/probe",
                   {"url": f"{base}/tiny.mp4"})
        assert info["ext"] == "mp4", info

        job = req("POST", "http://127.0.0.1:8799/jobs",
                  {"url": f"{base}/tiny.mp4"})
        jid = job["id"]
        for _ in range(200):
            j = req("GET", f"http://127.0.0.1:8799/jobs/{jid}")
            if j["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert j["status"] == "completed", j
        assert Path(j["filepath"]).exists(), j

        # -- playlists -------------------------------------------------------
        pl = req("POST", "http://127.0.0.1:8799/probe",
                 {"url": f"{base}/playlist.html"})
        assert pl["playlist"] is True and pl["count"] == 2, pl

        pj = req("POST", "http://127.0.0.1:8799/jobs",
                 {"url": f"{base}/playlist.html", "playlist_items": "1-1"})
        for _ in range(300):
            pjp = req("GET", f"http://127.0.0.1:8799/jobs/{pj['id']}")
            if pjp["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert pjp["status"] == "completed", pjp
        assert pjp["playlist_count"] == 1, pjp
        assert len(list(dl_dir.glob("*.mp4"))) == 2, list(dl_dir.iterdir())

        # -- tier-1 settings: round-trip + a real postprocessed download -----
        s = req("POST", "http://127.0.0.1:8799/settings",
                {"embed_metadata": True, "fragments": 4, "rate_limit": "5M",
                 "subtitles_mode": "sidecar", "sponsorblock_mode": "mark"})
        assert s["embed_metadata"] is True and s["fragments"] == 4, s
        assert s["rate_limit"] == "5M" and s["subtitles_mode"] == "sidecar", s

        ej = req("POST", "http://127.0.0.1:8799/jobs",
                 {"url": f"{base}/tiny.mp4"})
        for _ in range(300):
            ejp = req("GET", f"http://127.0.0.1:8799/jobs/{ej['id']}")
            if ejp["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert ejp["status"] == "completed", ejp

        # -- archive: enabling it must make the second run a no-op -----------
        req("POST", "http://127.0.0.1:8799/settings", {"archive": True})
        # first run with the archive on records the URL...
        a1 = req("POST", "http://127.0.0.1:8799/jobs", {"url": f"{base}/tone.m4a"})
        for _ in range(300):
            a1p = req("GET", f"http://127.0.0.1:8799/jobs/{a1['id']}")
            if a1p["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert a1p["status"] == "completed", a1p
        # ...so the next run is skipped explicitly
        a2 = req("POST", "http://127.0.0.1:8799/jobs", {"url": f"{base}/tone.m4a"})
        for _ in range(300):
            a2p = req("GET", f"http://127.0.0.1:8799/jobs/{a2['id']}")
            if a2p["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert a2p["status"] == "completed", a2p
        assert a2p.get("note") == "already in the archive — skipped", a2p
        assert (home / ".suravidl" / "archive.txt").exists(), \
            list((home / ".suravidl").iterdir())

        # M1 surface: version, error->retry flow, persistence
        ver = req("GET", "http://127.0.0.1:8799/version")
        assert ver["engine"] and ver["yt_dlp"], ver

        bad = req("POST", "http://127.0.0.1:8799/jobs",
                  {"url": "http://127.0.0.1:1/nope.mp4"})
        for _ in range(200):
            bj = req("GET", f"http://127.0.0.1:8799/jobs/{bad['id']}")
            if bj["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert bj["status"] == "error", bj

        retried = req("POST", f"http://127.0.0.1:8799/jobs/{bad['id']}/retry")
        assert retried["id"] != bad["id"] and retried["url"] == bad["url"]
        # retry of the dead URL errors again — that's the expected outcome here
        for _ in range(200):
            j2 = req("GET", f"http://127.0.0.1:8799/jobs/{retried['id']}")
            if j2["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert j2["status"] == "error", j2

        print(json.dumps({
            "SMOKE": "OK",
            "engine": h,
            "version": ver,
            "probe_ext": info["ext"],
            "probe_formats": len(info["formats"]),
            "job_status": j["status"],
            "file": j["filepath"],
            "bytes": Path(j["filepath"]).stat().st_size,
            "retry_of_error_job": j2["status"],
        }, indent=2))
    finally:
        eng.terminate()
        try:
            eng.wait(timeout=10)
        except subprocess.TimeoutExpired:
            eng.kill()
        fs.shutdown()


if __name__ == "__main__":
    main()
