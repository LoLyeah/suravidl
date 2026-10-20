"""v0.46.19 "the knock" — the relaunched app comes to the FRONT.

Field reports (2026-10-14): after an update the app "refused to install
and restart" — the swap landed but nothing came back until the user
clicked the icon — and a freshly opened window "can't click anything"
until an app switch. One mechanism: an app launched by the background
swap script gets no LaunchServices activation, and since macOS 14 it
cannot always activate itself; until something activates it, the window
sits behind everything and clicks land dead.

The fix knocks on both sides of the glass: the script asks
LaunchServices to raise the fresh instance (a plain `open` after the
`open -n` — skipped when a stale registration was left alive), and the
app activates itself the sanctioned way, orders its window front
regardless, and hands the web view first responder.
"""
import os
import subprocess
import zipfile
from pathlib import Path

from suravidl_engine import whatsnew

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "suravidl_engine"
SWAP = SRC / "macos_swap.sh"
MAIN = (SRC / "__main__.py").read_text()


# --- the script side: the knock ---------------------------------------------


def test_the_script_asks_launchservices_to_raise_the_fresh_instance():
    s = SWAP.read_text()
    assert s.count('knock "$1"') == 2, \
        "both LaunchServices paths raise the window (v0.46.19)"
    assert "activation requested" in s, "the attempt leaves a trace"
    assert "sleep 1" in s, "a fresh instance needs a breath to register"


def test_a_stale_registration_is_never_raised():
    s = SWAP.read_text()
    assert "LEFT_BEHIND=1" in s, "the reap section marks a left-alive pid"
    assert "activation skipped" in s, "open would land on the stale one"
    assert 'if [ -z "$LEFT_BEHIND" ] && open "$1"' in s, \
        "the plain-open middle rung is gated too"


def test_the_exec_fallback_does_not_knock():
    s = SWAP.read_text()
    assert "no activation" in s, \
        "a directly-spawned process never registered with LaunchServices; " \
        "an open here would launch a SECOND instance instead of raising it"


# --- the script side: live runs with shims -----------------------------------


def _shim_bin(tmp_path):
    """ditto/xattr/open stand-ins so the swap + relaunch run on any POSIX box."""
    d = tmp_path / "shimbin"
    d.mkdir()
    ditto = d / "ditto"
    ditto.write_text(
        '#!/bin/bash\n'
        'if [ "$1" = "-x" ]; then exec python3 -c '
        '"import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" '
        '"$3" "$4"; fi\n'
        'exit 0\n')
    ditto.chmod(0o755)
    xattr = d / "xattr"
    xattr.write_text("#!/bin/bash\nexit 0\n")
    xattr.chmod(0o755)
    op = d / "open"
    op.write_text(
        '#!/bin/bash\n'
        # printf, not echo: a leading "-n" is echo's own flag, not an arg
        'printf "%s\\n" "$*" >> "${OPEN_LOG:?}"\n'
        'if [ "$1" = "-n" ] && [ -n "${OPEN_REFUSE_N:-}" ]; then exit 1; fi\n'
        'exit 0\n')
    op.chmod(0o755)
    return d


def _fixture(tmp_path):
    installed = tmp_path / "installed" / "suravidl.app"
    (installed / "Contents").mkdir(parents=True)
    (installed / "Contents" / "OLD").write_text("old")
    z = tmp_path / "update.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("suravidl.app/Contents/NEW", "new")
    return installed, z


def _run_swap(tmp_path, installed, z, pid, extra_env=None):
    shimbin = _shim_bin(tmp_path)
    open_log = tmp_path / "open.log"
    upd_log = tmp_path / "update.log"
    env = dict(os.environ, PATH=f"{shimbin}:{os.environ['PATH']}",
               OPEN_LOG=str(open_log), SURAVIDL_UPDATE_LOG=str(upd_log),
               SURAVIDL_APPLY_WAIT_TICKS="2")
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["bash", str(SWAP), "suravidl-apply",
                        str(installed), str(z), str(pid)],
                       capture_output=True, text=True, env=env, timeout=120)
    lines = open_log.read_text().splitlines() if open_log.exists() else []
    return r, lines, upd_log.read_text() if upd_log.exists() else ""


def test_the_knock_follows_the_open_n(tmp_path):
    installed, z = _fixture(tmp_path)
    r, calls, log = _run_swap(tmp_path, installed, z, 999999)
    assert r.returncode == 0, r.stderr
    assert calls == [f"-n {installed}", str(installed)], \
        "open -n to launch fresh, then a plain open to raise it"
    assert "relaunch: open -n ok" in log
    assert "activation requested" in log
    assert (installed / "Contents" / "NEW").exists(), "the swap landed"
    assert not z.exists(), "the spent carrier is gone"


def test_a_plain_open_takes_over_when_open_n_is_refused(tmp_path):
    installed, z = _fixture(tmp_path)
    r, calls, log = _run_swap(tmp_path, installed, z, 999999,
                              extra_env={"OPEN_REFUSE_N": "1"})
    assert r.returncode == 0, r.stderr
    assert calls == [f"-n {installed}", str(installed), str(installed)], \
        "the middle rung launches through LaunchServices, then knocks"
    assert "plain open ok" in log and "activation requested" in log


def test_a_left_alive_pid_silences_the_knock(tmp_path):
    """A live stale registration must not be raised: open could land on
    the window-less old process and the user sees nothing come back."""
    stale = subprocess.Popen(["sleep", "60"])
    try:
        installed, z = _fixture(tmp_path)
        r, calls, log = _run_swap(tmp_path, installed, z, stale.pid)
        assert r.returncode == 0, r.stderr
        assert calls == [f"-n {installed}"], \
            "no plain open while a stale registration is alive"
        assert "activation skipped" in log
        assert stale.poll() is None, "the stranger pid must not be killed"
        assert (installed / "Contents" / "NEW").exists(), "the swap landed"
    finally:
        stale.kill()
        stale.wait()


# --- the app side: the knock from inside -------------------------------------


def test_the_app_knocks_on_its_own_window():
    assert "def _ensure_activated" in MAIN
    assert "activateWithOptions_" in MAIN, "the sanctioned macOS 14+ API"
    assert "NSApplicationActivateAllWindows" in MAIN
    assert "activateIgnoringOtherApps_" in MAIN, "the older systems stay covered"
    assert "orderFrontRegardless" in MAIN, "visible even if activation is denied"
    assert "makeFirstResponder_" in MAIN, \
        "the classic cure for a WKWebView that ignores clicks"


def test_the_knock_is_wired_at_startup_and_one_shot():
    assert MAIN.count("_ensure_activated(window)") >= 2, \
        "GUI-start and the first landed page both try"
    assert "_KNOCKED" in MAIN, "a later reload must not steal focus"


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # 0.46.19 "the knock" retired out of the rolling ten in v0.47.9
    assert "The knock" not in [e["title"] for e in whatsnew.ENTRIES]
