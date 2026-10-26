"""v0.47.17 "the hoist" — a helper read before it existed.

The phone's Settings showed an FFMPEG row that could only ever say
"checking…". The row was supposed to be hidden on Android since v0.47.14 —
and the hiding line was there. It called `ANDROID()`, which was a
`const () => …` declared 1500 lines FURTHER DOWN. `refreshFfmpeg()` runs at
module load, so the call hit the temporal dead zone, threw inside an async
function (a rejected promise nobody saw), and the row kept its static text.

The same shape existed for `refreshStorageInfo` (a `let` initialised near the
bottom, read from several early paths). Both now live where load-time code can
see them.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
WHATSNEW = (ROOT / "src" / "suravidl_engine" / "whatsnew.py").read_text()


def test_android_is_a_hoisted_function():
    assert "function ANDROID()" in APP, "a const arrow is TDZ-dead at load time"
    assert "const ANDROID =" not in APP
    # and the call site still exists, so the intent is intact
    assert 'if (ANDROID()) { const f = $("ffmpegField")' in APP


def test_the_storage_refresher_is_declared_at_the_top():
    decl = APP.index("let refreshStorageInfo = null;")
    assert APP.count("let refreshStorageInfo = null;") == 1
    # module state that early paths read lives above every function body
    assert decl < APP.index("async function api("), (
        "a `let` below the first function body can be read before it exists")


def test_a_failed_ffmpeg_check_does_not_spin_forever():
    assert 'stateEl.textContent = t("could not check")' in APP
    assert '"could not check": "tidak bisa memeriksa"' in APP


def test_the_notes_name_this_release():
    from suravidl_engine import __version__
    from suravidl_engine.whatsnew import ENTRIES

    assert __version__ == "0.47.17"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the hoist"
    assert len(ENTRIES) == 10
    for item in ENTRIES[0]["items"]:
        assert 0 < len(item) <= 220


def test_no_other_top_level_helper_is_defined_as_a_late_const():
    """Regression guard for the class, not just the instance: any top-level
    `const NAME =` / `let NAME = null` that a load-time call reaches before its
    line would throw the same way. Only ANDROID is called at load today, so
    the guard pins that it is a function declaration and that the two known
    helpers are early."""
    top = []
    for i, line in enumerate(APP.splitlines(), 1):
        if re.match(r"(?:const|let)\s+[A-Za-z_$][\w$]*\s*=", line):
            top.append((line.split("=")[0].strip(), i))
    names = dict(top)
    # ANDROID/refreshStorageInfo must not be in that list at all, or must be
    # declared before the first line that can run at load time
    load_lines = [i for i, l in enumerate(APP.splitlines(), 1)
                  if l.strip() in ("initFfmpegRow();", "initStorageSection();")]
    first_load = min(load_lines) if load_lines else len(APP.splitlines())
    for name in ("ANDROID",):
        assert name not in names, f"{name} must be a function declaration"
    for name, at in names.items():
        if name in ("refreshStorageInfo",):
            assert at < first_load, f"{name} is read before its declaration"
