"""v0.41.0 "the courier" — the engine side: manifest feed, staged download,
and the apply hand-off.

The feed reads a tiny version.json through releases/latest/download (no API
rate limit; the REST API stays the fallback). The download stages the asset
into the engine cache, verifies SHA-256, and only then reports ready. The
apply endpoint hands the staged file to the desktop shell's applier — the
shell owns spawning the installer and shutting down; Android installs
through its own bridge, never through this endpoint.
"""
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine import updater
from suravidl_engine.api import create_app

PAYLOAD = b"pretend installer bytes" * 64
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()

ROLE_ASSETS = {
    "windows_installer": "suravidl-windows-x64-setup.exe",
    "android_apk": "app-release.apk",
    "linux_appimage": "suravidl-linux-x64.AppImage",
}


def _manifest(version="99.0.0", url_host="https://github.com/LoLyeah/suravidl"):
    assets = {}
    for role, name in ROLE_ASSETS.items():
        assets[name] = {"url": f"{url_host}/releases/download/v{version}/{name}",
                        "size": len(PAYLOAD), "sha256": PAYLOAD_SHA}
    return {"version": version, "tag": f"v{version}",
            "repo": "LoLyeah/suravidl", "assets": assets, "roles": dict(ROLE_ASSETS)}


# --- the feed ---------------------------------------------------------------

def test_the_manifest_feed_is_primary_and_complete():
    r = updater.check_update("0.41.0", manifest_fn=lambda repo: _manifest())
    assert r["update_available"] is True
    assert r["latest"] == "99.0.0"
    assert r["manifest"] is True
    # on this (linux) test box the asset is the AppImage and no self-apply
    assert r["asset"]["name"] == "suravidl-linux-x64.AppImage"
    assert r["can_apply"] is False
    assert r["url"].endswith("v99.0.0")


def test_windows_and_android_can_self_apply(monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "win32")
    r = updater.check_update("0.41.0", manifest_fn=lambda repo: _manifest())
    assert r["can_apply"] is True
    assert r["apply_kind"] == "windows_installer"
    assert r["asset"]["name"] == "suravidl-windows-x64-setup.exe"

    monkeypatch.undo()
    monkeypatch.setenv("SURAVIDL_ANDROID", "1")
    monkeypatch.setattr(updater.sys, "platform", "linux")
    r = updater.check_update("0.41.0", manifest_fn=lambda repo: _manifest())
    assert r["can_apply"] is True
    assert r["apply_kind"] == "android_apk"
    assert r["asset"]["name"] == "app-release.apk"


def test_a_missing_manifest_falls_back_to_the_release_api():
    r = updater.check_update(
        "0.41.0",
        manifest_fn=lambda repo: (_ for _ in ()).throw(OSError("no manifest")),
        fetch_fn=lambda repo: {"tag_name": "v99.0.0",
                               "html_url": "https://example/v99.0.0"})
    assert r["update_available"] is True
    assert r["manifest"] is False
    assert r["asset"] is None
    assert r["can_apply"] is False


def test_the_old_contract_gains_the_new_keys():
    r = updater.check_update("0.5.0",
                             fetch_fn=lambda repo: {"tag_name": "v0.6.0"})
    for key in ("current", "latest", "update_available", "url",
                "asset", "can_apply", "apply_kind", "manifest"):
        assert key in r
    assert r["asset"] is None


def test_parse_orders_prereleases_below_the_release():
    """0.41.0-rc1 < 0.41.0 so rc installs get offered the final build
    (v0.41.x audit, finding 7)."""
    assert updater._parse("0.41.0-rc1") < updater._parse("0.41.0")
    assert updater._parse("v0.41.0-rc1") < updater._parse("v0.41.0")
    assert updater._parse("0.41.0") < updater._parse("0.41.1")


# --- the staged download ----------------------------------------------------

class _BlobHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *a):
        pass


@pytest.fixture()
def blob_url():
    srv = HTTPServer(("127.0.0.1", 0), _BlobHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/blob"
    srv.shutdown()


def test_download_verifies_then_lands(tmp_path, blob_url):
    st = updater.download_asset(blob_url, PAYLOAD_SHA, "app-release.apk",
                                tmp_path)
    assert st["status"] == "ready"
    assert st["sha256_ok"] is True
    assert open(st["path"], "rb").read() == PAYLOAD
    assert st["total"] == len(PAYLOAD)


def test_download_hash_mismatch_fails_clean(tmp_path, blob_url):
    st = updater.download_asset(blob_url, "0" * 64, "app-release.apk", tmp_path)
    assert st["status"] == "failed"
    assert "mismatch" in st["error"].lower()
    # nothing half-written is left behind: no final file, no partial
    assert not (tmp_path / "app-release.apk").exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_refuses_a_traversal_name(tmp_path, blob_url):
    with pytest.raises(ValueError):
        updater.download_asset(blob_url, None, "../evil.apk", tmp_path)


def test_download_refuses_a_missing_checksum(tmp_path, blob_url):
    """A manifest that carries no sha256 must not fail open: no checksum,
    no staging (v0.41.x audit, finding 1)."""
    for missing in (None, "", "   "):
        st = updater.download_asset(blob_url, missing, "app-release.apk", tmp_path)
        assert st["status"] == "failed", missing
        assert "checksum" in st["error"].lower()
        assert not (tmp_path / "app-release.apk").exists()
        assert not list(tmp_path.glob("*.part"))


def test_start_walks_the_flow_offline(tmp_path):
    seen = {}

    def fake_download(url, sha256, name, dest_dir):
        seen["url"], seen["name"] = url, name
        return {"status": "ready", "path": str(tmp_path / name),
                "sha256_ok": True, "bytes": 1, "total": 1, "name": name,
                "error": None}

    updater.reset_update_state()
    updater.start_update_download("0.41.0", manifest_fn=lambda repo: _manifest(),
                                  download_fn=fake_download, dest_dir=tmp_path)
    for _ in range(100):
        if updater.update_status()["status"] != "downloading":
            break
        threading.Event().wait(0.05)
    st = updater.update_status()
    assert st["status"] == "ready"
    assert seen["name"] == "suravidl-linux-x64.AppImage"  # this box
    assert seen["url"].startswith("https://github.com/LoLyeah/suravidl/")
    assert st["name"] == seen["name"]


def test_start_refuses_a_foreign_repo_url(tmp_path):
    """Any github repo is still the wrong repo: the prefix pins to this
    project's release path (v0.41.x audit, finding 6)."""
    updater.reset_update_state()
    updater.start_update_download(
        "0.41.0",
        manifest_fn=lambda repo: _manifest(url_host="https://github.com/attacker/mirror"),
        download_fn=lambda *a, **k: pytest.fail("must not download"),
        dest_dir=tmp_path)
    for _ in range(100):
        if updater.update_status()["status"] != "downloading":
            break
        threading.Event().wait(0.05)
    st = updater.update_status()
    assert st["status"] == "failed"
    assert "untrusted" in st["error"].lower()


def test_start_refuses_an_untrusted_url(tmp_path):
    updater.reset_update_state()
    updater.start_update_download(
        "0.41.0",
        manifest_fn=lambda repo: _manifest(url_host="https://evil.example"),
        download_fn=lambda *a, **k: pytest.fail("must not download"),
        dest_dir=tmp_path)
    for _ in range(100):
        if updater.update_status()["status"] != "downloading":
            break
        threading.Event().wait(0.05)
    st = updater.update_status()
    assert st["status"] == "failed"
    assert "untrusted" in st["error"].lower()


def test_start_is_claimed_once(tmp_path):
    """Two quick taps: the claim is visible under the lock BEFORE the
    blocking feed check, so only one check runs (v0.41.x audit, finding 2)."""
    updater.reset_update_state()
    calls = []
    gate = threading.Event()

    def slow_manifest(repo):
        calls.append(1)
        gate.set()
        threading.Event().wait(0.7)
        return _manifest()

    def fake_download(url, sha256, name, dest_dir):
        return {"status": "ready", "path": str(tmp_path / name),
                "sha256_ok": True, "bytes": 1, "total": 1, "name": name,
                "error": None}

    t = threading.Thread(target=lambda: updater.start_update_download(
        "0.41.0", manifest_fn=slow_manifest, download_fn=fake_download,
        dest_dir=tmp_path))
    t.start()
    assert gate.wait(2)
    second = updater.start_update_download(
        "0.41.0", manifest_fn=slow_manifest, download_fn=fake_download,
        dest_dir=tmp_path)
    assert second["status"] == "downloading"   # the claim is visible
    assert len(calls) == 1                     # and only one check ran
    t.join()


def test_a_locked_destination_still_fails_clean(tmp_path, blob_url, monkeypatch):
    """If the move into place fails (AV lock, handle), the .part must not
    survive (v0.41.x audit, finding 11)."""
    from pathlib import Path as _P

    def boom(self, target):
        raise PermissionError("locked by another process")

    monkeypatch.setattr(_P, "replace", boom)
    st = updater.download_asset(blob_url, PAYLOAD_SHA, "app-release.apk", tmp_path)
    assert st["status"] == "failed"
    assert "move" in st["error"].lower()
    assert not list(tmp_path.glob("*.part"))


# --- the endpoints ----------------------------------------------------------

def _client(tmp_path, **kw):
    app = create_app(download_dir=str(tmp_path), auth_token="t",
                     db_path=":memory:", **kw)
    return TestClient(app), {"Authorization": "Bearer t"}


def test_download_endpoint_reports_and_guards(tmp_path):
    updater.reset_update_state()
    c, h = _client(tmp_path,
                   update_download_fn=lambda: {"status": "downloading",
                                               "bytes": 1, "total": 2})
    r = c.post("/update/download", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "downloading"
    assert c.post("/update/download").status_code in (401, 403)


def test_status_endpoint_is_always_answerable(tmp_path):
    updater.reset_update_state()
    c, h = _client(tmp_path)
    r = c.get("/update/status", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] in ("idle", "downloading", "verifying",
                                  "ready", "failed")


def test_apply_hands_the_staged_file_to_the_desktop_shell(tmp_path):
    updater.reset_update_state(status="ready", path=str(tmp_path / "setup.exe"),
                               name="suravidl-windows-x64-setup.exe")
    seen = {}
    c, h = _client(tmp_path,
                   desktop_actions={"apply_update":
                                    lambda path=None: seen.update(path=path)})
    r = c.post("/update/apply", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["mode"] == "desktop"
    assert seen["path"] == str(tmp_path / "setup.exe")


def test_apply_refuses_while_downloads_run(tmp_path, monkeypatch):
    """The installer restarts the app; live downloads would die mid-stream.
    The guard consults the manager's listing (a restart marks stale rows
    interrupted, so a db seed cannot stay 'active') — pin one active job
    there and expect the refusal (v0.41.x audit, finding 8)."""
    from suravidl_engine import jobs as jobs_mod

    updater.reset_update_state(status="ready", path=str(tmp_path / "setup.exe"),
                               name="suravidl-windows-x64-setup.exe")
    monkeypatch.setattr(
        jobs_mod.JobManager, "list",
        lambda self: [{"id": "j1", "status": "downloading"}])
    c, h = _client(tmp_path,
                   desktop_actions={"apply_update": lambda path=None: True})
    r = c.post("/update/apply", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "download" in body["reason"].lower()


def test_apply_is_honest_without_an_applier(tmp_path):
    updater.reset_update_state(status="ready", path=str(tmp_path / "x"))
    c, h = _client(tmp_path)
    r = c.post("/update/apply", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "install" in body["reason"].lower() or "applier" in body["reason"].lower()


# --- the desktop applier (pins; the real spawn is Windows-only) -------------

def test_the_silent_upgrade_command_keeps_its_flags():
    import base64

    from suravidl_engine.__main__ import _windows_apply_command

    argv = _windows_apply_command("C:\\Temp\\suravidl-setup.exe",
                                  "C:\\App\\suravidl.exe")
    # one opaque argument (v0.43.2): nothing for CreateProcess re-quoting
    # to mangle — decode and read the script it will run
    assert argv[0] == "powershell.exe" and "-EncodedCommand" in argv
    script = base64.b64decode(argv[-1]).decode("utf-16-le")
    assert "/SILENT" in script and "/SP-" in script
    assert "/NORESTART" in script          # we own the relaunch
    assert "/CLOSEAPPLICATIONS" in script  # stragglers let go via RM
    assert "'C:\\Temp\\suravidl-setup.exe'" in script
    assert "'C:\\App\\suravidl.exe'" in script
    # the wait must survive a DETACHED process (no console): timeout.exe
    # dies instantly with no stdin — Start-Sleep is the console-free wait
    assert "Start-Sleep" in script
    # statements run in order regardless of any one step's outcome: the
    # app comes back even if the installer failed
    assert script.index("Start-Process") < script.index("Remove-Item")


def test_the_applier_honestly_refuses_outside_windows(tmp_path):
    from suravidl_engine.__main__ import _make_apply_update_action

    act = _make_apply_update_action(None)
    assert act(str(tmp_path / "whatever.exe")) is False
    assert act(None) is False


def test_the_desktop_actions_carry_the_applier():
    src = (Path(__file__).resolve().parents[1]
           / "src/suravidl_engine/__main__.py").read_text()
    assert '"apply_update": _make_apply_update_action(window)' in src
