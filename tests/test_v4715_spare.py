"""v0.47.15 "the spare" — the phone ships no ffmpeg fetcher.

The phone's ffmpeg has always been inside the APK (nativeLibraryDir, exported
as SURAVIDL_FFMPEG). v0.47.13 added an on-demand fetch for desktop, and the
Android build carried that module too — dead code that could only ever do the
wrong thing there. Chaquopy 3.11 has no per-file exclude, so the engine is
staged without tools.py before it is packaged, and the release build proves it
at the artifact level.
"""
import builtins
import pathlib
import subprocess
import sys
import zipfile

from suravidl_engine import __version__, api
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRADLE = (ROOT / "android" / "app" / "build.gradle").read_text()
WORKFLOW = (ROOT / ".github" / "workflows" / "android.yml").read_text()
CHECKER = ROOT / "android" / "scripts" / "check_no_fetcher.py"
AUTH = {"Authorization": "Bearer testtoken"}


def test_the_notes_name_this_release():
    assert __version__ == "0.47.15"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the spare"
    assert len(ENTRIES) == 10


def test_the_android_build_stages_the_engine_without_the_fetcher():
    assert "stageAndroidEngine" in GRADLE
    assert "exclude 'suravidl_engine/tools.py'" in GRADLE
    assert "python.srcDir stagedPythonDir" in GRADLE
    # preBuild is the earliest hook Chaquopy's task graph respects
    assert "dependsOn(stageAndroidEngine)" in GRADLE
    assert "../../src" in GRADLE, "the source of the copy must still be the tree"


def test_the_release_build_checks_the_artifact():
    assert "check_no_fetcher.py" in WORKFLOW
    assert WORKFLOW.index("check_no_fetcher.py") > WORKFLOW.index("assembleRelease")


def _fake_apk(path: pathlib.Path, engine_files: dict[str, bytes]) -> None:
    """An APK-shaped zip with a Chaquopy archive holding the given files."""
    import io

    imy = io.BytesIO()
    with zipfile.ZipFile(imy, "w") as inner:
        for name, data in engine_files.items():
            inner.writestr(f"suravidl_engine/{name}", data)
    with zipfile.ZipFile(path, "w") as apk:
        apk.writestr("AndroidManifest.xml", b"<manifest/>")
        apk.writestr("assets/chaquopy/app.imy", imy.getvalue())


def _run_checker(apk: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECKER), str(apk)],
                          capture_output=True, text=True)


def test_the_checker_passes_an_apk_without_the_fetcher(tmp_path):
    apk = tmp_path / "ok.apk"
    _fake_apk(apk, {"api.py": b"from fastapi import FastAPI\n",
                    "cut.py": b"def ffmpeg_exe(): return 'bundled'\n"})
    out = _run_checker(apk)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "no fetcher" in out.stdout


def test_the_checker_catches_an_apk_that_still_carries_it(tmp_path):
    apk = tmp_path / "bad.apk"
    _fake_apk(apk, {"api.py": b"from fastapi import FastAPI\n",
                    "tools.py": b"def start_download():\n    pass\n"})
    out = _run_checker(apk)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "FETCHER IN APK" in out.stdout


def test_the_checker_refuses_an_apk_with_no_engine_at_all(tmp_path):
    # a staging task that silently copied nothing would otherwise "pass"
    apk = tmp_path / "empty.apk"
    with zipfile.ZipFile(apk, "w") as z:
        z.writestr("AndroidManifest.xml", b"<manifest/>")
    out = _run_checker(apk)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "not in the APK" in out.stdout


def test_the_settings_routes_survive_a_build_without_the_module(tmp_path, monkeypatch):
    """The APK has no tools.py: asking for its status must not 500."""
    import suravidl_engine

    # both halves of the import: the module slot AND the package attribute
    # (an earlier test may have bound it already)
    monkeypatch.delattr(suravidl_engine, "tools", raising=False)
    monkeypatch.setitem(sys.modules, "suravidl_engine.tools", None)
    d = pathlib.Path(tmp_path)
    app = api.create_app(download_dir=d / "dl", auth_token="testtoken",
                         db_path=d / "jobs.db")
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        st = c.get("/tools/ffmpeg", headers=AUTH)
        assert st.status_code == 200, st.text
        body = st.json()
        assert body["supported"] is False and body["installed"] is True
        assert "Android" in body["note"]
        assert c.post("/tools/ffmpeg", headers=AUTH).status_code == 501
        assert c.post("/tools/ffmpeg/remove", headers=AUTH).status_code == 501


def test_the_desktop_still_has_the_fetcher(tmp_path, monkeypatch):
    """The exclusion is Android-only: the module is still the desktop's."""
    from suravidl_engine import tools

    monkeypatch.setenv("SURAVIDL_TOOLS_DIR", str(tmp_path))
    monkeypatch.delenv("SURAVIDL_ANDROID", raising=False)
    st = tools.status()
    assert st["supported"] is True
    assert st["note"] == ""
