#!/usr/bin/env python3
"""Release notes and a changelog for every tagged release.

The release workflow used GitHub's auto notes, which on this repo are a
compare link and nothing else — every release is a direct commit to main, not
a pull request. This script writes the notes a person can read: the release's
own "what's new" entry (the same text the app shows after an update) followed
by the commits that landed since the previous tag, grouped by kind.

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

# Conventional-commit prefixes, in the order the notes read them. `release:`
# is the commit that changes the version; it is the tag's own message, so it
# is not a "change" to report.
GROUPS = [
    ("Features", ("feat", "feature")),
    ("Fixes", ("fix", "bugfix", "hotfix")),
    ("Performance", ("perf",)),
    ("Docs", ("docs", "doc")),
    ("Build & CI", ("build", "ci", "chore", "test", "tests")),
    ("Other", ()),
]
SKIP = {"release", "changelog"}
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
    raw = git("log", span, "--no-merges", "--format=%h%x1f%s", "--reverse")
    kept, dropped = [], []
    for line in raw.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        subject = subject.strip()
        # the release workflow's own bookkeeping commits are not this release
        if subject.lower().startswith("docs: changelog for"):
            continue
        m = SUBJECT_RE.match(subject)
        # a release commit is the tag's own message, not a change — unless it
        # is the ONLY thing between two tags (a one-commit cut), in which case
        # "no commits" would be a lie
        # a release commit is the tag's own message, not a change: the notes
        # above already say what shipped
        (dropped if m and m["kind"] in SKIP else kept).append((sha, subject))
    return kept


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


def group_for(kind: str) -> str:
    for name, kinds in GROUPS:
        if kind in kinds:
            return name
    return "Other" if kind else "Other"


def group_lines(commits: list[tuple[str, str]]) -> list[str]:
    """Conventional-commit subjects under their headings, sha included."""
    buckets: dict[str, list[str]] = {}
    for sha, subject in commits:
        m = SUBJECT_RE.match(subject)
        kind = m["kind"] if m else ""
        text = m["text"] if m else subject
        scope = m["scope"] if m else None
        shown = f"{scope}: {text}" if scope else text
        buckets.setdefault(group_for(kind), []).append(f"- {shown} (`{sha}`)")
    out: list[str] = []
    for name, _ in GROUPS:
        if name in buckets:
            out.append(f"**{name}**")
            out += buckets.pop(name)
            out.append("")
    for name, entries in buckets.items():      # a kind nobody listed
        out.append(f"**{name}**")
        out += entries
        out.append("")
    return out


def notes_for(tag: str, *, with_commits: bool = True, heading: int = 1,
              detail: bool = True) -> str:
    """One release page: what it is, when, its highlights, and its detail.

    `detail` carries the tag's own commit message — the notes written at cut
    time — which is what makes a release page read like a release page and not
    like four bullets. The changelog skips it: ten lines per tag, not a book.
    """
    version, title, items = whatsnew_at(tag)
    name = f"suravidl {version or tag.lstrip('v')}"
    if title:
        name += f" — {title}"
    lines = ["#" * heading + f" {name}", ""]
    meta = [tag_date(tag)]
    ext = extension_version(tag)
    if ext:
        meta.append(f"extension {ext}")
    link = compare_url(previous_tag(tag), tag)
    if link:
        meta.append(f"[compare]({link})")
    lines += [" · ".join(meta), ""]
    if items:
        lines += ["#" * (heading + 1) + " Highlights", ""]
        lines += [f"- {item}" for item in items] + [""]
    if detail:
        body = release_detail(tag)
        # The release commit is written from the same work the card summarises;
        # printing both verbatim says everything twice. Keep it only when it
        # adds something the highlights do not (a specific cause, a caveat).
        if items:
            words = lambda text: {w.lower().strip(".,;:()—–-\"") for w in text.split()
                                  if len(w) > 3}
            have, want = words(body), words(" ".join(items))
            if want and len(have & want) / len(want) > 0.45:
                body = ""
        if body:
            lines += ["#" * (heading + 1) + " What changed", "", body, ""]
    if not with_commits:
        return "\n".join(lines).rstrip() + "\n"
    commits = commits_between(tag)
    if not commits:
        return "\n".join(lines).rstrip() + "\n"
    lines.append("#" * (heading + 1) + f" Commits ({len(commits)})")
    lines.append("")
    lines += group_lines(commits)
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
    for tag in tags:
        lines.append(f"## [{tag}](https://github.com/{repo_slug()}/releases/tag/{tag})"
                     f" — {tag_date(tag)}")
        lines.append("")
        # drop the heading and the meta line (the H2 above already carries
        # the tag, the date and the link); keep the content
        parts = notes_for(tag, heading=3, detail=False).split("\n\n")
        lines.append("\n\n".join(parts[2:]).strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", help="write the notes for one tag")
    ap.add_argument("--all", action="store_true", help="write the whole changelog")
    ap.add_argument("--out", default="-", help="file to write, or - for stdout")
    args = ap.parse_args()

    if args.all:
        text = changelog()
    elif args.tag:
        known = git("tag", "-l", args.tag).strip()
        if not known:
            print(f"no such tag: {args.tag}", file=sys.stderr)
            return 2
        text = notes_for(args.tag)
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
