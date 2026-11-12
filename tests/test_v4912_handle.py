"""v0.49.12 "the handle" — a file name a person can live with.

The report: a download landed as
`AQNenhI7M4vPbmsy…jq7jEZeKCnMr [00246db2f6c1].mp4` — the site's "title" was
an opaque token. The name is built from a preset budget, and a title that is
only a token is replaced with who and when, while `[id]` keeps it unique.
"""
from __future__ import annotations

import pathlib

from suravidl_engine import names
from suravidl_engine.settings import DEFAULTS, Settings

ROOT = pathlib.Path(__file__).resolve().parents[1]

TOKEN = ("AQNenhI7M4vPbmsyM6X1UrJITkT9NR9McjrjzcxvE542K8lq6jVx6VpElhlqyZ-"
         "00ajzXeAWJuDC2KR6CxEoEfh2jq7jEZeKCnMr")


def test_the_reported_token_is_recognised():
    assert names.looks_opaque(TOKEN, "00246db2f6c1") is True


def test_a_real_title_is_never_a_token():
    assert names.looks_opaque("How to make bread at home") is False
    assert names.looks_opaque("Cara membuat roti di rumah") is False
    # space-free CJK and Thai are real titles, not tokens
    assert names.looks_opaque("中文标题没有空格但是真的") is False
    assert names.looks_opaque("ทำอาหารเช้าง่ายๆ") is False
    # no digits, or too short, or not ASCII-only
    assert names.looks_opaque("abcdefghijklmnopqrstuvwxyz") is False
    assert names.looks_opaque("abc123") is False
    assert names.looks_opaque("naïve_café_1234567890abcd") is False


def test_a_title_equal_to_its_id_is_a_token_only_when_id_shaped():
    long_id = "Cx0a1b2c3d4e5f6g7h8i9j0k"
    assert names.looks_opaque(long_id, long_id) is True
    # a local file's "tiny [tiny]" keeps its name
    assert names.looks_opaque("tiny", "tiny") is False


def test_a_token_becomes_who_and_when():
    info = {"title": TOKEN, "id": "00246db2f6c1",
            "uploader": "Massimo", "upload_date": "20260109"}
    assert names.fallback_title(info, 100) == "Massimo - 2026-01-09"
    assert names.fallback_title({"title": TOKEN}, 100) == "video"


def test_the_filter_rewrites_the_title_before_the_name_is_built():
    info = {"title": TOKEN, "id": "00246db2f6c1",
            "uploader": "Massimo", "upload_date": "20260109"}
    assert names.title_filter(100)(info) is None
    assert info["title"] == "Massimo - 2026-01-09"


def test_a_long_title_is_cut_in_bytes_not_in_characters():
    # 40 CJK characters are 120 UTF-8 bytes; a 30-byte budget keeps ten
    text = "中" * 40
    assert names.clean_title(text, 30) == "中" * 10


def test_a_cut_never_splits_an_emoji():
    family = "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"
    got = names.clean_title("a" + family + "b", 20)   # the family is 25 bytes
    assert got == "a"
    assert "\u200d" not in got


def test_the_name_is_normalised_and_stripped_of_direction_marks():
    assert names.clean_title("cafe\u0301  au   lait", 100) == "café au lait"
    assert names.clean_title("\u202eabc", 100) == "abc"
    assert names.clean_title("trailing. ", 100) == "trailing"


def test_no_limit_keeps_the_title_whole_but_still_cleans_it():
    assert names.clean_title(TOKEN, 0) == TOKEN
    assert names.clean_title("a  b", 0) == "a b"


def test_the_preset_rides_the_default_template():
    s = dict(DEFAULTS, filename_length="short")
    assert names.template_for(s) == "%(title).60B [%(id)s].%(ext)s"


def test_download_opts_carry_the_filter_and_the_budget():
    from suravidl_engine.download_opts import build_download_opts

    s = dict(DEFAULTS, filename_length="long")
    opts = build_download_opts(s, "/tmp")
    assert opts["outtmpl"].endswith("%(title).180B [%(id)s].%(ext)s")
    assert callable(opts["match_filter"])
    info = {"title": TOKEN, "id": "x1", "uploader": "Massimo"}
    opts["match_filter"](info)
    assert info["title"] == "Massimo"


def test_a_hand_written_template_is_left_alone():
    from suravidl_engine.download_opts import build_download_opts

    s = dict(DEFAULTS, filename_template="%(uploader)s - %(title)s.%(ext)s")
    opts = build_download_opts(s, "/tmp")
    assert opts["outtmpl"].endswith("%(uploader)s - %(title)s.%(ext)s")


def test_the_setting_validates_and_defaults():
    store = Settings()
    assert store.update({"filename_length": "short"})["filename_length"] == "short"
    assert store.update({"filename_length": ""})["filename_length"] == "standard"
    try:
        store.update({"filename_length": "huge"})
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown preset must be refused")
