"""v0.43.0 "the refresh" — yt-dlp updates reach every build.

A packaged app (PyInstaller one-file on Windows/macOS/Linux, Chaquopy on
Android) carries yt-dlp inside itself: there is no pip to run and nowhere
for one to install. So packaged builds get the second copy: the official
yt-dlp wheel is fetched from PyPI, its sha256 verified against PyPI's own
metadata, unpacked next to jobs.db, and preferred from the next start.

The rules pinned here:
  * newer wins — by numeric calendar-version comparison, never by "the
    downloaded one always wins" (an app update may ship something newer);
  * a stale staged copy is removed once the app carries a newer one;
  * without runtime metadata to compare against, a stage is trusted only
    while it was staged under the same app version;
  * nothing is installed unverified: pythonhosted.org only, https only,
    sha256 checked, zip entries that reach outside the wheel refused.
"""
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine import __version__
from suravidl_engine.api import create_app

ROOT = Path(__file__).parent.parent
ENGINE = ROOT / "src" / "suravidl_engine"
APPJS = (ENGINE / "web" / "app.js").read_text()
HTML = (ENGINE / "web" / "index.html").read_text()
MAINPY = (ENGINE / "__main__.py").read_text()
SPEC = (ROOT / "suravidl.spec").read_text()
AUTH = {"Authorization": "Bearer t"}


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _wheel(version, host="files.pythonhosted.org", sha="ab" * 32, size=1000,
           py_tag="py3"):
    name = f"yt_dlp-{version}-{py_tag}-none-any.whl"
    return {"filename": name, "packagetype": "bdist_wheel",
            "url": f"https://{host}/packages/aa/bb/{name}",
            "digests": {"sha256": sha}, "size": size}


def _payload(releases):
    return {"info": {"version": "0"}, "releases": releases}


def _wheel_zip(version, evil=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("yt_dlp/__init__.py", "from .version import __version__\n")
        z.writestr("yt_dlp/version.py", f'__version__ = "{version}"\n')
        z.writestr(f"yt_dlp-{version}.dist-info/METADATA",
                   f"Metadata-Version: 2.1\nName: yt-dlp\nVersion: {version}\n")
        if evil:
            z.writestr("../evil.py", "boom\n")
    return buf.getvalue()


def _fake_download(payload_bytes):
    def _dl(url, dest: Path):
        dest.write_bytes(payload_bytes)
        return len(payload_bytes)
    return _dl


def _plant_shadow(base, version, app_stamp=None, baseline="2026.1.1"):
    """A staged copy as stage_update leaves it on disk."""
    sh = base / "ytdlp"
    pkg = sh / "yt_dlp"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("from .version import __version__\n")
    (pkg / "version.py").write_text(f'__version__ = "{version}"\n')
    di = sh / f"yt_dlp-{version}.dist-info"
    di.mkdir()
    (di / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: yt-dlp\nVersion: {version}\n")
    (sh / "staged.json").write_text(json.dumps({
        "version": version, "baseline": baseline,
        "app": app_stamp if app_stamp is not None else __version__}))
    return sh


# -- version math: calendar versions, numerically -----------------------------

def test_calendar_versions_compare_numerically_not_as_strings():
    from suravidl_engine import ytdlp_update as yu

    assert yu.is_newer("2026.10.1", "2026.8.19")  # a string compare fails here
    assert yu.is_newer("2027.1.1", "2026.12.31")
    assert yu.is_newer("2026.8.19", "2026.8.4")
    assert not yu.is_newer("2026.8.19", "2026.8.19")
    assert not yu.is_newer("2026.7.1", "2026.8.19")


def test_nightlies_are_not_stable_versions():
    from suravidl_engine import ytdlp_update as yu

    assert not yu.is_stable("2026.9.0.dev0")
    assert not yu.is_stable("2026.9.0rc1")
    assert yu.is_stable("2026.8.19")
    assert yu.is_stable("2026.8.19.1")


# -- picking the right release on PyPI ----------------------------------------

def test_pick_stable_skips_nightlies_and_takes_the_calendar_max():
    from suravidl_engine import ytdlp_update as yu

    got = yu.pick_stable(_payload({
        "2026.8.19": [_wheel("2026.8.19")],
        "2026.9.0.dev0": [_wheel("2026.9.0.dev0")],
        "2026.10.1": [_wheel("2026.10.1")],
        "2026.7.2": [_wheel("2026.7.2")],
    }))
    assert got["version"] == "2026.10.1"
    assert got["url"].startswith("https://files.pythonhosted.org/")
    assert len(got["sha256"]) == 64


def test_pick_stable_walks_down_until_a_verifiable_wheel_exists():
    from suravidl_engine import ytdlp_update as yu

    good = _wheel("2026.9.1")
    off_host = _wheel("2026.9.2", host="evil.example.com")
    no_digest = _wheel("2026.9.3")
    no_digest["digests"] = {}
    abi = _wheel("2026.9.4", py_tag="cp311")
    plain_http = _wheel("2026.9.5")
    plain_http["url"] = plain_http["url"].replace("https://", "http://")
    got = yu.pick_stable(_payload({
        "2026.9.5": [plain_http], "2026.9.4": [abi],
        "2026.9.3": [no_digest], "2026.9.2": [off_host],
        "2026.9.1": [good],
    }))
    assert got["version"] == "2026.9.1"  # nothing newer is acceptable


def test_pick_stable_none_when_nothing_qualifies():
    from suravidl_engine import ytdlp_update as yu

    sdist = {"filename": "yt_dlp-2026.9.9.tar.gz", "packagetype": "sdist",
             "url": "https://files.pythonhosted.org/x.tar.gz",
             "digests": {"sha256": "cd" * 32}, "size": 10}
    assert yu.pick_stable(_payload({"2026.9.9": [sdist]})) is None


# -- staging: download, verify, unpack, swap ----------------------------------

def test_stage_update_fetches_verifies_and_installs_beside_jobs_db(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    blob = _wheel_zip("2026.9.9")
    releases = {"2026.9.9": [_wheel("2026.9.9", sha=_sha(blob), size=len(blob))]}
    r = yu.stage_update(db_path=tmp_path / "jobs.db",
                        fetch_json=lambda: _payload(releases),
                        download=_fake_download(blob),
                        before="2026.8.19")
    shadow = tmp_path / "ytdlp"
    assert r["ok"] is True and r["updated"] is True
    assert r["before"] == "2026.8.19" and r["after"] == "2026.9.9"
    assert r["restart"] is True and r["bundled"] is True
    assert yu.shadow_version(shadow) == "2026.9.9"
    meta = json.loads((shadow / "staged.json").read_text())
    assert meta["version"] == "2026.9.9" and meta["baseline"] == "2026.8.19"
    assert meta["app"] == __version__
    assert not (tmp_path / "ytdlp.whl.part").exists()
    assert not list(tmp_path.glob("ytdlp.stage.*"))


def test_stage_update_replaces_an_older_staged_copy(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    _plant_shadow(tmp_path, "2026.9.1")
    blob = _wheel_zip("2026.9.9")
    releases = {"2026.9.9": [_wheel("2026.9.9", sha=_sha(blob), size=len(blob))]}
    r = yu.stage_update(db_path=tmp_path / "jobs.db",
                        fetch_json=lambda: _payload(releases),
                        download=_fake_download(blob),
                        before="2026.9.1")
    assert r["updated"] is True
    assert yu.shadow_version(tmp_path / "ytdlp") == "2026.9.9"
    assert not list(tmp_path.glob("ytdlp.old*"))
    assert not list(tmp_path.glob("ytdlp.stage.*"))


def test_stage_update_says_already_latest_and_touches_nothing(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    blob = _wheel_zip("2026.8.19")
    releases = {"2026.8.19": [_wheel("2026.8.19", sha=_sha(blob))]}
    r = yu.stage_update(db_path=tmp_path / "jobs.db",
                        fetch_json=lambda: _payload(releases),
                        download=_fake_download(blob),
                        before="2026.8.19")
    assert r["ok"] is True and r["updated"] is False
    assert "latest" in r["detail"]
    assert not (tmp_path / "ytdlp").exists()


def test_stage_update_refuses_a_wheel_whose_sha256_does_not_match(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    blob = _wheel_zip("2026.9.9")
    releases = {"2026.9.9": [_wheel("2026.9.9", sha="de" * 32, size=len(blob))]}
    r = yu.stage_update(db_path=tmp_path / "jobs.db",
                        fetch_json=lambda: _payload(releases),
                        download=_fake_download(blob),
                        before="2026.8.19")
    assert r["ok"] is False and r["updated"] is False
    assert "sha256" in r["detail"].lower()
    assert not (tmp_path / "ytdlp").exists()
    assert not (tmp_path / "ytdlp.whl.part").exists()


def test_stage_update_refuses_a_wheel_that_reaches_outside_itself(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    blob = _wheel_zip("2026.9.9", evil=True)
    releases = {"2026.9.9": [_wheel("2026.9.9", sha=_sha(blob), size=len(blob))]}
    r = yu.stage_update(db_path=tmp_path / "jobs.db",
                        fetch_json=lambda: _payload(releases),
                        download=_fake_download(blob),
                        before="2026.8.19")
    assert r["ok"] is False
    assert not (tmp_path / "ytdlp").exists()
    assert not (tmp_path / "evil.py").exists()


def test_stage_update_refuses_an_absurdly_large_wheel_before_downloading(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    big = _wheel("2026.9.9", size=999_000_000)
    called = {"n": 0}

    def _dl(url, dest):
        called["n"] += 1
        raise AssertionError("must not download")

    r = yu.stage_update(db_path=tmp_path / "jobs.db",
                        fetch_json=lambda: _payload({"2026.9.9": [big]}),
                        download=_dl, before="2026.8.19")
    assert r["ok"] is False and called["n"] == 0


def test_stage_update_survives_pypi_being_unreachable(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    def boom():
        raise OSError("no network")

    r = yu.stage_update(db_path=tmp_path / "jobs.db", fetch_json=boom,
                        before="2026.8.19")
    assert r["ok"] is False and r["updated"] is False
    assert "no network" in r["detail"]


# -- the boot decision: newer wins, stale is swept ----------------------------

def test_activate_puts_the_newer_stage_ahead_of_the_bundle(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    fresh = _plant_shadow(tmp_path, "2026.9.9")
    monkeypatch.setattr(yu, "bundled_version", lambda: "2026.8.19")
    monkeypatch.setattr(sys, "path", list(sys.path))
    # a crashed stage never survives a boot either
    (tmp_path / "ytdlp.whl.part").write_bytes(b"x")
    (tmp_path / "ytdlp.stage.999").mkdir()
    v = yu.activate(db_path=tmp_path / "jobs.db")
    assert v == "2026.9.9"
    assert sys.path[0] == str(fresh)
    assert not (tmp_path / "ytdlp.whl.part").exists()
    assert not list(tmp_path.glob("ytdlp.stage.*"))


def test_activate_removes_a_stale_stage_the_app_has_superseded(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    stale = _plant_shadow(tmp_path, "2026.1.1")
    monkeypatch.setattr(yu, "bundled_version", lambda: "2026.8.19")
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") is None
    assert not stale.exists()
    assert str(stale) not in sys.path


def test_activate_without_metadata_trusts_a_same_app_stage(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    _plant_shadow(tmp_path, "2026.9.9", app_stamp=__version__)
    monkeypatch.setattr(yu, "bundled_version", lambda: None)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"


def test_activate_without_metadata_prefers_a_bundle_from_a_newer_app(tmp_path, monkeypatch):
    """After an app update the bundle may be newer than the stage; with no
    metadata to compare, the app's own copy wins until the user re-taps
    Update (which re-stages the true latest)."""
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path, "2026.9.9", app_stamp="0.41.0")
    monkeypatch.setattr(yu, "bundled_version", lambda: None)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") is None
    assert str(sh) not in sys.path
    assert sh.exists()  # kept: nothing runs from it, re-tapping converges


def test_activate_clears_a_corrupt_stage(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    sh = tmp_path / "ytdlp"
    (sh / "yt_dlp").mkdir(parents=True)  # no dist-info: a torn extraction
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") is None
    assert not sh.exists()


def test_activate_twice_in_a_row_keeps_the_activated_shadow(tmp_path, monkeypatch):
    """The frozen app calls activate() twice per boot: main() and then
    start_server(). After the first call the shadow is on sys.path, so a
    second call's importlib.metadata scan sees the SHADOW as "the bundle"
    — the naive re-check classified it stale and deleted the update it had
    just activated. The first decision must stand within a process."""
    from suravidl_engine import ytdlp_update as yu

    fresh = _plant_shadow(tmp_path, "2026.9.9")
    monkeypatch.setattr(sys, "path", list(sys.path))

    def honest_metadata():
        # faithful to importlib.metadata: it scans sys.path, so once the
        # shadow is on the path it reports the shadow's version
        return yu.shadow_version(fresh) if str(fresh) in sys.path else "2026.8.19"

    monkeypatch.setattr(yu, "bundled_version", honest_metadata)
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"   # main()
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"   # start_server()
    assert fresh.exists(), "the second call wiped the activated update"
    assert sys.path[0] == str(fresh)


def test_pending_version_reports_a_stage_waiting_for_restart(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    _plant_shadow(tmp_path, "2026.9.9")
    monkeypatch.setattr(yu, "active_version", lambda: "2026.8.19")
    assert yu.pending_version(tmp_path / "jobs.db") == "2026.9.9"
    monkeypatch.setattr(yu, "active_version", lambda: "2026.9.9")
    assert yu.pending_version(tmp_path / "jobs.db") is None


# -- the real interpreter actually loads the shadow ---------------------------

_SUBPROCESS_PROBE = """
import sys
sys.path.insert(0, r"{src}")
from suravidl_engine import ytdlp_update
v = ytdlp_update.activate(db_path=r"{db}")
import yt_dlp
print("activated:", v)
print("effective:", yt_dlp.version.__version__)
print("origin:", yt_dlp.__file__)
"""


def test_a_staged_shadow_shadows_the_bundled_yt_dlp_for_real(tmp_path):
    _plant_shadow(tmp_path, "9999.1.1")
    code = _SUBPROCESS_PROBE.format(src=ROOT / "src", db=tmp_path / "jobs.db")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    assert "activated: 9999.1.1" in out.stdout
    assert "effective: 9999.1.1" in out.stdout
    assert str(tmp_path / "ytdlp") in out.stdout


def test_a_stale_shadow_is_removed_by_the_real_interpreter(tmp_path):
    _plant_shadow(tmp_path, "1.0")
    code = _SUBPROCESS_PROBE.format(src=ROOT / "src", db=tmp_path / "jobs.db")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    assert "activated: None" in out.stdout
    assert not (tmp_path / "ytdlp").exists()


# -- routing: pip where pip exists, wheel everywhere else ---------------------

def test_self_update_routes_to_the_wheel_path_when_pip_is_absent(monkeypatch):
    from suravidl_engine import updater, ytdlp_update

    monkeypatch.setattr(updater, "updates_possible", lambda: False)
    seen = {}

    def fake_stage(db_path=None, before=None):
        seen["db"] = db_path
        return {"ok": True, "updated": True, "bundled": True,
                "before": "2026.1.1", "after": "2026.9.9",
                "restart": True, "detail": "staged"}

    monkeypatch.setattr(ytdlp_update, "stage_update", fake_stage)
    r = updater.self_update(db_path="/x/jobs.db")
    assert seen["db"] == "/x/jobs.db"
    assert r["updated"] is True and r["restart"] is True and r["bundled"] is True


def test_the_update_endpoint_hands_the_db_path_to_the_wheel_path(tmp_path, monkeypatch):
    from suravidl_engine import updater, ytdlp_update

    monkeypatch.setattr(updater, "updates_possible", lambda: False)
    calls = {}

    def fake_stage(db_path=None, before=None):
        calls["db"] = db_path
        return {"ok": True, "updated": False, "bundled": True,
                "before": "2026.8.19", "after": "2026.8.19",
                "detail": "already on the latest release (2026.8.19)"}

    monkeypatch.setattr(ytdlp_update, "stage_update", fake_stage)
    app = create_app(download_dir=tmp_path, auth_token="t",
                     db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        r = c.post("/update", headers=AUTH)
    assert r.status_code == 200
    assert Path(calls["db"]) == tmp_path / "jobs.db"


def test_version_endpoint_reports_a_pending_stage(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update

    monkeypatch.setattr(ytdlp_update, "pending_version",
                        lambda db_path=None: "2026.9.9")
    app = create_app(download_dir=tmp_path, auth_token="t",
                     db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        r = c.get("/version", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["staged"] == "2026.9.9"


# -- the UI stops refusing and starts explaining ------------------------------

def test_the_packaged_build_tooltip_says_where_updates_come_from():
    seg = APPJS.split("u.bundled", 1)[1][:600]
    assert ".disabled" not in seg, "v0.43: packaged builds update from PyPI now"
    assert "PyPI" in seg


def test_the_update_handler_speaks_restart_when_the_stage_waits():
    handler = APPJS.split('$("updateBtn").onclick', 1)[1][:1000]
    assert "loadVersions()" in handler
    assert "restart" in handler


def test_the_ytdlp_card_can_show_a_stage_waiting_for_restart():
    card = HTML.split('id="panel-ytdlp"', 1)[1].split("</section>", 1)[0]
    assert 'id="ytdlpStaged"' in card
    assert "ytdlpStaged" in APPJS
    seg = APPJS.split("ytdlpStaged", 1)[1][:400]
    assert "restart" in seg


# -- the entry points: activate before anything imports yt_dlp ----------------

def test_start_server_activates_the_shadow_before_any_yt_dlp_import():
    i = MAINPY.index("def start_server")
    seg = MAINPY[i:i + 1600]
    assert "ytdlp_update" in seg and "activate_safe(" in seg
    # must run before the sweep — importing updater imports yt_dlp
    assert seg.index("activate_safe(") < seg.index("sweep_stale_downloads")


def test_main_activates_right_after_the_arguments_parse():
    i = MAINPY.index("def main()")
    j = MAINPY.index("args = p.parse_args()", i)
    seg = MAINPY[j:j + 900]
    assert "activate_safe(" in seg
    k = MAINPY.index("activate_safe(", j)
    assert k < MAINPY.index("start_server(", j)


def test_the_spec_keeps_ytdlp_metadata_for_the_stale_stage_check():
    # without dist-info in the frozen bundle, bundled_version() cannot
    # compare, and a stale stage after an app update would be trusted
    assert "copy_metadata" in SPEC
    assert '"yt-dlp"' in SPEC or "'yt-dlp'" in SPEC


def test_the_pypi_fetches_trust_the_same_store_as_the_rest_of_the_app():
    # net.py exists because a frozen macOS bundle verifies nothing with a
    # stock urlopen; yt-dlp's own downloads must not be the one path that
    # forgot that (v0.43.0 mac freeze check)
    src = (ENGINE / "ytdlp_update.py").read_text()
    assert "from .net import ssl_context" in src
    assert src.count("context=ssl_context()") >= 2


def test_ytdlp_update_module_stays_import_light():
    import ast

    tree = ast.parse((ENGINE / "ytdlp_update.py").read_text())
    for node in tree.body:  # module level only — lazy imports are fine
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] != "yt_dlp", \
                    "the shadow decision must precede the first yt_dlp import"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "yt_dlp", \
                "the shadow decision must precede the first yt_dlp import"

def test_the_tally_entry_retired_cleanly_with_the_eleventh():
    """The rolling card keeps ten entries — v0.43.0's entry pushed out "The
    tally" (0.40.6). Its feature lives on in test_v406_badge.py, its words
    live in the release notes, and no half-entry may remain here."""
    from suravidl_engine import whatsnew

    versions = [e["version"] for e in whatsnew.ENTRIES]
    assert len(versions) == 10
    assert "0.40.6" not in versions
    assert all(e["title"] != "The tally" for e in whatsnew.ENTRIES)
