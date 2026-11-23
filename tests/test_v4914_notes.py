"""The release notes script (v0.49.14, reshaped in v0.49.16).

GitHub's auto notes for this repo are a compare link: every release is a
direct commit to main, so there are no pull requests to list. These checks run
the script against the real history — it reads tags and commits, nothing else.

The page follows the shape used by the other repos in this account:

    ## 🚀 suravidl v0.49.15 — The handshake

    <one line about the product>

    ### 📄 What's Changed

    #### 🚀 Features & Improvements
    * subject ([sha](commit url))

    **Full Changelog**: <compare url>

    ### 📦 Download Packages
    | Platform | Format | Filename | Description |
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_notes.py"


def run(*args: str) -> str:
    out = subprocess.run([sys.executable, str(SCRIPT), *args],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def tags() -> list[str]:
    out = subprocess.run(["git", "tag", "-l", "v*"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [t for t in out.split() if t.count(".") == 2]


def test_the_script_is_executable_and_has_a_usage():
    assert SCRIPT.exists()
    out = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode != 0
    assert "--tag" in out.stderr and "--all" in out.stderr


def test_one_release_reads_like_a_release_page():
    text = run("--tag", "v0.46.17")
    assert text.startswith("## suravidl 0.46.17 — The namesake")
    assert "### What's Changed" in text
    assert "**Full Changelog**: https://github.com/LoLyeah/suravidl/compare/" in text
    # one of the three shelves, as the reference pages use
    assert "#### Features & Improvements" in text \
        or "#### Bug Fixes" in text \
        or "#### Build, CI & Platform Packaging" in text


def test_every_commit_is_a_bullet_with_its_own_link():
    text = run("--tag", "v0.49.15")
    assert ("* handshake: the two halves say what they are; a support block; "
            "a disk floor ([849fbbb](https://github.com/LoLyeah/suravidl/commit/849fbbb") in text
    # a work-in-progress commit reads as its scope, not as "wip", on a page
    # that ships it
    assert "wip(" not in text


def test_the_download_table_matches_the_files(tmp_path):
    for name in ("suravidl-macos-arm64.dmg", "notes.txt"):
        (tmp_path / name).write_text("x")
    text = run("--tag", "v0.49.15", "--assets-dir", str(tmp_path))
    assert "### Download Packages" in text
    assert "| **macOS** | DMG | `suravidl-macos-arm64.dmg` |" in text
    assert "notes.txt" not in text          # only known packages are rows


def test_no_table_without_files():
    text = run("--tag", "v0.49.15")
    assert "### Download Packages" not in text


def test_only_the_tags_own_whats_new_entry_is_used():
    """The first bug this script had: it read every entry in the file."""
    text = run("--tag", "v0.49.13")
    assert "The take" in text
    # 0.49.12's notes belong to another release and must not appear here
    assert "File name length choice" not in text


def test_a_single_commit_cut_still_lists_that_commit():
    text = run("--tag", "v0.49.13")
    # the version is in the heading; the bullet is what the commit did
    assert "* the play sheet on a phone ([9f1ae9d]" in text
    assert "release: v0.49.13" not in text


def test_an_unknown_tag_is_refused():
    out = subprocess.run([sys.executable, str(SCRIPT), "--tag", "v9.9.9"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 2
    assert "no such tag" in out.stderr


def test_the_changelog_holds_every_tag_newest_first(tmp_path):
    dest = tmp_path / "CHANGELOG.md"
    run("--all", "--out", str(dest))
    text = dest.read_text()
    assert text.startswith("# Changelog")
    headings = [line for line in text.splitlines() if line.startswith("## [v")]
    known = tags()
    assert len(headings) == len(known)
    # newest first, by version not by string: 0.49.9 < 0.49.10
    newest = sorted(known, key=lambda t: tuple(int(x) for x in t.lstrip("v").split(".")),
                    reverse=True)[0]
    assert headings[0].startswith("## [v0.49.15")
