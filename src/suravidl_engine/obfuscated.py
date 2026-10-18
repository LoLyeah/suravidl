"""XOR-obfuscated HLS playlists — v0.47.0 "the veil".

Some players (the flixcloud embeds behind sites like reanime.to) never
serve an m3u8 in the clear: every playlist body is base64 of the plaintext
XORed with a repeating 32-byte key, and the key is exported by the
player's own WASM to `window.__pk`. A downloader that fetches such a
playlist straight gets a blob yt-dlp calls "Response data has no m3u
header" — the field report that started this round (2026-10-15).

The extension lifts the key from the page while sniffing (it already
stands in every frame) and rides it on the handoff; this module turns
URL + key into an ordinary HLS tree the engine's own download path can
eat: fetch, decode, rewrite every child reference — variants and audio
renditions — to a local decoded copy, and keep #EXT-X-KEY URIs absolute
so yt-dlp fetches and AES-128-decrypts them exactly as on any other site.

Segments are proxied through the same loopback face under ordinary .ts
names (v0.47.2 "the disguise"): this CDN names segments .png/.webp, and
ffmpeg's HLS demuxer refuses to open a segment whose extension is not in
its media list — the download died on "Invalid data found" with the
bytes sitting right there. The proxy passes the ciphertext through
untouched; only the name changes.

The decoded tree is served over a loopback HTTP server, not as local
files: yt-dlp must resolve the relative child references like any other
stream, and betting on its file:// handling is betting on an internal.
The server binds 127.0.0.1, serves one job's tree, and dies with it.

Honest failure is part of the design: a body the key cannot decode is
never guessed at — the error says to sniff again from the page.
"""
from __future__ import annotations

import base64
import binascii
import functools
import re
import shutil
import tempfile
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .classify import HEADER_DEFAULTS
from .net import ssl_context

# base64-shaped head: the alphabet plus whitespace, nothing else
_B64_HEAD = re.compile(r"^[A-Za-z0-9+/=\s_-]+$")
_URI_ATTRS = re.compile(r'URI="([^"]+)"')
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def decode_key(key: str | None) -> bytes | None:
    """The captured key as bytes: base64, 8..256 bytes. None when absent."""
    if not key:
        return None
    s = str(key).strip()
    try:
        raw = base64.b64decode(s + "=" * (-len(s) % 4), validate=False)
    except (binascii.Error, ValueError) as e:
        raise ValueError("the captured decode key is not base64") from e
    if not 8 <= len(raw) <= 256:
        raise ValueError("the captured decode key has a strange length")
    return raw


def looks_obfuscated(body: str) -> bool:
    """Not an m3u8, and shaped like base64 rather than HTML or JSON.

    Deliberately narrow: a Cloudflare wall or an error page keeps its own,
    more honest error — only a base64-shaped body that is not a playlist
    is "scrambled", and only when a key was actually captured.
    """
    head = (body or "").lstrip()[:4096]
    if not head or "#EXTM3U" in head[:256]:
        return False
    return bool(_B64_HEAD.match(head[:512]))


def xor_decode(body: str, key: bytes) -> str | None:
    """base64-decode, XOR with the repeating key, expect #EXTM3U."""
    s = re.sub(r"\s+", "", body or "")
    if not s:
        return None
    try:
        raw = base64.b64decode(s + "=" * (-len(s) % 4), validate=False)
    except (binascii.Error, ValueError):
        return None
    if not raw:
        return None
    out = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    try:
        text = out.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text.lstrip().startswith("#EXTM3U") else None


def _request(url: str, headers: dict | None = None) -> urllib.request.Request:
    """A Request built the way the browser sends it: the engine's TLS story,
    case-insensitive headers. urllib happily sends `User-Agent` *and*
    `user-agent` when both are in the dict, and the captured headers are
    lowercase — so the defaults are merged case-insensitively first."""
    merged: dict[str, str] = {}
    for k, v in {**HEADER_DEFAULTS, **(headers or {})}.items():
        merged[k.lower()] = str(v)
    return urllib.request.Request(url, headers={k.title(): v for k, v in merged.items()})


def _fetch(url: str, headers: dict | None = None, timeout: int = 40) -> str:
    with urllib.request.urlopen(_request(url, headers), timeout=timeout,
                                context=ssl_context()) as r:
        return r.read().decode("utf-8", "replace")


def _fetch_bytes(url: str, headers: dict | None = None, timeout: int = 60) -> tuple[int, bytes]:
    """The proxy's fetch: raw bytes for a segment, headers and all."""
    with urllib.request.urlopen(_request(url, headers), timeout=timeout,
                                context=ssl_context()) as r:
        return r.status, r.read()


def _peek(url: str, headers: dict | None = None, n: int = 32) -> bytes:
    """The first n bytes of a resource — a Range read, cheap on a CDN."""
    req = _request(url, headers)
    req.add_header("Range", f"bytes=0-{n - 1}")
    with urllib.request.urlopen(req, timeout=20, context=ssl_context()) as r:
        return r.read(n)


def looks_wrapped(head: bytes) -> bool:
    """A segment wearing an image container (v0.47.5 "the carrier").

    One CDN wave serves every segment as RIFF/WEBP (or PNG/JPEG) with an
    opaque payload inside — the site's own player unwraps it in wasm and
    nothing else can. The magic is unmistakable in the first 32 bytes.
    """
    return (head[:4] == b"RIFF" and head[8:12] == b"WEBP"
            or head[:8] == b"\x89PNG\r\n\x1a\n"
            or head[:3] == b"\xff\xd8\xff")


class _QuietHandler(SimpleHTTPRequestHandler):
    """The tree is for yt-dlp, not the log."""

    def log_message(self, format, *args):  # noqa: A002 - the stdlib spelling
        pass

    def guess_type(self, path):  # noqa: N802 - the stdlib spelling
        if str(path).endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        return super().guess_type(path)


class DecodedHls:
    """A decoded tree's local face: loopback server + the temp dir it serves.

    Use as a context manager (or call stop()): both the server and the
    files die together, and neither outlives the probe/job that made it.

    `routes` is the segment proxy: disguised segment URLs (v0.47.2 "the
    disguise" — this CDN names segments .png/.webp, and ffmpeg's HLS
    demuxer refuses extensions outside its media list) are re-served from
    here as ordinary .ts paths, fetched with the job's own headers. The
    bytes stay AES-128 ciphertext: the key URI stays remote, so the
    downloader decrypts exactly as on any other site.
    """

    def __init__(self, workdir: Path, headers: dict | None = None):
        self.dir = Path(workdir)
        self.headers = dict(headers or {})
        self.routes: dict[str, str] = {}
        self.url = ""
        self._server: ThreadingHTTPServer | None = None

    def add_route(self, local: str, remote: str) -> None:
        self.routes["/" + local.lstrip("/")] = remote

    def start(self, master: Path) -> None:
        routes, headers = self.routes, self.headers

        class _Handler(_QuietHandler):
            def _maybe_proxy(self, head: bool) -> bool:
                path = self.path.split("?", 1)[0]
                remote = routes.get(path)
                if remote is None:
                    return False
                try:
                    status, data = _fetch_bytes(remote, headers)
                except Exception:  # noqa: BLE001 - a segment fetch must not kill the server
                    self.send_error(502)
                    return True
                self.send_response(200 if status == 200 else status)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if not head:
                    self.wfile.write(data)
                return True

            def do_GET(self):  # noqa: N802 - the stdlib spelling
                if not self._maybe_proxy(head=False):
                    super().do_GET()

            def do_HEAD(self):  # noqa: N802 - the stdlib spelling
                if not self._maybe_proxy(head=True):
                    super().do_HEAD()

        handler = functools.partial(_Handler, directory=str(self.dir))
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/{master.name}"

    def stop(self) -> None:
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:  # noqa: BLE001 - teardown must never raise
                pass
            self._server = None
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self) -> "DecodedHls":
        return self

    def __exit__(self, *_exc) -> bool:
        self.stop()
        return False


def maybe_materialize(url: str, *, headers: dict | None = None,
                      xor_key: str | None = None,
                      fetch=_fetch) -> DecodedHls | None:
    """A running DecodedHls for an obfuscated playlist URL, or None.

    None means "nothing to lift — use the URL as-is": no key captured, or
    the body is already a plain m3u8, or it is not base64-shaped at all
    (an error page keeps its own error). Raises ValueError when the body
    IS obfuscated but the key cannot decode it: guessing is never an
    option, and the message tells the user to sniff again.
    """
    key = decode_key(xor_key)
    if key is None:
        return None
    body = fetch(url, headers)
    if "#EXTM3U" in body[:64] or not looks_obfuscated(body):
        return None

    workdir = Path(tempfile.mkdtemp(prefix="sv-hls-"))
    hls = DecodedHls(workdir, headers=headers)
    counter = {"n": 0}
    seg = {"n": 0}

    def _decode(text: str, where: str) -> str:
        got = xor_decode(text, key)
        if got is None:
            raise ValueError(
                "this stream's playlists are scrambled and the captured "
                "key does not decode them — sniff it again from the page "
                f"so a fresh key rides along ({where})")
        return got

    def _proxy(ref: str, ext: str = "ts") -> str:
        """A disguised segment, re-served from our loopback face under a
        name ffmpeg's HLS demuxer accepts (v0.47.2 "the disguise")."""
        seg["n"] += 1
        local = f"s{seg['n']}.{ext}"
        hls.add_route(local, ref)
        return local

    def _materialize(purl: str, depth: int) -> str:
        text = _decode(fetch(purl, headers), purl)
        is_master = "#EXT-X-STREAM-INF" in text
        out: list[str] = []
        segs: list[str] = []
        for line in text.splitlines():
            if line.startswith("#EXT-X-MEDIA:"):
                # audio renditions live in the master and are scrambled too:
                # materialize them like variants, or the downloader fetches
                # the raw blob and the mux comes out broken (v0.47.2)
                if is_master and depth < 3:
                    out.append(_URI_ATTRS.sub(
                        lambda m: f'URI="{_materialize(urljoin(purl, m.group(1)), depth + 1)}"',
                        line))
                else:
                    out.append(_URI_ATTRS.sub(
                        lambda m: f'URI="{urljoin(purl, m.group(1))}"', line))
                continue
            if line.startswith("#EXT-X-KEY:"):
                # the key stays remote: the downloader decrypts, we do not
                out.append(_URI_ATTRS.sub(
                    lambda m: f'URI="{urljoin(purl, m.group(1))}"', line))
                continue
            if line.startswith("#EXT-X-MAP:"):
                out.append(_URI_ATTRS.sub(
                    lambda m: f'URI="{_proxy(urljoin(purl, m.group(1)), "mp4")}"', line))
                continue
            if line and not line.startswith("#"):
                ref = urljoin(purl, line.strip())
                if is_master and depth < 3:
                    out.append(_materialize(ref, depth + 1))
                else:
                    segs.append(ref)
                    out.append(_proxy(ref))
                continue
            out.append(line)
        counter["n"] += 1
        name = f"p{counter['n']}.m3u8"
        if not is_master and segs:
            # v0.47.5 "the carrier": one CDN wave wraps every segment in a
            # fake image the player alone can unwrap. ffmpeg would merge the
            # carriers and call the result broken — refuse before the
            # download starts, with the way out.
            try:
                head = _peek(segs[0], headers)
            except Exception:  # noqa: BLE001 - a failed peek is not a verdict
                head = b""
            if looks_wrapped(head):
                raise ValueError(
                    "this server wraps its video segments in fake images "
                    "(a carrier only the site's own player can unwrap) — "
                    "the engine cannot read it. Pick another server on the "
                    "page (e.g. HD-1 instead of HD-2) and sniff again.")
        (workdir / name).write_text("\n".join(out) + "\n", encoding="utf-8")
        return name

    try:
        base = _SAFE_NAME.sub("_", Path(urlparse(url).path).name) or "master.m3u8"
        if not base.endswith(".m3u8"):
            base = "master.m3u8"
        final = f"master-{base}" if base.startswith("p") else base
        # materialize into the workdir root, then move the top playlist to
        # its public name (children keep pN.m3u8)
        name = _materialize(url, 0)
        (workdir / name).rename(workdir / final)
        hls.start(workdir / final)
        return hls
    except Exception:
        hls.stop()
        raise
