"""v0.32.0 — the one-time "What's new" card after an update.

The engine owns the notes (`whatsnew.ENTRIES`, `GET /whats-new`); the web UI
shows the entries newer than the version THIS device last saw, once — and it
waits for "Got it", so until then the next launch asks again. A fresh install
shows nothing (there was no update to explain). The selection rule is RUN in
Node against the real functions, so the mirror cannot drift.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine import __version__
from suravidl_engine import whatsnew

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
AUTH = {"Authorization": "Bearer testtoken"}


@pytest.fixture()
def client(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path, auth_token="testtoken")
    with TestClient(app) as c:
        yield c


def _fn(name, end_marker):
    """The source of a function: from its declaration to `end_marker`."""
    assert name in APP, f"{name} is missing"
    return APP.split(name, 1)[1].split(end_marker, 1)[0]


# -- the engine owns the notes ------------------------------------------------

def test_the_notes_start_with_the_current_version():
    """The card is only as honest as this list — bumping the version without
    shipping notes must fail right here."""
    assert whatsnew.ENTRIES, "no notes at all"
    assert whatsnew.ENTRIES[0]["version"] == __version__


def test_every_entry_is_shaped_and_newest_first():
    def tup(v):
        return tuple(int(x) if x.isdigit() else 0 for x in str(v).split("."))

    versions = [e["version"] for e in whatsnew.ENTRIES]
    assert versions == sorted(versions, key=tup, reverse=True), "newest first"
    for e in whatsnew.ENTRIES:
        assert e["title"], e["version"]
        assert e["items"], "an entry without items is not worth a card"
        for item in e["items"]:
            assert item and len(item) <= 220, "one line per thought"
    assert len(whatsnew.ENTRIES) <= 10, "keep the list recent — 3 are shown"


def test_the_endpoint_is_auth_gated_and_speaks_the_engine_version(client):
    assert client.get("/whats-new").status_code == 401
    r = client.get("/whats-new", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == __version__
    assert body["entries"][0]["version"] == __version__


# -- the shell: one card per device, waiting for "Got it" ---------------------

def test_the_card_exists_with_the_house_shape():
    assert 'id="whatsNewModal"' in HTML and 'class="overlay hidden"' in HTML
    assert 'aria-labelledby="whatsNewTitle"' in HTML
    for elem in ("whatsNewTitle", "whatsNewList", "whatsNewClose",
                 "whatsNewDone"):
        assert f'id="{elem}"' in HTML, elem
    # the way back in, for anyone who dismissed it in a hurry
    assert 'id="wnOpen"' in HTML


def test_a_first_launch_gets_the_current_release_and_later_ones_whats_new():
    assert '"suravidl.whatsnew.seen"' in APP
    assert "MAX: 3," in APP, "one update explains at most three releases"
    maybe = _fn("async function maybeShowWhatsNew",
                "\nasync function openWhatsNew")
    assert 'await api("/whats-new")' in maybe
    assert 'const seen = updStore.get(WN.seen, "");' in maybe
    assert "const pick = seen ? whatsNewFor(seen, data.entries)" in maybe
    assert ": (data.entries || []).slice(0, 1);" in maybe, \
        "a device that never saw a card gets the current release's notes"
    assert "if (!pick.length) { updStore.set(WN.seen, data.version); return; }" in maybe
    assert "showWhatsNew(pick, data.version);" in maybe


def test_the_card_waits_for_got_it():
    dismiss = _fn("function dismissWhatsNew", "\n\n")
    assert "if (version) updStore.set(WN.seen, version);" in dismiss
    assert '$("whatsNewModal").classList.add("hidden");' in dismiss
    show = _fn("function showWhatsNew", "\n\n/** Record on dismiss")
    assert '$("whatsNewDone").onclick = () => dismissWhatsNew(version);' in show
    assert '$("whatsNewClose").onclick = () => dismissWhatsNew(version);' in show
    assert '$("whatsNewModal").classList.remove("hidden");' in show


def test_settings_can_reopen_this_versions_notes():
    assert "wireWhatsNewRow();" in APP and "maybeShowWhatsNew();" in APP, \
        "both the row and the boot card must be wired"
    open_fn = _fn("async function openWhatsNew", "\n\nfunction wireWhatsNewRow")
    assert ".filter((e) => e && e.version === data.version);" in open_fn


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_selection_rule_runs(tmp_path):
    """Execute the REAL functions from app.js in Node: which entries a device
    coming from a given version sees."""
    js = ("const WN = {" + _fn("const WN = {", "\n};") + "\n};\n"
          "function versionTuple" + _fn("function versionTuple", "\n/** a > b")
          + "\nfunction versionCmp" + _fn("function versionCmp", "\n/** The entries")
          + "\nfunction whatsNewFor" + _fn("function whatsNewFor",
                                           "\nfunction showWhatsNew"))
    harness = tmp_path / "wn.js"
    harness.write_text(js + """
const E = [
  {version: "0.32.0"}, {version: "0.31.0"},
  {version: "0.30.0"}, {version: "0.29.0"},
];
const picks = ["0.30.0", "0.26.0", "0.32.0", "9.9.9", "junk", "0.31.9"]
  .map((seen) => whatsNewFor(seen, E).map((e) => e.version));
console.log(JSON.stringify(picks));
""")
    out = subprocess.run(["node", str(harness)], capture_output=True, text=True,
                         timeout=30, check=True)
    got = json.loads(out.stdout)
    assert got[0] == ["0.32.0", "0.31.0"], "entries newer than the seen version"
    assert got[1] == ["0.32.0", "0.31.0", "0.30.0"], "capped at three"
    assert got[2] == [] and got[3] == [], "seen = current (or older): nothing"
    assert got[4] == ["0.32.0", "0.31.0", "0.30.0"], "junk floors below everything"
    assert got[5] == ["0.32.0"], "0.31.9 < 0.32.0 — numeric, not string order"
