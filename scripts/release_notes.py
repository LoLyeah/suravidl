#!/usr/bin/env python3
"""Release notes and a changelog for every tagged release.

The release workflow used GitHub's auto notes, which on this repo are a
compare link and nothing else — every release is a direct commit to main, not
a pull request. This script writes the page instead, in the shape the other
repos in this account use: the product line, "What's Changed" with every
commit since the previous tag on one of three shelves, the compare link, and
a table of the packages actually attached to the release.

    scripts/release_notes.py --tag v0.49.14 --out notes.md
    scripts/release_notes.py --all --out CHANGELOG.md

Both modes are read-only about git history: they ask git for tags, ranges and
messages, and write only the file they were told to write.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

DESCRIPTION = ("Local video downloader for Windows, macOS, Linux and Android — with a "
               "browser extension that hands it the page you are on.")

# The release pages follow the shape used by the other repos in this account:
# three shelves, every commit in the range, full links, and a package table.
SHELVES = [
    ("🚀", "Features & Improvements",
     {"feat", "feature", "perf", "improve", "ext", "sound", "handshake", "ui",
      "engine", "api", "web", "names", "wip", "cut", "player", "theme"}),
    ("🐛", "Bug Fixes", {"fix", "bugfix", "hotfix", "bug"}),
]
FALLBACK = ("🛠️", "Build, CI & Platform Packaging")

# name → (platform, format, description); order is the table's order
PACKAGES = [
    ("suravidl-windows-x64-setup.exe", "Windows", "Setup Installer",
     "Recommended installer (x64)"),
    ("suravidl-windows-x64.exe", "Windows", "Portable",
     "Single executable, no install"),
    ("suravidl-macos-arm64.dmg", "macOS", "DMG",
     "Apple silicon (M1 and later)"),
    ("suravidl-macos-arm64.zip", "macOS", "Zip",
     "Apple silicon, zipped app"),
    ("suravidl-linux-x64.AppImage", "Linux", "AppImage",
     "Portable Linux build (x86_64)"),
    ("app-release.apk", "Android", "Universal APK",
     "Signed APK for phones and tablets"),
    ("suravidl-extension-chrome.zip", "Chrome", "Extension",
     "Chrome Web Store package"),
    ("suravidl-extension-firefox.xpi", "Firefox", "Extension",
     "Signed add-on"),
]
SUBJECT_RE = re.compile(r"^(?P<kind>[a-z]+)(?:\((?P<scope>[^)]*)\))?!?:\s*(?P<text>.+)$")


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def version_key(tag: str):
    m = TAG_RE.match(tag)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def tags_newest_first() -> list[str]:
    tags = [t for t in git("tag", "-l", "v*").splitlines() if TAG_RE.match(t)]
    return sorted(tags, key=version_key, reverse=True)


def previous_tag(tag: str) -> str:
    ordered = list(reversed(tags_newest_first()))       # oldest first
    try:
        i = ordered.index(tag)
    except ValueError:
        return ""
    return ordered[i - 1] if i > 0 else ""


def tag_date(tag: str) -> str:
    return git("log", "-1", "--format=%cs", tag)


def repo_slug() -> str:
    """owner/repo from origin, so a release can link its own diff."""
    try:
        url = git("remote", "get-url", "origin")
    except SystemExit:
        return ""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def compare_url(prev: str, tag: str) -> str:
    slug = repo_slug()
    if not slug or not prev:
        return ""
    return f"https://github.com/{slug}/compare/{prev}...{tag}"


def extension_version(tag: str) -> str:
    try:
        data = git("show", f"{tag}:extension/manifest.json")
        return str(json.loads(data).get("version") or "")
    except (SystemExit, ValueError):
        return ""


def release_assets(tag: str) -> list[str] | None:
    """The file names on the published release, or None if gh cannot say."""
    out = subprocess.run(
        ["gh", "release", "view", tag, "--json", "assets", "--jq", ".assets[].name"],
        capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def release_detail(tag: str) -> str:
    """The body of the tag's own commit — the notes written at cut time.

    The subject is the release line (already in the heading), and the test
    count is bookkeeping; everything else is what actually shipped, which the
    in-app card compresses into four bullets.
    """
    try:
        message = git("log", "-1", "--format=%B", tag)
    except SystemExit:
        return ""
    lines = message.splitlines()[1:]          # drop the subject
    keep = []
    for line in lines:
        low = line.strip().lower()
        if low.startswith(("suite", "tests", "co-authored-by:", "signed-off-by:")):
            continue
        keep.append(line.rstrip())
    text = "\n".join(keep).strip()
    return text[:1800]


def commits_between(tag: str) -> list[tuple[str, str]]:
    prev = previous_tag(tag)
    span = f"{prev}..{tag}" if prev else tag
    raw = git("log", span, "--no-merges", "--format=%H%x1f%s", "--reverse")
    commits = []
    for line in raw.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        commits.append((sha, subject.strip()))
    return commits


def whatsnew_at(tag: str) -> tuple[str, str, list[str]]:
    """(version, title, items) for the release the tag carries, if it says."""
    try:
        source = git("show", f"{tag}:src/suravidl_engine/whatsnew.py")
    except SystemExit:
        return "", "", []
    # only the FIRST entry: each one is a release, and the ones below it
    # belong to older versions that shipped in earlier tags
    begin = source.find("ENTRIES = [")
    start = source.find('"version"', begin)
    end = source.find("\n    },", start)
    block = source[start:end if end > start else len(source)]
    m = re.search(r'"version":\s*"([^"]+)"', block)
    version = m.group(1) if m else ""
    tm = re.search(r'"title":\s*"([^"]+)"', block)
    title = tm.group(1) if tm else ""
    items = re.findall(r'^\s{12}"((?:[^"\\]|\\.)*)",\s*$', block, re.M)
    def unescape(text: str) -> str:
        text = text.replace('\\"', '"').replace("\\'", "'")
        return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return (version, unescape(title),
            [unescape(i) for i in items][:6])


def shelf_for(subject: str) -> tuple[str, str]:
    m = SUBJECT_RE.match(subject)
    kind = m["kind"] if m else ""
    # a release commit is the human summary of what shipped (every tag before
    # v0.49 had exactly one), so it shelves with the work, not with the build
    if kind == "release" or VERSION_SUBJECT.match(subject) or BARE_VERSION.match(subject):
        return SHELVES[0][:2]
    for emoji, name, kinds in SHELVES:
        if kind in kinds:
            return emoji, name
    return FALLBACK


VERSION_SUBJECT = re.compile(r'^v\d+\.\d+\.\d+(?:\s+"[^"]*")?\s*[—–-]\s*')
BARE_VERSION = re.compile(r'^v\d+\.\d+\.\d+(?:\s+"[^"]*")?\s*$')


def display_subject(subject: str) -> str:
    """How a commit reads on the page of the release that ships it.

    "wip(sound): ..." was true while it was being written, not afterwards;
    "release: v0.49.15 — ..." repeats the heading. Neither is worth the ink.
    """
    m = SUBJECT_RE.match(subject)
    if m:
        if m["kind"] == "wip" and m["scope"]:
            subject = f"{m['scope']}: {m['text']}"
        elif m["kind"] == "release":
            subject = m["text"]
    if BARE_VERSION.match(subject):
        return subject
    return VERSION_SUBJECT.sub("", subject)


def bullets(commits: list[tuple[str, str]]) -> list[str]:
    """Every commit in the range, one bullet, its shelf as an H4."""
    shells: dict[tuple[str, str], list[str]] = {}
    for sha, subject in commits:
        shelf = shelf_for(subject)
        subject = display_subject(subject)
        short = sha[:7]
        url = f"https://github.com/{repo_slug()}/commit/{sha}" if repo_slug() else ""
        link = f" ([{short}]({url}))" if url else f" ({short})"
        shells.setdefault(shelf, []).append(f"* {subject}{link}")
    out: list[str] = []
    for emoji, name, _ in SHELVES:
        if (emoji, name) in shells:
            out += [f"#### {emoji} {name}", ""]
            out += shells.pop((emoji, name))
            out.append("")
    if shells:                       # everything else, under the last shelf
        emoji, name = FALLBACK
        out += [f"#### {emoji} {name}", ""]
        for key, entries in shells.items():
            out += entries
        out.append("")
    return out


def package_table(assets: list[str] | None) -> list[str]:
    # No file list, no table: a release page must not promise a package it
    # cannot show. CI passes --assets-dir dist; the backfill reads the release.
    if not assets:
        return []
    rows = [p for p in PACKAGES if p[0] in assets]
    if not rows:
        return []
    out = [
        "### 📦 Download Packages",
        "",
        "| Platform | Format | Filename | Description |",
        "|:---|:---|:---|:---|",
    ]
    for name, platform, fmt, note in rows:
        out.append(f"| **{platform}** | {fmt} | `{name}` | {note} |")
    return out


def notes_for(tag: str, *, heading: int = 2,
              assets: list[str] | None = None) -> str:
    """One release page, in the shape the other repos in this account use.

        ## 🚀 suravidl v0.49.15 — The handshake

        <one line about what this product is>

        ### 📄 What's Changed

        #### 🚀 Features & Improvements
        * subject ([sha7](commit url))

        #### 🐛 Bug Fixes
        #### 🛠️ Build, CI & Platform Packaging

        **Full Changelog**: <compare url>

        ### 📦 Download Packages
        | Platform | Format | Filename | Description |
    """
    version, title, _ = whatsnew_at(tag)
    name = f"🚀 suravidl {version or tag.lstrip('v')}"
    if title:
        name += f" — {title}"
    lines = ["#" * heading + f" {name}", "", DESCRIPTION, ""]
    lines += ["#" * (heading + 1) + " 📄 What's Changed", ""]
    commits = commits_between(tag)
    lines += bullets(commits) if commits else ["_No commits recorded._", ""]
    link = compare_url(previous_tag(tag), tag)
    if link:
        lines += [f"**Full Changelog**: {link}", ""]
    table = package_table(assets)
    if table:
        lines += table
    return "\n".join(lines).rstrip() + "\n"


def changelog() -> str:
    tags = tags_newest_first()
    lines = [
        "# Changelog",
        "",
        "Every tagged release, newest first.",
        "Generated by `scripts/release_notes.py` from the tags and their commits",
        "— do not edit by hand.",
        "",
    ]
    if not tags:
        return "\n".join(lines) + "_No tags yet._\n"
    slug = repo_slug()
    for tag in tags:
        version, title, _ = whatsnew_at(tag)
        name = f"v{version or tag.lstrip('v')}"
        if title:
            name += f" — {title}"
        lines.append(f"## [{name}](https://github.com/{slug}/releases/tag/{tag})"
                     f" — {tag_date(tag)}")
        lines.append("")
        entries = bullets(commits_between(tag))
        lines.append("\n".join(entries).strip() or "_No commits recorded._")
        link = compare_url(previous_tag(tag), tag)
        if link:
            lines += ["", f"**Full Changelog**: {link}"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", help="write the notes for one tag")
    ap.add_argument("--all", action="store_true", help="write the whole changelog")
    ap.add_argument("--out", default="-", help="file to write, or - for stdout")
    ap.add_argument("--assets-dir", help="directory of release files (CI: dist)")
    ap.add_argument("--assets-from-release", action="store_true",
                    help="read the file names off the published release (gh)")
    args = ap.parse_args()

    assets: list[str] | None = None
    if args.assets_dir:
        assets = sorted(p.name for p in Path(args.assets_dir).iterdir() if p.is_file())
    elif args.assets_from_release and args.tag:
        assets = release_assets(args.tag)
        if assets is None:
            print("could not read the release's assets; writing without a table",
                  file=sys.stderr)
            assets = []

    if args.all:
        text = changelog()
    elif args.tag:
        known = git("tag", "-l", args.tag).strip()
        if not known:
            print(f"no such tag: {args.tag}", file=sys.stderr)
            return 2
        text = notes_for(args.tag, assets=assets)
    else:
        ap.error("one of --tag or --all is required")

    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{args.out}: {len(text)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
