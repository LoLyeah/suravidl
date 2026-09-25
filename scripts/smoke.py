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
import urllib.error
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

        # -- curated groups (yt-dlp tab): validation + round-trip -------------
        c = req("POST", "http://127.0.0.1:8799/settings",
                {"ip_version": "ipv4", "sleep_requests": 1.5,
                 "geo_bypass": True, "geo_bypass_country": "id",
                 "extractor_args": "youtube:player_client=web_safari",
                 "verbose": False})
        assert c["ip_version"] == "ipv4" and c["sleep_requests"] == 1.5, c
        assert c["geo_bypass_country"] == "ID", c
        assert c["extractor_args"] == "youtube:player_client=web_safari", c
        try:
            req("POST", "http://127.0.0.1:8799/settings", {"ip_version": "ipv5"})
            raise AssertionError("ip_version accepted ipv5")
        except urllib.error.HTTPError as e:
            assert e.code == 400, e.code               # refused, as it must be
        # and a download still works with the curated groups set
        cj = req("POST", "http://127.0.0.1:8799/jobs", {"url": f"{base}/tiny2.mp4"})
        for _ in range(300):
            cjp = req("GET", f"http://127.0.0.1:8799/jobs/{cj['id']}")
            if cjp["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert cjp["status"] == "completed", cjp
        req("POST", "http://127.0.0.1:8799/settings",
            {"ip_version": "auto", "sleep_requests": 0, "geo_bypass": False,
             "geo_bypass_country": "", "extractor_args": ""})

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

        # -- raw yt-dlp arguments + option catalogue (Advanced tier) ---------
        s2 = req("POST", "http://127.0.0.1:8799/settings",
                 {"raw_args_enabled": True, "raw_args": "--write-info-json"})
        assert s2["raw_args_enabled"] is True, s2
        rj = req("POST", "http://127.0.0.1:8799/jobs",
                 {"url": f"{base}/tiny2.mp4"})
        for _ in range(300):
            rjp = req("GET", f"http://127.0.0.1:8799/jobs/{rj['id']}")
            if rjp["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert rjp["status"] == "completed", rjp
        assert rjp["raw_args"] == "--write-info-json", rjp
        assert any(p.name.endswith(".info.json") for p in dl_dir.iterdir()), \
            list(dl_dir.iterdir())

        # a flag the engine owns is refused, with the reason
        try:
            req("POST", "http://127.0.0.1:8799/settings",
                {"raw_args_enabled": True, "raw_args": "--exec echo boom"})
            raise AssertionError("--exec should have been refused")
        except urllib.error.HTTPError as e:
            assert e.code == 400 and "--exec" in e.read().decode(), e.code

        cat = req("GET", "http://127.0.0.1:8799/options")
        assert cat["count"] > 300, cat["count"]

        # no desktop shell here -> opening links is 501, never a crash
        try:
            req("POST", "http://127.0.0.1:8799/app/open-url",
                {"url": "https://example.com"})
            raise AssertionError("open-url should be 501 without a shell")
        except urllib.error.HTTPError as e:
            assert e.code == 501, e.code

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

        # --- per-download delete (the trash button) ---
        # a finished job with a real file goes away, file included
        wrote = Path(j["filepath"])
        written_bytes = wrote.stat().st_size
        wrote.with_suffix(".info.json").write_text("{}")   # a sidecar
        gone = req("POST", f"http://127.0.0.1:8799/jobs/{j['id']}/delete")
        assert gone["deleted"] >= 2 and gone["freed_bytes"] > 0, gone
        assert not wrote.exists() and not wrote.with_suffix(".info.json").exists()
        try:
            req("GET", f"http://127.0.0.1:8799/jobs/{j['id']}")
            raise AssertionError("the row should be gone")
        except urllib.error.HTTPError as e:
            assert e.code == 404, e.code
        # an unknown job is a 404, not a 500
        try:
            req("POST", "http://127.0.0.1:8799/jobs/nope/delete")
            raise AssertionError("unknown id should 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404, e.code

        # --- per-download overrides + named presets ---
        # a preset stores a validated patch; applying it is an override
        saved = req("POST", "http://127.0.0.1:8799/presets", {
            "name": "smoke bundle",
            "patch": {"subtitles_mode": "sidecar", "embed_metadata": True},
        })
        assert saved["builtin"] is False, saved
        listing = req("GET", "http://127.0.0.1:8799/presets")
        names = {p["name"] for p in listing["presets"]}
        assert {"audio-native", "audio-m4a", "audio-mp3", "smoke bundle"} <= names
        assert "filename_template" in listing["per_job_keys"]
        # a bad patch and a bad name are refused, not stored
        for bad in ({"name": "x", "patch": {"download_dir": "/tmp"}},
                    {"name": "x", "patch": {"nope": 1}},
                    {"name": "bad/name", "patch": {"archive": True}}):
            try:
                req("POST", "http://127.0.0.1:8799/presets", bad)
                raise AssertionError(f"should have been refused: {bad}")
            except urllib.error.HTTPError as e:
                assert e.code == 400, e.code
        # a per-download override really reaches yt-dlp (the file name proves it)
        # and can turn an app-wide setting off for one job (the archive, which
        # the earlier steps left enabled and which would otherwise skip this URL)
        ov = req("POST", "http://127.0.0.1:8799/jobs", {
            "url": f"{base}/tiny2.mp4",
            "overrides": {"filename_template": "smoke-ov.%(ext)s",
                          "archive": False},
        })
        assert ov["overrides"] == {"filename_template": "smoke-ov.%(ext)s",
                                   "archive": False}, ov
        for _ in range(200):
            cur = req("GET", f"http://127.0.0.1:8799/jobs/{ov['id']}")
            if cur["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert cur["status"] == "completed", cur
        assert cur["filepath"].endswith("smoke-ov.mp4"), cur["filepath"]
        assert req("GET", "http://127.0.0.1:8799/settings")["filename_template"] != \
            "smoke-ov.%(ext)s", "global settings must not change"
        # and the archive setting the other jobs rely on is still on
        assert req("GET", "http://127.0.0.1:8799/settings")["archive"] is True
        assert req("DELETE", "http://127.0.0.1:8799/presets/smoke%20bundle")["ok"]

        # --- test cookies: static report, and a real extraction as proof ---
        none = req("POST", "http://127.0.0.1:8799/auth/check", {})
        assert none["ok"] is False and none["source"] == "none", none
        assert "Settings" in none["message"], none
        ck = home / "cookies.txt"
        ck.write_text("# Netscape HTTP Cookie File\n"
                      f"127.0.0.1\tFALSE\t/\tFALSE\t2000000000\tsuravidl_smoke\thi\n")
        req("POST", "http://127.0.0.1:8799/settings", {"cookies_file": str(ck)})
        static = req("POST", "http://127.0.0.1:8799/auth/check", {})
        assert static["ok"] is True and static["cookies"]["count"] == 1, static
        assert "hi" not in json.dumps(static), "a cookie value leaked"
        live = req("POST", "http://127.0.0.1:8799/auth/check",
                   {"url": f"{base}/tiny.mp4"})
        assert live["ok"] is True and "worked" in live["message"], live
        tested = {"cookies_static": static["message"], "cookies_live": live["message"]}

        # --- tier-1 knobs: they reach yt-dlp, and stay per-job overridable ---
        req("POST", "http://127.0.0.1:8799/settings", {"retries": 3,
                                                       "max_downloads": 2})
        st = req("GET", "http://127.0.0.1:8799/settings")
        assert st["retries"] == 3 and st["max_downloads"] == 2, st
        knobs = req("POST", "http://127.0.0.1:8799/jobs", {
            "url": f"{base}/tiny2.mp4",
            "overrides": {"retries": 0, "max_downloads": 1}})
        assert knobs["overrides"] == {"retries": 0, "max_downloads": 1}, knobs

        # --- quality picks are engine-owned and yt-dlp accepts every one ---
        q = req("GET", "http://127.0.0.1:8799/presets")["qualities"]
        assert [x["key"] for x in q][:2] == ["best", "2160"], q
        spec = next(x for x in q if x["key"] == "480")["fmt"]
        cap = req("POST", "http://127.0.0.1:8799/jobs", {
            "url": f"{base}/tone.m4a", "fmt": spec,
            # earlier steps left the archive on and tone.m4a in it: one job can
            # turn that off for itself — which is also the thing being tested
            "overrides": {"archive": False}})
        assert cap["fmt"] == spec, cap
        for _ in range(200):
            c = req("GET", f"http://127.0.0.1:8799/jobs/{cap['id']}")
            if c["status"] in ("completed", "error"):
                break
            time.sleep(0.1)
        assert c["status"] == "completed", c
        # a capped spec must still fall back to the single file for audio-only
        assert Path(c["filepath"]).suffix == ".m4a" and Path(c["filepath"]).is_file(), c
        caps = {"quality_spec": spec, "quality_file": Path(c["filepath"]).name}

        print(json.dumps({
            "SMOKE": "OK",
            "engine": h,
            "version": ver,
            "probe_ext": info["ext"],
            "probe_formats": len(info["formats"]),
            "job_status": j["status"],
            "file": j["filepath"],
            "bytes": written_bytes,
            "deleted": gone,
            "retry_of_error_job": j2["status"],
            "cookies": tested,
            "quality": caps,
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
