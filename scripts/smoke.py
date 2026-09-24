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
    env = dict(os.environ, SURAVIDL_TOKEN=TOKEN)
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
