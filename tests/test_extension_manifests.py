"""The two extension manifests, and the AMO contract they feed.

Both browsers ship one extension from one source tree, and the only real
difference is the manifest — so nothing else notices a version bumped in one and
forgotten in the other (0.5.1 vs 0.5.2, found while preparing the AMO listing).
The store side is pinned against the vendor's own rules rather than my memory of
them: a first listing is rejected outright when `categories`, `summary` or the
version's `license` are missing, and the valid slugs come from addons-server's
constants (categories.py, licenses.py).
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
EXT = ROOT / "extension"
CHROME = json.loads((EXT / "manifest.json").read_text())
FIREFOX = json.loads((EXT / "firefox/manifest.json").read_text())
AMO = json.loads((ROOT / "docs/amo-metadata.json").read_text())
GECKO = FIREFOX["browser_specific_settings"]["gecko"]

# addons-server: src/olympia/constants/categories.py, ADDON_EXTENSION
AMO_CATEGORIES = {
    "alerts-updates", "appearance", "bookmarks", "download-management",
    "feeds-news-blogging", "games-entertainment", "language-support",
    "photos-music-videos", "privacy-security", "search-tools", "shopping",
    "social-communication", "tabs", "web-development", "other",
}
# addons-server: src/olympia/constants/licenses.py (the SPDX slugs)
AMO_LICENSES = {
    "MPL-2.0", "Apache-2.0", "GPL-2.0-only", "GPL-3.0-only", "LGPL-2.1-only",
    "LGPL-3.0-only", "AGPL-3.0-only", "MIT", "ISC", "BSD-2-Clause", "MPL-1.1",
    "Unlicense", "all-rights-reserved",
}


def test_both_manifests_carry_the_same_version():
    """One source tree, two packages: a version bumped in one manifest only is
    how a store ends up serving a build older than the release."""
    assert CHROME["version"] == FIREFOX["version"], (
        f"chrome {CHROME['version']} vs firefox {FIREFOX['version']}")


def test_firefox_stays_mv2_and_chrome_mv3():
    """Mozilla still supports MV2 alongside MV3 and says developers are not
    required to move; the Firefox package is the MV2 manifest, and a stable
    Firefox only installs it with the ID AMO knows."""
    assert FIREFOX["manifest_version"] == 2
    assert CHROME["manifest_version"] == 3
    assert GECKO["id"] == "suravidl@fritzkier.com", \
        "the add-on ID is permanent once listed — never retype it"


def test_the_firefox_floor_matches_the_data_collection_declaration():
    """`data_collection_permissions` reached Firefox 140 (142 on Android) and
    AMO requires the declaration for new submissions. A floor below that makes
    Mozilla's linter warn and lets installs that predate the key skip the
    disclosure entirely — so the floor has to be at least 140."""
    assert GECKO["data_collection_permissions"]["required"] == ["none"]
    assert int(GECKO["strict_min_version"].split(".")[0]) >= 140


def test_the_amo_metadata_has_what_a_first_listing_requires():
    """Mozilla's rule, from the web-ext docs: on a first listed version,
    `categories`, `summary` and the version's `license` must be provided, and
    translated fields must carry at least one locale."""
    assert AMO["categories"], "categories are required"
    assert set(AMO["categories"]) <= AMO_CATEGORIES, "unknown category slug"
    assert AMO["summary"].get("en-US")
    assert AMO["description"].get("en-US")
    assert AMO["version"]["license"] in AMO_LICENSES, "unknown licence slug"
    assert AMO["version"]["compatibility"] == ["firefox"], \
        "desktop Firefox only: Android Firefox has not been tested"
    assert AMO["version"]["approval_notes"], \
        "reviewers need to know how to test a local-engine companion"
    assert AMO["privacy_policy"]["en-US"].startswith("https://")


def test_the_listing_fields_have_the_shape_amo_asks_for():
    """AMO answers 400 when a translated field arrives as a plain string —
    "You must provide an object of {lang-code:value}". homepage and support_url
    were strings on the first submission and it was refused; the rest of the
    translated fields were already right, which is why the error named only
    those two."""
    for field in ("summary", "description", "homepage", "support_url",
                  "privacy_policy"):
        value = AMO[field]
        assert isinstance(value, dict), f"{field} must be {{lang: value}}"
        assert value.get("en-US"), f"{field} needs at least one locale"
    for field in ("license", "approval_notes"):
        assert isinstance(AMO["version"][field], str), f"{field} is plain text"
    assert all(isinstance(c, str) for c in AMO["categories"])


def test_the_submitted_package_leaves_out_development_files():
    """The shop window is not the workshop: the test harness and the other
    browser's manifest have no business inside a submitted package."""
    release = (ROOT / ".github/workflows/release.yml").read_text()
    assert "rm -rf /tmp/ffext/firefox /tmp/ffext/test_harness.mjs" in release
    assert '-x "test_harness.mjs"' in release
    amo = (ROOT / ".github/workflows/amo.yml").read_text()
    assert "rm -rf /tmp/ffext/firefox /tmp/ffext/test_harness.mjs" in amo


def test_the_amo_submission_reads_the_secrets_and_says_nothing_about_them():
    """The workflow must take the API credentials from repository secrets (a
    JWT secret has no business in a log), submit a *listed* version with the
    metadata file, and refuse to invent success when the credentials are
    missing."""
    amo = (ROOT / ".github/workflows/amo.yml").read_text()
    assert "${{ secrets.AMO_JWT_ISSUER }}" in amo
    assert "${{ secrets.AMO_JWT_SECRET }}" in amo
    assert "--channel listed" in amo
    assert "--amo-metadata docs/amo-metadata.json" in amo
    assert "if: env.AMO_JWT_ISSUER != ''" in amo
    # the credentials are never echoed
    assert 'echo "$AMO_JWT_SECRET"' not in amo
    assert "echo $AMO_JWT_SECRET" not in amo
