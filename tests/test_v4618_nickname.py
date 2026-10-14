"""v0.46.18 "the nickname" — a filename id must be a tag, not a paragraph.

Field report (2026-10-14, the day after "the namesake" shipped): an HLS
download landed as
`master [master.m3u8?token=bcb90d467b7581a9d6fad7e70b2ccb5b-1791965600-182.253.116].mp4`
— the "id" some extractors hand back is the whole signed URL, so the
uniqueness tag became a novel.

The nickname: long or URL-sludge ids collapse to a stable 12-hex digest
(`short_id`), applied by `ShortIdPP` at pre_process — BEFORE yt-dlp
computes the output name (process_info calls pre_process at
YoutubeDL.py:3359, right above prepare_filename), so the template, the
skip escape and the remux guard all see the short form. Compact ids pass
verbatim (YouTube's 11 characters, TikTok's digits); the rewrite is
deterministic, so the same video always wears the same tag — the skip
dedupe and the owner checks rely on that.
"""
import functools
import hashlib
import http.server
import json
import re
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
EXTRACT = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(
    encoding="utf-8")
JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text(
    encoding="utf-8")

sys.path.insert(0, str(ROOT / "src"))
from suravidl_engine import download_opts, whatsnew  # noqa: E402
from suravidl_engine.jobs import JobManager  # noqa: E402
from suravidl_engine.settings import DEFAULTS  # noqa: E402

FIELD_ID = ("master.m3u8?token=bcb90d467b7581a9d6fad7e70b2ccb5b"
            "-1791965600-182.253.116")


# -- the rule ----------------------------------------------------------------

def test_compact_ids_pass_verbatim():
    for clean in ("dQw4w9WgXcQ",                       # YouTube
                  "7293681857083747589",               # TikTok digits
                  "C1x2Yz3AbCd",                       # instagram-ish
                  "t" * download_opts.SHORT_ID_MAX):   # exactly at the cap
        assert download_opts.short_id(clean) == clean


def test_ugly_ids_collapse_to_a_stable_digest():
    got = download_opts.short_id(FIELD_ID)
    assert got == "6844270b910f", \
        "the field id's exact tag — a change here changes every future name"
    assert re.fullmatch(r"[0-9a-f]{12}", got)
    assert download_opts.short_id(FIELD_ID) == got, "deterministic"
    assert download_opts.short_id(got) == got, "idempotent — already a tag"
    # every junk class triggers, and so does sheer length
    for ugly in ("a?b", "a&b", "a=b", "a%b", "a#b", "a:b", "a/b", "a\\b",
                 "a b", "a\tb", "t" * (download_opts.SHORT_ID_MAX + 1)):
        assert download_opts.short_id(ugly) != ugly, ugly
        assert len(download_opts.short_id(ugly)) == 12


def test_empty_ids_stay_empty():
    assert download_opts.short_id(None) == ""
    assert download_opts.short_id("") == ""


# -- the PP and the name check ----------------------------------------------

def test_the_pp_rewrites_the_id_and_leaves_clean_ones():
    import yt_dlp

    from suravidl_engine.extract import ShortIdPP

    pp = ShortIdPP(yt_dlp.YoutubeDL({"quiet": True}))
    _, info = pp.run({"id": FIELD_ID, "title": "master"})
    assert info["id"] == download_opts.short_id(FIELD_ID)
    assert info["title"] == "master", "only the id is touched"
    _, info2 = pp.run({"id": "dQw4w9WgXcQ"})
    assert info2["id"] == "dQw4w9WgXcQ"


def test_the_owner_check_knows_the_short_form(tmp_path):
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db")
    tag = download_opts.short_id(FIELD_ID)
    named = tmp_path / "dl" / f"master [{tag}].mp4"
    named.write_bytes(b"x")
    # both spellings of the video id recognize the short-named file
    assert mgr._path_belongs_to(named, FIELD_ID) is True
    assert mgr._path_belongs_to(named, tag) is True
    other = tmp_path / "dl" / "master.mp4"
    other.write_bytes(b"y")
    assert mgr._path_belongs_to(other, FIELD_ID) is False


def test_the_nickname_is_wired():
    assert "class ShortIdPP" in EXTRACT
    assert "_attach_short_id(ydl)" in EXTRACT
    assert "info[\"id\"] = short_id(info[\"id\"])" in EXTRACT
    assert "short_id(vid)" in JOBS
    assert "short_id(vid)" in EXTRACT          # the remux guard's suffix


# -- end to end: the field name, on the real flow ---------------------------

def _serve(directory):
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _wait(mgr, jid, timeout=90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = mgr.get(jid)
        if j["status"] in ("completed", "error", "cancelled"):
            return j
        time.sleep(0.25)
    raise TimeoutError(jid)


def test_an_hls_style_id_lands_as_a_short_tag(tmp_path):
    """The field report, end to end: a stem that IS a signed URL must not
    become a paragraph in the filename; the tag is the digest, and the
    job's recorded video_id wears it too."""
    root = tmp_path / "srv"
    root.mkdir()
    stem = "master.m3u8?token=abc123def456"
    shutil.copy(FIXTURES / "tiny.mp4", root / f"{stem}.mp4")
    server, base = _serve(root)
    try:
        dd = tmp_path / "dl"
        dd.mkdir()

        def dopts(dir_, raw_args=None, overrides=None):
            s = {**DEFAULTS, "download_dir": str(dir_)}
            return download_opts.build_download_opts(s, dir_, raw_args=raw_args)
        mgr = JobManager(download_dir=dd, db_path=dd / "jobs.db",
                         max_concurrent=1, download_opts=dopts)
        from urllib.parse import quote
        url = f"{base}/{quote(stem)}.mp4"
        j = _wait(mgr, mgr.create(url)["id"])
        assert j["status"] == "completed", j.get("error")
        tag = download_opts.short_id(stem)
        name = Path(j["filepath"]).name
        assert f"[{tag}]" in name, name
        assert f"[{stem}]" not in name, "the raw URL never reaches the bracket"
        assert j["video_id"] == tag, "the recorded id is the short form"
    finally:
        server.shutdown()


# -- the release itself ------------------------------------------------------

def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__

    assert __version__ == "0.46.18"
    top = whatsnew.ENTRIES[0]
    assert top["version"] == "0.46.18"
    assert top["title"].lower() == "the nickname"
    assert len(whatsnew.ENTRIES) == 10
