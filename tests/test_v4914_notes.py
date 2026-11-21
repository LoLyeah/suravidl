"""The release notes script (v0.49.14).

GitHub's auto notes for this repo are a compare link: every release is a
direct commit to main, so there are no pull requests to list. These checks run
the script against the real history — it reads tags and commits, nothing else.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

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


def test_one_release_names_itself_and_its_changes():
    text = run("--tag", "v0.46.17")
    assert text.startswith("# suravidl 0.46.17 — The namesake")
    assert "- Two different videos could end up under one filename" in text
    assert "### Changes" in text
    assert "**Fixes**" in text or "**Features**" in text


def test_only_the_tags_own_whats_new_entry_is_used():
    """The first bug this script had: it read every entry in the file."""
    text = run("--tag", "v0.49.13")
    assert "The take" in text
    # 0.49.12's notes belong to another release and must not appear here
    assert "File name length choice" not in text


def test_a_release_commit_is_not_listed_as_a_change():
    text = run("--tag", "v0.49.13")
    assert "### Changes" not in text     # a one-commit cut: notes only


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
    headings = [line for line in text.splitlines() if line.startswith("## v")]
    known = tags()
    assert len(headings) == len(known)
    # newest first, by version not by string: 0.49.9 < 0.49.10
    assert headings[0].split()[1] == sorted(
        known, key=lambda t: tuple(int(x) for x in t.lstrip("v").split(".")),
        reverse=True)[0]
