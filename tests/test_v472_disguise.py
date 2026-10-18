"""v0.47.2 "the disguise" — segments wearing image names, and audio tracks.

The flixcloud CDNs name every media segment .png/.webp (a disguise: the
bytes are ordinary AES-128 HLS underneath) and split video and audio into
separate renditions announced by #EXT-X-MEDIA. v0.47.0 decoded the
playlists but handed the disguised segment URLs straight to the
downloader — ffmpeg refuses extensions outside its media list ("not in
allowed_segment_extensions") — and left the audio renditions scrambled
remote blobs. The episode then failed, or arrived as a file no player
would open.

This rig is the real scheme offline: video + audio HLS made by ffmpeg,
segments written as seg%d.png, every playlist XOR-scrambled, a hotlink
gate on every request. The job must finish with one file carrying both
tracks: the proxy re-serves the ciphertext under ordinary .ts names with
the job's headers, the AES key stays remote, and ffprobe finds video + audio.
"""
import base64
import functools
import http.server
import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from suravidl_engine import cut
from suravidl_engine.download_opts import build_download_opts
from suravidl_engine.jobs import JobManager
from suravidl_engine.obfuscated import maybe_materialize
from suravidl_engine.settings import DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
REF = "https://flixcloud.cc/"
XOR = b"0123456789abcdef0123456789abcdef"          # 32-byte repeating key
KEY_B64 = base64.b64encode(XOR).decode()
AES_KEY = bytes(range(16))

pytestmark = pytest.mark.skipif(not cut.ffmpeg_exe(),
                                reason="no ffmpeg on this box")

MASTER = (
    "#EXTM3U\n#EXT-X-VERSION:3\n"
    '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",LANGUAGE="jpn",NAME="Native",'
    'DEFAULT=YES,AUTOSELECT=YES,URI="audio/index.m3u8"\n'
    '#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=320x240,AUDIO="audio",'
    'CODECS="avc1.42e01e,mp4a.40.2"\n'
    "video/index.m3u8\n"
)


def _scramble(text: str) -> str:
    raw = text.encode()
    out = bytes(b ^ XOR[i % len(XOR)] for i, b in enumerate(raw))
    return base64.b64encode(out).decode()


def _rendition(root: Path, name: str, *args: str) -> None:
    """ffmpeg makes a real AES-128 HLS rendition whose segments wear .png."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "key.bin").write_bytes(AES_KEY)
    info = d / "keyinfo.txt"
    info.write_text(f"key.bin\n{d / 'key.bin'}\n")
    subprocess.run(
        [cut.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args,
         "-f", "hls", "-hls_time", "2", "-hls_playlist_type", "vod",
         "-hls_key_info_file", str(info),
         "-hls_segment_filename", str(d / "seg%d.png"),
         str(d / "index.m3u8")], check=True)


def _build_tree(root: Path) -> None:
    _rendition(root, "video",
               "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=10", "-t", "4",
               "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p")
    _rendition(root, "audio",
               "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
               "-t", "4", "-c:a", "aac", "-b:a", "64k", "-vn")
    # the playlists then wear the veil, like the field
    for rel in ("master.m3u8", "video/index.m3u8", "audio/index.m3u8"):
        text = MASTER if rel == "master.m3u8" else (root / rel).read_text()
        (root / rel).write_text(_scramble(text))


class _Gate(http.server.SimpleHTTPRequestHandler):
    """The CDN's hotlink gate: a request without the referer gets no bytes."""

    def log_message(self, format, *args):  # noqa: A002 - silence
        pass

    def do_GET(self):  # noqa: N802 - the stdlib spelling
        if self.headers.get("Referer", "") != REF:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"no")
            return
        super().do_GET()


@pytest.fixture()
def disguise_rig(tmp_path):
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
        s = {**DEFAULTS, "download_dir": str(dir_)}
        return build_download_opts(s, dir_, raw_args=raw_args)
    return JobManager(download_dir=dd, db_path=dd / "jobs.db",
                      max_concurrent=1, download_opts=dopts)


# --- the field report, end to end -------------------------------------------

def test_the_disguised_tree_lands_with_both_tracks(tmp_path, disguise_rig):
    """The whole bug: disguised segments + a separate scrambled audio
    rendition — the job must land one file with video AND audio."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd)
    job = mgr.create(f"{disguise_rig}/master.m3u8",
                     extra_headers={"referer": REF}, xor_key=KEY_B64)
    done = _wait(mgr, job["id"])
    assert done["status"] == "completed", done.get("error")
    out = Path(done["filepath"])
    assert out.is_file() and out.stat().st_size > 0
    probe = subprocess.run(
        [str(Path(cut.ffmpeg_exe()).with_name("ffprobe")), "-v", "error",
         "-show_entries", "stream=codec_type", "-of", "json", str(out)],
        capture_output=True, text=True)
    kinds = sorted(s["codec_type"] for s in json.loads(probe.stdout)["streams"])
    assert "video" in kinds and "audio" in kinds, probe.stdout


def test_the_served_tree_has_no_disguised_names(disguise_rig):
    """The proxy is the fix: no served playlist may reference a .png/.webp
    segment, and the audio rendition must be a local decoded playlist."""
    hls = maybe_materialize(f"{disguise_rig}/master.m3u8",
                            headers={"referer": REF}, xor_key=KEY_B64)
    assert hls is not None
    try:
        served = {p.name: p.read_text() for p in hls.dir.iterdir()
                  if p.suffix == ".m3u8"}
        assert served, "nothing materialized"
        for name, text in served.items():
            assert ".png" not in text and ".webp" not in text, name
            for line in text.splitlines():
                if line.startswith("#EXT-X-MEDIA:"):
                    assert 'URI="p' in line, line   # local decoded audio
                if line.startswith("#EXT-X-KEY:"):
                    # the key stays remote (the rendition's own key.bin) —
                    # never a proxied sN name
                    uri = line.split('URI="', 1)[1].split('"', 1)[0]
                    assert uri.rsplit("/", 1)[-1] == "key.bin", line
        # a proxied segment hands the ciphertext through, headers and all
        video = [t for t in served.values() if "#EXT-X-KEY" in t and "EXTINF" in t]
        assert video, "no variant served"
        seg = [ln for ln in video[0].splitlines() if ln.endswith(".ts")][0]
        base = hls.url.rsplit("/", 1)[0]
        req = urllib.request.Request(base + "/" + seg,
                                     headers={"Referer": REF})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        assert body and body[:1] != b"#"
    finally:
        hls.stop()


# --- release + shell pins ----------------------------------------------------

def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__, whatsnew

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # v0.47.3 "the legend" — this round's entry stays among the living
    # ten (the strict current-version pin moved to that release's test
    # file, per the retirement policy)
    assert any(e["version"] == "0.47.2"
               and e["title"].lower() == "the masquerade"
               for e in whatsnew.ENTRIES)


def test_the_popup_names_the_tree():
    """The extension's list: roles, the fold, and the version."""
    popup = (ROOT / "extension/popup.js").read_text()
    assert "function roleOf(" in popup
    assert "function groupRows(" in popup
    assert "All qualities" in popup
    assert "Show the {n} separate streams" in popup
    assert 'if (role.role === "audio")' in popup
    man = json.loads((ROOT / "extension/manifest.json").read_text())["version"]
    assert "v" + man in (ROOT / "extension/popup.html").read_text()
    for rel in ("extension/manifest.json", "extension/firefox/manifest.json"):
        assert json.loads((ROOT / rel).read_text())["version"] == man
