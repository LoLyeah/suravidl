"""v0.40.7 "the handful" — the extension hands several finds over at once,
and right-click reaches the engine without a trip through the toolbar.

The behavior itself lives in extension/test_harness.mjs (background + popup,
both browser flavors, fired with realistic requests); these pins tie the
release together: the harness actually gates CI now, every version string in
the extension agrees, each manifest carries the permission its browser
really has, and the store notes say what the new doors are.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_the_extension_harness():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "node extension/test_harness.mjs" in ci, \
        "the harness's assertions must gate the extension job, not just node --check"


def test_every_extension_version_string_agrees():
    m3 = json.loads((ROOT / "extension/manifest.json").read_text())
    m2 = json.loads((ROOT / "extension/firefox/manifest.json").read_text())
    html = (ROOT / "extension/popup.html").read_text()
    assert m3["version"] == m2["version"] == "0.5.12"
    assert "v0.5.12" in html


def test_each_manifest_gets_the_permission_its_browser_has():
    m3 = json.loads((ROOT / "extension/manifest.json").read_text())
    m2 = json.loads((ROOT / "extension/firefox/manifest.json").read_text())
    assert "contextMenus" in m3["permissions"]
    assert "menus" in m2["permissions"]
    assert "contextMenus" not in m2["permissions"], \
        "Firefox's name for it is menus; contextMenus is not a Firefox permission"


def test_the_store_notes_carry_the_new_doors():
    meta = (ROOT / "docs/amo-metadata.json").read_text()
    json.loads(meta)   # the submission must never ship invalid JSON
    assert "contextMenus" in meta, "the approval notes justify the new permission"
    assert "share links" in meta, "the release notes say what changed"
