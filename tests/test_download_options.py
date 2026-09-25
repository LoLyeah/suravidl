"""Settings -> yt-dlp download options: the mapping must mirror yt-dlp's CLI.

yt-dlp's CLI turns flags like --embed-metadata / --embed-thumbnail /
--embed-subs / --sponsorblock-remove into postprocessors; the Python API does
not, so these tests pin the postprocessor keys and ordering we add.
"""
from pathlib import Path

import pytest

from suravidl_engine.download_opts import (
    build_download_opts, parse_langs, parse_rate_limit,
)
from suravidl_engine.settings import DEFAULTS, Settings


def opts(**overrides):
    s = dict(DEFAULTS)
    s.update(overrides)
    return build_download_opts(s, "/dl", archive_path="/dl/archive.txt")


def pp_keys(o):
    return [p["key"] for p in o.get("postprocessors", [])]


# -- helpers ----------------------------------------------------------------

def test_parse_rate_limit():
    assert parse_rate_limit("") is None
    assert parse_rate_limit("1024") == 1024
    assert parse_rate_limit("500K") == 512000
    assert parse_rate_limit("2M") == 2 * 1024 * 1024
    assert parse_rate_limit("1.5M") == int(1.5 * 1024 * 1024)
    with pytest.raises(ValueError):
        parse_rate_limit("fast")
    with pytest.raises(ValueError):
        parse_rate_limit("-5")


def test_parse_langs():
    assert parse_langs("en, id ,id") == ["en", "id", "id"]
    assert parse_langs("") == []
    assert parse_langs("all") == ["all"]


# -- defaults / template ----------------------------------------------------

def test_defaults_only_set_outtmpl():
    o = opts()
    assert o["outtmpl"] == str(Path("/dl") / "%(title).100B.%(ext)s")
    assert "postprocessors" not in o
    assert "writesubtitles" not in o
    assert "ratelimit" not in o


def test_filename_template_is_applied():
    o = opts(filename_template="%(uploader)s - %(title)s.%(ext)s")
    assert o["outtmpl"] == str(Path("/dl") / "%(uploader)s - %(title)s.%(ext)s")


# -- subtitles --------------------------------------------------------------

def test_subtitles_sidecar():
    o = opts(subtitles_mode="sidecar", subtitles_langs="en, id")
    assert o["writesubtitles"] is True
    assert o["subtitleslangs"] == ["en", "id"]
    assert "writeautomaticsub" not in o
    assert "postprocessors" not in o


def test_subtitles_auto_sidecar():
    o = opts(subtitles_mode="sidecar", subtitles_auto=True)
    assert o["writeautomaticsub"] is True


def test_subtitles_embed_adds_postprocessor():
    o = opts(subtitles_mode="embed")
    assert pp_keys(o) == ["FFmpegEmbedSubtitle"]
    assert o["postprocessors"][0]["already_have_subtitle"] is True


def test_subtitles_off_by_default():
    o = opts(subtitles_mode="off", subtitles_langs="en")
    assert "writesubtitles" not in o


# -- metadata / thumbnails --------------------------------------------------

def test_embed_metadata():
    o = opts(embed_metadata=True)
    assert pp_keys(o) == ["FFmpegMetadata"]
    assert o["postprocessors"][0]["add_metadata"] is True


def test_embed_thumbnail_implies_writethumbnail():
    o = opts(embed_thumbnail=True)
    assert o["writethumbnail"] is True
    assert pp_keys(o) == ["EmbedThumbnail"]
    # playlist thumbnail output must be disabled, like the CLI does
    assert o["outtmpl"]["pl_thumbnail"] == ""
    assert o["outtmpl"]["default"].endswith("%(title).100B.%(ext)s")


# -- sponsorblock -----------------------------------------------------------

def test_sponsorblock_mark_only():
    o = opts(sponsorblock_mode="mark", sponsorblock_categories="sponsor, intro")
    assert pp_keys(o) == ["SponsorBlock", "ModifyChapters"]
    assert o["postprocessors"][0]["categories"] == {"sponsor", "intro"}
    assert o["postprocessors"][0]["when"] == "after_filter"
    assert o["postprocessors"][1]["remove_sponsor_segments"] == set()


def test_sponsorblock_remove():
    o = opts(sponsorblock_mode="remove", sponsorblock_categories="sponsor")
    assert pp_keys(o) == ["SponsorBlock", "ModifyChapters"]
    assert o["postprocessors"][1]["remove_sponsor_segments"] == {"sponsor"}


# -- network ----------------------------------------------------------------

def test_rate_limit_and_fragments():
    o = opts(rate_limit="2M", fragments=4)
    assert o["ratelimit"] == 2 * 1024 * 1024
    assert o["concurrent_fragment_downloads"] == 4
    o2 = opts(fragments=1)
    assert "concurrent_fragment_downloads" not in o2


def test_proxy():
    o = opts(proxy="socks5://127.0.0.1:1080")
    assert o["proxy"] == "socks5://127.0.0.1:1080"


# -- archive ----------------------------------------------------------------

def test_archive():
    o = opts(archive=True)
    assert o["download_archive"] == "/dl/archive.txt"
    assert "download_archive" not in opts(archive=False)


# -- combined ordering ------------------------------------------------------

def test_combined_order_matches_cli_phases():
    o = opts(subtitles_mode="embed", embed_metadata=True,
             embed_thumbnail=True, sponsorblock_mode="remove")
    assert pp_keys(o) == [
        "FFmpegEmbedSubtitle", "SponsorBlock", "ModifyChapters",
        "FFmpegMetadata", "EmbedThumbnail",
    ]


# -- settings validation ----------------------------------------------------

def test_settings_validate_tier1_keys(tmp_path):
    s = Settings(path=tmp_path / "s.json")

    s.update({"filename_template": "%(title)s.%(ext)s",
              "subtitles_mode": "embed", "subtitles_langs": "en, id",
              "subtitles_auto": True, "embed_metadata": True,
              "embed_thumbnail": False, "rate_limit": "1.5M", "fragments": 8,
              "proxy": "http://127.0.0.1:8080", "archive": True,
              "sponsorblock_mode": "remove",
              "sponsorblock_categories": "sponsor, selfpromo"})
    got = s.get()
    assert got["filename_template"] == "%(title)s.%(ext)s"
    assert got["fragments"] == 8
    assert got["sponsorblock_categories"] == "sponsor, selfpromo"

    for bad in ({"filename_template": "../escape.%(ext)s"},
                {"filename_template": "no-extension"},
                {"filename_template": "/abs/%(ext)s"},
                {"subtitles_mode": "burn"},
                {"rate_limit": "fast"},
                {"proxy": "ftp://x"},
                {"proxy": "http://has space"},
                {"sponsorblock_mode": "nuke"},
                {"sponsorblock_categories": "sponsor,evil"}):
        with pytest.raises(ValueError):
            s.update(bad)

    # fragments clamp
    assert s.update({"fragments": 99})["fragments"] == 16
    assert s.update({"fragments": 0})["fragments"] == 1
