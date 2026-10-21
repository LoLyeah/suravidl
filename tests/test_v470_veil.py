"""v0.47.0 "the veil" — scrambled playlists come down like any other stream.

Field report (2026-10-15): a site whose player obfuscates every playlist
(the flixcloud embeds behind reanime.to) — yt-dlp on the captured m3u8 URL
dies with "Response data has no m3u header", because the body is base64 of
the plaintext XORed with a 32-byte key the page exports to `window.__pk`.
The sniffer lifts that key from the page and rides it on the handoff; the
engine decodes the tree behind a loopback server and feeds its own
download path — segments stay remote and standard (AES-128 here, exactly
like the real sites), so yt-dlp decrypts and muxes as always.

The rig below is the whole scheme, offline: an XOR-scrambled master and
variant, AES-128 segments (ffmpeg's own encrypted HLS output), a hotlink
gate that refuses without the flixcloud referer — and the engine must
land the file with the key, fail honestly without it, and never guess
with a wrong one.
"""
import base64
import functools
import http.server
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from suravidl_engine import cut, download_opts, whatsnew  # noqa: E402
from suravidl_engine import obfuscated
from suravidl_engine.jobs import JobManager

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REF = "https://flixcloud.cc/"
KEY = bytes(range(32))            # the rig's "window.__pk" (32 bytes)
KEY_B64 = base64.b64encode(KEY).decode()

pytestmark = pytest.mark.skipif(not cut.ffmpeg_exe(),
                                reason="no ffmpeg on this box")


# --- the unit layer ----------------------------------------------------------


def test_decode_key_validates_before_anything_runs():
    assert obfuscated.decode_key(None) is None
    assert obfuscated.decode_key("") is None
    assert len(obfuscated.decode_key(KEY_B64)) == 32
    with pytest.raises(ValueError):
        obfuscated.decode_key("not base64 !!!")
    with pytest.raises(ValueError):
        obfuscated.decode_key(base64.b64encode(b"tiny").decode())


def test_xor_roundtrip_and_the_narrow_obfuscated_guess():
    plain = "#EXTM3U\n#EXT-X-VERSION:3\n"
    raw = plain.encode()
    blob = bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(raw))
    enc = base64.b64encode(blob).decode()
    assert obfuscated.xor_decode(enc, KEY) == plain
    assert obfuscated.xor_decode(enc, bytes(32)) is None
    assert obfuscated.looks_obfuscated(enc)
    assert not obfuscated.looks_obfuscated("<html>nope</html>")
    assert not obfuscated.looks_obfuscated('{"error": "nope"}')
    assert not obfuscated.looks_obfuscated(plain)


# --- the rig: the whole scheme on loopback ----------------------------------


def _scramble(text: str) -> str:
    raw = text.encode()
    return base64.b64encode(
        bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(raw))).decode()


def _build_tree(root: Path) -> None:
    """ffmpeg makes real AES-128 HLS; the playlists then wear the veil."""
    (root / "key.bin").write_bytes(bytes(range(16)))   # ffmpeg wants it to exist
    keyinfo = root / "keyinfo"
    keyinfo.write_text("key.bin\n" + str(root / "key.bin") + "\n")
    r = subprocess.run(
        [cut.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(FIXTURES / "tiny.mp4"), "-c", "copy",
         "-hls_time", "1", "-hls_playlist_type", "vod",
         "-hls_key_info_file", str(keyinfo),
         "-hls_segment_filename", str(root / "seg%d.ts"),
         str(root / "plain.m3u8")], capture_output=True, text=True)
    if r.returncode != 0 or not (root / "plain.m3u8").exists():
        # a fixture codec TS cannot carry with -c copy: transcode instead
        subprocess.run(
            [cut.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(FIXTURES / "tiny.mp4"), "-c:v", "libx264",
             "-c:a", "aac", "-hls_time", "1", "-hls_playlist_type", "vod",
             "-hls_key_info_file", str(keyinfo),
             "-hls_segment_filename", str(root / "seg%d.ts"),
             str(root / "plain.m3u8")], check=True)
    variant = (root / "plain.m3u8").read_text()
    (root / "v.m3u8").write_text(_scramble(variant))
    (root / "master.m3u8").write_text(_scramble(
        "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100000,"
        "RESOLUTION=320x180\nv.m3u8\n"))


class _Gate(http.server.SimpleHTTPRequestHandler):
    """The CDN's hotlink gate: no flixcloud referer, no bytes."""

    def log_message(self, format, *args):  # noqa: A002 - silence
        pass

    def do_GET(self):  # noqa: N802 - the stdlib spelling
        ref = self.headers.get("Referer", "")
        if ref != REF:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"no")
            return
        super().do_GET()


@pytest.fixture()
def veil_rig(tmp_path):
    root = tmp_path / "cdn"
    root.mkdir()
    _build_tree(root)
    handler = functools.partial(_Gate, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _wait(mgr, jid, timeout=150.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = mgr.get(jid)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.25)
    raise TimeoutError(f"job stayed {mgr.get(jid)['status']}")


def _manager(dd):
    def dopts(dir_, raw_args=None, overrides=None):
        from suravidl_engine.settings import DEFAULTS

        s = {**DEFAULTS, "download_dir": str(dir_)}
        return download_opts.build_download_opts(s, dir_, raw_args=raw_args)
    return JobManager(download_dir=dd, db_path=dd / "jobs.db",
                      max_concurrent=1, download_opts=dopts)


# --- the field report, end to end -------------------------------------------


def test_the_scrambled_tree_downloads_like_any_stream(tmp_path, veil_rig):
    """The whole report: master + variant behind the veil, AES-128
    segments, a hotlink gate — and the file lands."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd)
    job = mgr.create(f"{veil_rig}/master.m3u8",
                     extra_headers={"referer": REF}, xor_key=KEY_B64)
    done = _wait(mgr, job["id"])
    assert done["status"] == "completed", done.get("error")
    out = Path(done["filepath"])
    assert out.is_file() and out.stat().st_size > 0
    assert out.suffix in (".mp4", ".ts"), out.name


def test_without_the_key_the_error_says_how_to_get_it(tmp_path, veil_rig):
    """A paste carries no key: the failure must point at the sniffer, not
    at yt-dlp's "no m3u header"."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd)
    job = mgr.create(f"{veil_rig}/master.m3u8",
                     extra_headers={"referer": REF})
    done = _wait(mgr, job["id"])
    assert done["status"] == "error"
    assert "scrambles its playlists" in (done.get("error") or "")


def test_a_wrong_key_is_an_honest_failure(tmp_path, veil_rig):
    """Never guess: a key that does not decode this stream fails loudly
    and tells the user to sniff again."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd)
    wrong = base64.b64encode(b"x" * 32).decode()
    job = mgr.create(f"{veil_rig}/master.m3u8",
                     extra_headers={"referer": REF}, xor_key=wrong)
    done = _wait(mgr, job["id"])
    assert done["status"] == "error"
    assert "sniff it again" in (done.get("error") or "")


def test_the_plain_path_is_untouched_by_a_stray_key(tmp_path, veil_rig):
    """A key from another tab must never break a stream that was never
    scrambled: the body is already #EXTM3U, so the key is ignored."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd)
    # a fully plain tree the rig also serves (the ffmpeg playlist itself)
    plain = tmp_path / "cdn" / "open.m3u8"
    plain.write_text("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100000,"
                     "RESOLUTION=320x180\nplain.m3u8\n")
    job = mgr.create(f"{veil_rig}/open.m3u8",
                     extra_headers={"referer": REF}, xor_key=KEY_B64)
    done = _wait(mgr, job["id"])
    assert done["status"] == "completed", done.get("error")


def test_the_probe_reads_the_decoded_tree(tmp_path, veil_rig):
    """The extension's quality door: /probe with the key returns formats,
    and the hotlink gate proves the captured referer rode along."""
    from suravidl_engine.api import create_app
    from fastapi.testclient import TestClient

    app = create_app(download_dir=str(tmp_path), auth_token="t",
                     db_path=":memory:")
    c = TestClient(app)
    h = {"Authorization": "Bearer t"}
    r = c.post("/probe", headers=h, json={
        "url": f"{veil_rig}/master.m3u8",
        "headers": {"referer": REF},
        "xor_key": KEY_B64,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("formats"), "the decoded tree must show its formats"
    # without the referer the gate refuses — the probe says so, honestly
    r2 = c.post("/probe", headers=h, json={
        "url": f"{veil_rig}/master.m3u8",
        "headers": {},
        "xor_key": KEY_B64,
    })
    assert r2.status_code == 400
    assert "403" in r2.json()["detail"]


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # 0.47.0 "the veil" retired out of the rolling ten in v0.47.10
    assert "The veil" not in [e["title"] for e in whatsnew.ENTRIES]


def test_create_keeps_its_positional_contract():
    """The Android harness calls create() positionally (url, fmt,
    extra_headers, preset) — a new parameter must go LAST or a headers
    dict lands on it. The v0.47.0 mid-signature insertion did exactly
    that and the 16k emulator board caught it before any tag existed."""
    import inspect

    from suravidl_engine.jobs import JobManager

    params = list(inspect.signature(JobManager.create).parameters)
    assert params[:5] == ["self", "url", "fmt", "extra_headers", "preset"]
    assert params[-1] == "xor_key", "new parameters go last"


# --- the extension side: the key's travel ------------------------------------


def test_the_extension_carries_the_key_from_the_page():
    """Source pins: Chrome reads window.__pk in a MAIN-world reader and the
    content script forwards it; Firefox reads page globals directly
    (wrappedJSObject — its MV2 scripts can, so it ships no reader); the
    background stores it per tab and rides it on every door."""
    ext = Path(__file__).resolve().parents[1] / "extension"
    pk = (ext / "pk.js").read_text()
    assert "window.__pk" in pk and "postMessage" in pk
    pagefind = (ext / "pagefind.js").read_text()
    assert "__svPk" in pagefind and "pkFind" in pagefind
    assert "wrappedJSObject" in pagefind, "Firefox's door"
    bg = (ext / "background.js").read_text()
    assert 'msg.type === "pkFind"' in bg
    assert "tabPk" in bg
    assert bg.count("xor_key:") >= 4, "every door carries the key"
    m = json.loads((ext / "manifest.json").read_text())
    scripts = [s for s in m["content_scripts"] if "pk.js" in s.get("js", [])]
    assert scripts and scripts[0].get("world") == "MAIN"
    ff = json.loads((ext / "firefox" / "manifest.json").read_text())
    assert all("pk.js" not in s.get("js", []) for s in ff["content_scripts"]), \
        "Firefox has no MAIN-world scripts in MV2 — wrappedJSObject is its door"
