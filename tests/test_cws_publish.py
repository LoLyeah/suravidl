"""The store submission path, minus the network.

The script is the only thing allowed to talk to the Web Store, and its two
dangerous mistakes are: uploading a version the store already has (the store
answers with an error that reads like a network fault), and uploading a zip
without a manifest at the root (the store rejects it after a long wait).
"""
import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cws_publish as cws  # noqa: E402

SCRIPT = (ROOT / "scripts" / "cws_publish.py").read_text()
WORKFLOW = (ROOT / ".github" / "workflows" / "extension-publish.yml").read_text()


def test_the_endpoints_are_the_v2_publisher_ones():
    assert cws.API == "https://chromewebstore.googleapis.com"
    assert cws.UPLOAD == "https://chromewebstore.googleapis.com/upload/v2"
    assert cws.SCOPE.endswith("/auth/chromewebstore")
    assert 'f"{API}/v2/{name_of(cfg)}:fetchStatus"' in SCRIPT
    assert 'f"{API}/v2/{name_of(cfg)}:publish"' in SCRIPT
    assert 'f"{UPLOAD}/{name_of(cfg)}:upload"' in SCRIPT
    assert 'f"publishers/{cfg[\'publisher_id\']}/items/{cfg[\'item_id\']}"' in SCRIPT


def test_the_zip_looks_like_an_extension(tmp_path):
    out = cws.build_zip(tmp_path / "ext.zip")
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        manifest = json.loads(z.read("manifest.json"))
    assert "manifest.json" in names
    assert not any(n.startswith("firefox/") for n in names)
    assert "test_harness.mjs" not in names
    assert manifest["version"] == cws.version_in_zip(out)


def test_a_published_version_is_refused_not_uploaded():
    info = {"publishedItemRevisionStatus": {"distributionChannels": [
        {"crxVersion": "0.5.19", "deployPercentage": 100}]}}
    assert cws.published_versions(info) == {"0.5.19"}
    assert "already on the store" in SCRIPT
    assert "return 2" in SCRIPT


def test_the_bump_raises_the_manifest_and_nothing_else(tmp_path, monkeypatch):
    ext = tmp_path / "extension"
    ext.mkdir()
    (ext / "manifest.json").write_text(json.dumps(
        {"manifest_version": 3, "name": "x", "version": "0.5.19",
         "action": {"default_popup": "options.html"}}, indent=2) + "\n")
    monkeypatch.setattr(cws, "EXT", ext)
    assert cws.bump_manifest("patch") == "0.5.20"
    data = json.loads((ext / "manifest.json").read_text())
    assert data["version"] == "0.5.20"
    assert data["action"] == {"default_popup": "options.html"}
    assert cws.bump_manifest("minor") == "0.6.0"


def test_the_workflow_skips_without_secrets_and_ships_the_release_zip():
    assert "CWS_REFRESH_TOKEN" in WORKFLOW
    assert "skipping the store submission" in WORKFLOW
    assert "suravidl-extension-chrome.zip" in WORKFLOW
    assert "workflow_dispatch" in WORKFLOW and "release:" in WORKFLOW
    # never echo a secret
    assert "echo $CWS_REFRESH_TOKEN" not in WORKFLOW


def test_the_docs_say_where_the_five_values_come_from():
    doc = (ROOT / "docs" / "CWS-PUBLISH.md").read_text()
    for needle in ("oauthplayground", "Publisher ID", "chmod 600",
                   "expire after 7 days", "Publish app"):
        assert needle in doc, needle
