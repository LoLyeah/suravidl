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
renditions — to a local decoded copy, and keep segments and #EXT-X-KEY
URIs absolute so yt-dlp fetches and AES-128-decrypts them exactly as on
any other site.

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


def _fetch(url: str, headers: dict | None = None, timeout: int = 40) -> str:
    """GET as a browser: the engine's TLS story, case-insensitive headers.

    urllib happily sends `User-Agent` *and* `user-agent` when both are in
    the dict, and the captured headers are lowercase — so the defaults are
    merged case-insensitively before the request is built.
    """
    merged: dict[str, str] = {}
    for k, v in {**HEADER_DEFAULTS, **(headers or {})}.items():
        merged[k.lower()] = str(v)
    req = urllib.request.Request(url, headers={k.title(): v for k, v in merged.items()})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        return r.read().decode("utf-8", "replace")


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
    """

    def __init__(self, workdir: Path):
        self.dir = Path(workdir)
        self.url = ""
        self._server: ThreadingHTTPServer | None = None

    def start(self, master: Path) -> None:
        handler = functools.partial(_QuietHandler, directory=str(self.dir))
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
    hls = DecodedHls(workdir)
    counter = {"n": 0}

    def _decode(text: str, where: str) -> str:
        got = xor_decode(text, key)
        if got is None:
            raise ValueError(
                "this stream's playlists are scrambled and the captured "
                "key does not decode them — sniff it again from the page "
                f"so a fresh key rides along ({where})")
        return got

    def _materialize(purl: str, depth: int) -> str:
        text = _decode(fetch(purl, headers), purl)
        is_master = "#EXT-X-STREAM-INF" in text
        out: list[str] = []
        for line in text.splitlines():
            if line.startswith(("#EXT-X-MEDIA:", "#EXT-X-KEY:", "#EXT-X-MAP:")):
                out.append(_URI_ATTRS.sub(
                    lambda m: f'URI="{urljoin(purl, m.group(1))}"', line))
                continue
            if line and not line.startswith("#"):
                ref = urljoin(purl, line.strip())
                if is_master and depth < 3:
                    out.append(_materialize(ref, depth + 1))
                else:
                    out.append(ref)        # segments stay remote, absolute
                continue
            out.append(line)
        counter["n"] += 1
        name = f"p{counter['n']}.m3u8"
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
