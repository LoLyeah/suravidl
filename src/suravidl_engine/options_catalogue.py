"""yt-dlp's real option surface, generated from the installed parser.

Never hand-maintained: the catalogue is built from ``create_parser()`` so it
is complete by construction and cannot drift from the installed version.
"""
from __future__ import annotations

from yt_dlp.options import create_parser

# yt-dlp marks switches it no longer wants to advertise with this sentinel
# (deprecated flags: --call-home, --include-ads, --write-annotations, …).
# Its own --help hides them; a catalogue that prints "SUPPRESSHELP" as the
# description does not (v0.49.7).
_HELP_HIDDEN = "SUPPRESSHELP"


def build_catalogue() -> list[dict]:
    """Every long option, grouped the way yt-dlp's own CLI groups them."""
    parser = create_parser()
    groups = [("General", parser)]
    groups += [(g.title or "Other", g) for g in parser.option_groups]

    entries: list[dict] = []
    for title, group in groups:
        for opt in list(getattr(group, "option_list", None) or []):
            longs = [s for s in opt._long_opts if s.startswith("--")]
            if not longs:
                continue
            help_text = " ".join((opt.help or "").split())
            if help_text == _HELP_HIDDEN:
                continue
            entries.append({
                "group": title,
                "name": longs[0],
                "flags": sorted(set(opt._long_opts) | set(opt._short_opts)),
                "metavar": opt.metavar,
                "takes_value": bool(opt.takes_value()),
                "help": help_text,
            })
    entries.sort(key=lambda e: (e["group"], e["name"]))
    return entries
