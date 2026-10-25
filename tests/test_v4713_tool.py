"""v0.47.13 "the tool" — ffmpeg fetched on demand, from Settings.

Desktop builds never bundled ffmpeg (only Android does), so "best video +
best audio" could never finish on a clean Mac or Windows box — the owner's
reel died exactly there. The installers stay small: Settings downloads a
static build into ~/.suravidl/tools, pinned by two sha256 checks (the
archive and the binary), and the resolver prefers it over PATH.
"""
import gzip
import hashlib
import pathlib
import sys
import time

import pytest

from suravidl_engine import api, cut, jobs, tools

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text()
AUTH = {"Authorization": "Bearer testtoken"}


def test_every_desktop_platform_has_a_pinned_build():
    assert set(tools.TOOLS) == {("darwin", "arm64"), ("darwin", "x64"),
                                ("linux", "x64"), ("linux", "arm64"),
                                ("win32", "x64")}
    for stem, gz_sha, bin_sha in tools.TOOLS.values():
        assert len(gz_sha) == 64 and len(bin_sha) == 64
        assert stem.startswith("ffmpeg-")


def test_the_platform_key_reads_like_the_manifest(monkeypatch):
    monkeypatch.setattr(tools.sys, "platform", "darwin")
    monkeypatch.setattr(tools._platform, "machine", lambda: "arm64")
    assert tools.platform_key() == "darwin-arm64"
    monkeypatch.setattr(tools.sys, "platform", "linux")
    monkeypatch.setattr(tools._platform, "machine", lambda: "x86_64")
    assert tools.platform_key() == "linux-x64"
    monkeypatch.setattr(tools.sys, "platform", "win32")
    monkeypatch.setattr(tools._platform, "machine", lambda: "AMD64")
    assert tools.platform_key() == "win32-x64"


def test_the_resolver_prefers_the_downloaded_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    monkeypatch.delenv("SURAVIDL_FFMPEG", raising=False)
    monkeypatch.setattr(cut.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    own = tools.ffmpeg_path()
    own.write_bytes(b"#!/bin/sh\n")
    own.chmod(0o755)
    assert cut.ffmpeg_exe() == str(own), "the app's own copy wins over PATH"


def test_the_android_env_still_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    monkeypatch.setenv("SURAVIDL_FFMPEG", "/jniLibs/ffmpeg")
    assert cut.ffmpeg_exe() == "/jniLibs/ffmpeg"


def test_ytdlp_is_told_where_it_is(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    monkeypatch.delenv("SURAVIDL_FFMPEG", raising=False)
    monkeypatch.setattr(cut.shutil, "which", lambda name: None)
    monkeypatch.setattr(cut.sys, "platform", "linux")
    assert jobs.ffmpeg_opts() == {}
    own = tools.ffmpeg_path()
    own.write_bytes(b"x")
    own.chmod(0o755)
    assert jobs.ffmpeg_opts() == {"ffmpeg_location": str(own)}


class _FakeResp:
    def __init__(self, payload: bytes):
        self._b = payload
        self.headers = {"Content-Length": str(len(payload))}

    def read(self, n: int) -> bytes:
        out, self._b = self._b[:n], self._b[n:]
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_downloaded_build_is_verified_twice_and_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    binary = b"\x7fELF fake ffmpeg"
    gz = gzip.compress(binary)
    monkeypatch.setitem(
        tools.TOOLS, ("linux", "x64"),
        ("ffmpeg-linux-x64", hashlib.sha256(gz).hexdigest(),
         hashlib.sha256(binary).hexdigest()))
    monkeypatch.setattr(tools.sys, "platform", "linux")
    monkeypatch.setattr(tools._platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *a, **k: _FakeResp(gz))

    assert tools.status()["installed"] is False
    tools.start_download()
    deadline = time.time() + 10
    while time.time() < deadline and tools.status()["download"]["state"] not in ("done", "error"):
        time.sleep(0.05)
    st = tools.status()
    assert st["download"]["state"] == "done", st
    assert st["installed"] is True
    assert tools.ffmpeg_path().read_bytes() == binary
    assert tools.ffmpeg_path().stat().st_mode & 0o100, "must be executable"


def test_a_bad_checksum_installs_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    monkeypatch.setitem(tools.TOOLS, ("linux", "x64"),
                        ("ffmpeg-linux-x64", "0" * 64, "0" * 64))
    monkeypatch.setattr(tools.sys, "platform", "linux")
    monkeypatch.setattr(tools._platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(tools.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(gzip.compress(b"nope")))
    tools.start_download()
    deadline = time.time() + 10
    while time.time() < deadline and tools.status()["download"]["state"] not in ("done", "error"):
        time.sleep(0.05)
    st = tools.status()
    assert st["installed"] is False
    assert "checksum" in (st["download"]["error"] or "")


def test_remove_takes_only_the_apps_own_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    own = tools.ffmpeg_path()
    own.write_bytes(b"x")
    res = tools.remove()
    assert res["removed"] is True and res["installed"] is False


def test_the_api_answers_the_settings_row(tmp_path):
    d = pathlib.Path(tmp_path)
    app = api.create_app(download_dir=d / "dl", auth_token="testtoken",
                         db_path=d / "jobs.db")
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/tools/ffmpeg", headers=AUTH)
        assert r.status_code == 200
        assert "installed" in r.json() and "supported" in r.json()
        assert c.post("/tools/ffmpeg/remove", headers=AUTH).status_code == 200


def test_the_settings_row_exists_and_speaks():
    for pin in ('id="ffState"', 'id="ffGet"', 'id="ffRemove"', 'id="ffMeta"'):
        assert pin in HTML
    assert "refreshFfmpeg" in APP and "/tools/ffmpeg" in APP
    assert "initFfmpegRow" in APP
