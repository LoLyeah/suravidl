"""v0.47.9 "the ghost" — the phone app sweeps abandoned gallery imports.

Field report (2026-10-18): Movies/suravidl looked empty in three different
file managers while its properties claimed 18 items / 516 MB. The bytes are
real and ours: an import inserted a MediaStore row as IS_PENDING, Android
killed the copy mid-way, and a pending item lives on disk as a hidden
`.pending-*` file — invisible in every listing, still counted by the index.
The app now deletes its own abandoned pending rows at every start (deleting
the row deletes the file), and a finished copy is never touched.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KT = ROOT / "android/app/src/main/java/com/suravidl/app"
LIB = (KT / "MediaLibrary.kt").read_text()
ACT = (KT / "MainActivity.kt").read_text()
IMP = (KT / "MediaImporter.kt").read_text()
TEST = (ROOT / "android/app/src/androidTest/java/com/suravidl/app"
        / "MediaLibraryTest.kt").read_text()


def test_the_sweep_takes_only_this_apps_pending_rows():
    seg = LIB[LIB.index("fun sweepPending"):]
    # no WHERE terms: providers reject selections on owner_package_name /
    # is_pending and the failure is silent (board, 2026-10-21) — everything
    # is filtered in code instead
    assert "arrayOf(context.packageName)" not in seg, "no owner selection"
    assert "cursor.getInt(2) != 1" in seg, "only unfinished copies"
    assert "owner != context.packageName" in seg, "only our own rows"
    assert "QUERY_ARG_MATCH_PENDING" in seg, "pending rows must be asked for"
    assert "path.contains(FOLDER)" not in seg, \
        "a pending row's RELATIVE_PATH is not reliable — owner+pending is the rule"
    assert "resolver.delete(uri, null, null)" in seg, "the row (and its file) goes"
    assert "lastSweepError" in LIB, "a failure names itself"


def test_the_app_sweeps_at_every_start():
    i = ACT.index("override fun onCreate")
    seg = ACT[i:i + 1200]
    assert "MediaLibrary.sweepPending(this)" in seg
    assert "Thread {" in seg, "never on the main thread"


def test_a_finished_import_is_still_finalized():
    assert "IS_PENDING, 1)" in IMP
    assert "IS_PENDING, 0" in IMP
    assert "resolver.delete(uri, null, null)" in IMP, "a failed publish is taken back"


def test_the_emulator_proves_it_end_to_end():
    assert "fun anAbandonedPendingImportIsSwept" in TEST
    assert "fun aProperlyPublishedImportSurvivesTheSweep" in TEST
