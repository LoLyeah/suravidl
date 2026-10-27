"""v0.47.18 "the twin" — deleting one video must not take its twin.

Two downloads can end up with the same display name: MediaStore numbers the
second copy ("Movie (2).mp4"), and the app's own matcher deliberately accepted
numbered variants. So trashing one row deleted every same-named copy in the
gallery — the user's report.

The fix deletes by identity: the MediaStore URI the job's import created is
remembered, and the trash asks for *that* job's rows. The name route stays only
as a fallback for jobs imported before this release.
"""
import pathlib
import re

from suravidl_engine import __version__
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
JAVA = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "suravidl" / "app"
MAIN = (JAVA / "MainActivity.kt").read_text()
LIB = (JAVA / "MediaLibrary.kt").read_text()
ENGINE = (JAVA / "EngineService.kt").read_text()
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_name_this_release():
    assert __version__ == "0.47.18"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the twin"
    assert len(ENTRIES) == 10
    for item in ENTRIES[0]["items"]:
        assert 0 < len(item) <= 220


def test_the_library_remembers_the_uri_of_each_copy():
    assert "fun rememberCopy(" in LIB
    assert "fun deleteOwnCopiesForJob(" in LIB
    # the key is the uri, not the display name
    assert "imported_uris" in LIB
    assert "contentResolver.delete(uri, null, null)" in LIB


def test_the_import_records_what_it_created():
    assert "MediaLibrary.rememberCopy(this, id, copy)" in ENGINE


def test_the_bridge_offers_job_identity_deletion():
    assert "fun deleteMediaForJob(" in MAIN
    assert "MediaLibrary.deleteOwnCopiesForJob" in MAIN


def test_the_ui_prefers_the_job_id_and_keeps_the_name_only_as_a_fallback():
    # two call sites (one row, clear filed), each a guard + a call
    assert APP.count("deleteMediaForJob(j.id)") == 2, (
        "both trash paths must delete by job id")
    # the name route survives only as the fallback for older copies
    assert APP.count("window.AndroidHost.deleteMediaNamed(name)") == 2
