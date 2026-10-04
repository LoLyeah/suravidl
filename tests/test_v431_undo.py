"""v0.43.1 "the undo" — the downloaded yt-dlp copy can be removed again.

v0.43.0 gave packaged builds a second copy that shadows the bundled one
while it is newer. v0.43.1 makes that reversible by hand: a staged copy
is canceled, an active one hands back to the bundle on the next start,
and the tab says where the running copy comes from so the state is never
ambiguous. The bundle itself is never touched by any of this — the
downloaded copy is the only thing that ever lives or dies here.
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine import __version__
from suravidl_engine.api import create_app

ROOT = Path(__file__).parent.parent
ENGINE = ROOT / "src" / "suravidl_engine"
APPJS = (ENGINE / "web" / "app.js").read_text()
HTML = (ENGINE / "web" / "index.html").read_text()
AUTH = {"Authorization": "Bearer t"}


def _plant_shadow(base, version):
    """A copy as stage_update leaves it on disk (same shape as v0.43.0)."""
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
        "version": version, "baseline": "2026.1.1", "app": __version__}))
    return sh


def _client(tmp_path):
    app = create_app(download_dir=tmp_path / "dl", auth_token="t",
                     db_path=tmp_path / "jobs.db")
    return TestClient(app)


# -- engine: the removal itself ----------------------------------------------

def test_remove_shadow_deletes_the_downloaded_copy(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path, "2026.9.9")
    r = yu.remove_shadow(db_path=tmp_path / "jobs.db")
    assert r["ok"] is True and r["removed"] is True
    assert r["version"] == "2026.9.9"
    assert not sh.exists()


def test_remove_shadow_with_nothing_downloaded_is_a_quiet_noop(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    r = yu.remove_shadow(db_path=tmp_path / "jobs.db")
    assert r == {"ok": True, "removed": False, "version": None}


def test_remove_shadow_also_cleans_stage_scratch(tmp_path):
    from suravidl_engine import ytdlp_update as yu

    _plant_shadow(tmp_path, "2026.9.9")
    (tmp_path / "ytdlp.old").mkdir()
    (tmp_path / "ytdlp.whl.part").write_bytes(b"half")
    (tmp_path / "ytdlp.stage.x").mkdir()
    yu.remove_shadow(db_path=tmp_path / "jobs.db")
    for leftover in ("ytdlp", "ytdlp.old", "ytdlp.whl.part", "ytdlp.stage.x"):
        assert not (tmp_path / leftover).exists(), leftover


def test_removal_also_drops_the_stale_import_path_entry(tmp_path, monkeypatch):
    # a deleted directory left on sys.path would keep shadowing nothing —
    # it must not linger for whatever asks next (v0.43.0 regression terms)
    from suravidl_engine import ytdlp_update as yu

    sh = _plant_shadow(tmp_path, "2026.9.9")
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"
    yu.remove_shadow(db_path=tmp_path / "jobs.db")
    assert str(sh) not in sys.path


def test_after_removal_the_bundle_takes_over(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    _plant_shadow(tmp_path, "2026.9.9")
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"
    yu.remove_shadow(db_path=tmp_path / "jobs.db")
    # what the next start sees: nothing staged, nothing on the path
    assert yu.activate(db_path=tmp_path / "jobs.db") is None


def test_active_source_names_the_running_copy(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    monkeypatch.setattr(sys, "path", list(sys.path))
    src = yu.active_source(db_path=tmp_path / "jobs.db")
    assert src in ("environment", "bundled")  # not frozen in the test venv
    _plant_shadow(tmp_path, "2026.9.9")
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"
    assert yu.active_source(db_path=tmp_path / "jobs.db") == "downloaded"


# -- api: /version says where the copy comes from; /ytdlp/remove deletes -----

def test_version_reports_the_source_and_the_stage(tmp_path):
    with _client(tmp_path) as c:
        v = c.get("/version", headers=AUTH).json()
        assert v["source"] in ("environment", "bundled")
        assert v["staged"] is None
        _plant_shadow(tmp_path, "2026.9.9")
        v2 = c.get("/version", headers=AUTH).json()
        # on disk but not yet active: staged, and the source is unchanged
        assert v2["staged"] == "2026.9.9"
        assert v2["source"] == v["source"]


def test_remove_endpoint_requires_auth(tmp_path):
    with _client(tmp_path) as c:
        r = c.post("/ytdlp/remove")
        assert r.status_code in (401, 403)


def test_remove_endpoint_cancels_a_stage(tmp_path):
    _plant_shadow(tmp_path, "2026.9.9")
    with _client(tmp_path) as c:
        r = c.post("/ytdlp/remove", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["removed"] is True
        assert body["version"] == "2026.9.9"
        assert body["was_active"] is False
        assert not (tmp_path / "ytdlp").exists()
        assert c.get("/version", headers=AUTH).json()["staged"] is None


def test_remove_endpoint_takes_over_from_an_active_copy(tmp_path, monkeypatch):
    from suravidl_engine import ytdlp_update as yu

    _plant_shadow(tmp_path, "2026.9.9")
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert yu.activate(db_path=tmp_path / "jobs.db") == "2026.9.9"
    with _client(tmp_path) as c:
        v = c.get("/version", headers=AUTH).json()
        assert v["source"] == "downloaded"
        body = c.post("/ytdlp/remove", headers=AUTH).json()
        assert body["was_active"] is True and body["removed"] is True
        assert not (tmp_path / "ytdlp").exists()


# -- web: the tab carries the undo --------------------------------------------

def test_the_ytdlp_tab_has_a_remove_control_wired_to_the_endpoint():
    assert 'id="removeBtn"' in HTML
    assert 'id="ytdlpRemoveRow"' in HTML
    assert 'id="ytdlpSrc"' in HTML
    assert "Remove downloaded copy" in HTML
    assert "/ytdlp/remove" in APPJS
    # the confirm must say what actually happens — back to the bundle
    assert "bundled with the app" in APPJS


def test_the_remove_row_stays_hidden_until_something_is_downloaded():
    i = HTML.index('id="ytdlpRemoveRow"')
    seg = HTML[i:i + 300]
    assert "hidden" in seg[:200]


def test_the_versions_line_shows_where_the_copy_comes_from():
    assert 'id="ytdlpSrc"' in HTML
    for marker in ('"(downloaded)"', '"(bundled)"'):
        assert marker in APPJS


def test_the_handful_entry_retired_cleanly_with_the_twelfth():
    """The rolling card keeps ten entries — v0.43.1's entry pushed out
    "The handful" (0.40.7). Its feature lives on in test_v407_handful.py,
    its words live in the release notes, and no half-entry may remain here."""
    from suravidl_engine import whatsnew

    versions = [e["version"] for e in whatsnew.ENTRIES]
    assert len(versions) == 10
    assert "0.40.7" not in versions
    assert all(e["title"] != "The handful" for e in whatsnew.ENTRIES)
