"""v0.46.17 "the namesake" — two videos, one title, one filename.

Field report (2026-10-14): when a different video wore the same filename
as an older download, the older file was replaced without confirmation.
Reproduced against the engine's own opts, both faces of it: with one
extension the second download was silently skipped ("already on disk —
nothing was fetched", the video never fetched), and with the container
setting the remux wrote straight over the older file (the ffmpeg
invocation under FFmpegVideoConvertorPP has no existence check).

The round: the default name wears the site's own id —
`%(title).100B [%(id)s].%(ext)s` — so names are unique per video by
construction, and a stored OLD default upgrades in place (a value still
equal to it was never customized; anything hand-made is left alone).
Custom templates WITHOUT the id get two guards: a download that yt-dlp
skips because the name is taken by a DIFFERENT video is re-run once
under an id-suffixed variant (jobs._escape_namesake), and the container
remux lands beside another video's file instead of over it
(extract.SafeRemuxPP). Both report themselves on the card through
_deliver_notice — the shared channel that survives yt-dlp running
process_info on a COPY and returning the original for downloads
(YoutubeDL.py:3118), which is why the v0.45.29 channel's PP-side writers
(thumbnail embed, stream fix) had also been writing into a dict nobody
reads.
"""
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text(encoding="utf-8")
EXTRACT = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(
    encoding="utf-8")
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")

sys.path.insert(0, str(ROOT / "src"))
from suravidl_engine import cut, download_opts, whatsnew  # noqa: E402
from suravidl_engine.jobs import JobManager  # noqa: E402
from suravidl_engine.settings import DEFAULTS, Settings  # noqa: E402

NEW = "%(title).100B [%(id)s].%(ext)s"
LEGACY = "%(title).100B.%(ext)s"
LONG = "t" * 100          # both titles truncate to this at .100B — one name
A_STEM, B_STEM = LONG + "AAA", LONG + "BBB"


# -- the name itself --------------------------------------------------------

def test_the_default_name_wears_the_id():
    assert DEFAULTS["filename_template"] == NEW
    assert download_opts.DEFAULT_TEMPLATE == NEW
    o = download_opts.build_download_opts(dict(DEFAULTS), "/dl")
    assert o["outtmpl"] == str(Path("/dl") / NEW)
    # the job-scoped fallback template (no settings wired) agrees
    assert 'str(target_dir / "%(title).100B [%(id)s].%(ext)s")' in JOBS
    assert 'placeholder="%(title).100B [%(id)s].%(ext)s"' in HTML


def test_a_stored_old_default_upgrades_itself(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"filename_template": LEGACY, "theme": "light"}))
    s = Settings(path=p)
    assert s.get()["filename_template"] == NEW, \
        "a stored old default was never customized — it upgrades in place"
    assert s.get()["theme"] == "light", "only the template migrates"


def test_a_hand_made_template_is_left_alone(tmp_path):
    for value in ("mine/%(title)s.%(ext)s",
                  "%(uploader)s - %(title)s.%(ext)s",
                  "%(title).80B.%(ext)s",
                  NEW):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"filename_template": value}))
        assert Settings(path=p).get()["filename_template"] == value


def test_the_disambiguating_variant_wears_the_id_before_the_extension():
    assert download_opts.disambiguating_template(LEGACY) == NEW
    assert download_opts.disambiguating_template(
        "channel/%(title)s.%(ext)s") == "channel/%(title)s [%(id)s].%(ext)s"
    assert download_opts.disambiguating_template(
        "%(uploader)s - %(title)s.%(ext)s") == (
        "%(uploader)s - %(title)s [%(id)s].%(ext)s")
    # already carries the id — a collision would mean the file IS this
    # video's; nothing to change (None = skip stands)
    assert download_opts.disambiguating_template(NEW) is None
    # no %(ext)s at the end to sit before — leave it alone
    assert download_opts.disambiguating_template("x/%(ext)s/%(title)s") is None


# -- the owner oracle -------------------------------------------------------

def test_the_owner_oracle_knows_whose_file_it_is(tmp_path):
    mgr = JobManager(download_dir=tmp_path / "dl", db_path=tmp_path / "j.db")
    a = tmp_path / "dl" / "X.mp4"
    a.write_bytes(b"a")
    # no row claims it, no id in the name -> NOT this video's (a skip over
    # it must never stand, a remux must never land on it)
    assert mgr._path_belongs_to(a, "vid1") is False
    with mgr._lock:
        mgr._jobs["j1"] = {"id": "j1", "video_id": "vid1",
                           "filepath": str(a), "files": [str(a)]}
    assert mgr._path_belongs_to(a, "vid1") is True
    assert mgr._path_belongs_to(a, "vid2") is False
    # rows long gone: the name itself can wear the id
    b = tmp_path / "dl" / "Y [vid9].mp4"
    b.write_bytes(b"b")
    assert mgr._path_belongs_to(b, "vid9") is True
    assert mgr._path_belongs_to(b, "vid1") is False


# -- the remux guard (unit, with real files) --------------------------------

def _gen(ffmpeg, dest, source_filter):
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", source_filter, "-pix_fmt", "yuv420p",
                    str(dest)], check=True, capture_output=True, timeout=120)


@pytest.mark.skipif(not cut.ffmpeg_exe(), reason="no ffmpeg on this box")
def test_a_remux_never_lands_on_another_videos_file(tmp_path):
    import yt_dlp

    from suravidl_engine.extract import SafeRemuxPP

    ff = cut.ffmpeg_exe()
    older = tmp_path / "cool.mp4"
    _gen(ff, older, "testsrc=duration=2:size=128x72:rate=10")
    before = hashlib.sha256(older.read_bytes()).hexdigest()
    src = tmp_path / "cool.mkv"
    _gen(ff, src, "color=c=red:duration=2:size=128x72:rate=10")

    ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True})
    out_notes: list = []
    ydl.params["__sv_notices_out"] = out_notes
    ydl.params["__sv_path_owner"] = lambda path, vid: False   # all foreign
    pp = SafeRemuxPP(ydl, preferedformat="mp4")
    files, out = pp.run({"filepath": str(src), "ext": "mkv",
                         "id": "BBB", "format": "f"})
    landed = Path(out["filepath"])
    assert landed.name == "cool [BBB].mp4", landed.name
    assert hashlib.sha256(older.read_bytes()).hexdigest() == before, \
        "the older file must be byte-identical — untouched"
    assert files == [str(src)], "the remuxed source is the one to delete"
    assert any("already belonged to a different video" in n
               for n in out_notes), out_notes


@pytest.mark.skipif(not cut.ffmpeg_exe(), reason="no ffmpeg on this box")
def test_a_remux_may_refresh_this_videos_own_file(tmp_path):
    import yt_dlp

    from suravidl_engine.extract import SafeRemuxPP

    ff = cut.ffmpeg_exe()
    own = tmp_path / "cool.mp4"
    _gen(ff, own, "testsrc=duration=2:size=128x72:rate=10")
    src = tmp_path / "cool.mkv"
    _gen(ff, src, "color=c=red:duration=2:size=128x72:rate=10")

    ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True})
    out_notes: list = []
    ydl.params["__sv_notices_out"] = out_notes
    ydl.params["__sv_path_owner"] = lambda path, vid: True    # this video's
    pp = SafeRemuxPP(ydl, preferedformat="mp4")
    files, out = pp.run({"filepath": str(src), "ext": "mkv",
                         "id": "BBB", "format": "f"})
    assert Path(out["filepath"]).name == "cool.mp4", \
        "same video: the plain name is right (a refresh, not a clash)"
    assert not out_notes, "no namesake caveat when the file is this video's"


# -- the delivery channel ---------------------------------------------------

def test_a_pp_notice_reaches_the_shared_channel():
    import yt_dlp

    from suravidl_engine.extract import _deliver_notice

    ydl = yt_dlp.YoutubeDL({"quiet": True})
    out: list = []
    ydl.params["__sv_notices_out"] = out
    info: dict = {}
    _deliver_notice(ydl, info, "hello")
    assert out == ["hello"], "the channel jobs reads back"
    assert info["__sv_notices"] == ["hello"], "and the in-dict road stays"
    # jobs plants the list and reads it (the returned info is a copy's
    # original — see the module docstring)
    assert 'opts["__sv_notices_out"] = []' in JOBS
    assert 'opts.get("__sv_notices_out")' in JOBS


# -- end to end: the same rig the field report needs ------------------------

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
    raise TimeoutError(f"job stayed {mgr.get(jid)['status']}")


def _manager(dd, template):
    def dopts(dir_, raw_args=None, overrides=None):
        s = {**DEFAULTS, "download_dir": str(dir_),
             "filename_template": template}
        return download_opts.build_download_opts(s, dir_, raw_args=raw_args)
    return JobManager(download_dir=dd, db_path=dd / "jobs.db",
                      max_concurrent=1, download_opts=dopts)


@pytest.fixture()
def namesake_rig(tmp_path):
    """Two DIFFERENT videos whose titles truncate to one filename."""
    root = tmp_path / "srv"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir(parents=True)
    shutil.copy(FIXTURES / "tiny.mp4", root / "a" / f"{A_STEM}.mp4")
    shutil.copy(FIXTURES / "tiny2.mp4", root / "b" / f"{B_STEM}.mp4")
    server, base = _serve(root)
    yield base
    server.shutdown()


def test_a_same_name_pair_no_longer_fights_over_one_filename(
        tmp_path, namesake_rig):
    """The field report, end to end: the second video must arrive —
    never a silent skip, never over the older file — with the id in its
    name and the reason on its card."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd, LEGACY)      # a custom template without the id
    ja = _wait(mgr, mgr.create(f"{namesake_rig}/a/{A_STEM}.mp4")["id"])
    assert ja["status"] == "completed", ja.get("error")
    a_path = Path(ja["filepath"])
    a_sha = hashlib.sha256(a_path.read_bytes()).hexdigest()

    jb = _wait(mgr, mgr.create(f"{namesake_rig}/b/{B_STEM}.mp4")["id"])
    assert jb["status"] == "completed", jb.get("error")
    b_path = Path(jb["filepath"])
    assert b_path.is_file() and b_path != a_path
    assert f"[{download_opts.short_id(B_STEM)}]" in b_path.name, \
        "the escaped download wears the site's id (short form since v0.46.18)"
    assert "already belonged to a different video" in (jb.get("note") or "")
    assert hashlib.sha256(a_path.read_bytes()).hexdigest() == a_sha, \
        "the older file is byte-identical — it was never the price"


def test_the_default_template_needs_no_guards_at_all(tmp_path, namesake_rig):
    """With the id in the default name the two never collide: both
    arrive, distinct names, and no caveat rides either card."""
    dd = tmp_path / "dl"
    dd.mkdir()
    mgr = _manager(dd, NEW)
    ja = _wait(mgr, mgr.create(f"{namesake_rig}/a/{A_STEM}.mp4")["id"])
    jb = _wait(mgr, mgr.create(f"{namesake_rig}/b/{B_STEM}.mp4")["id"])
    assert (ja["status"], jb["status"]) == ("completed", "completed")
    assert Path(ja["filepath"]).name != Path(jb["filepath"]).name
    assert Path(ja["filepath"]).is_file() and Path(jb["filepath"]).is_file()
    assert not ja.get("note") and not jb.get("note"), \
        "no collision happened — no namesake caveat may appear"


# -- wiring and the release itself ------------------------------------------

def test_the_guards_are_wired():
    assert "def _escape_namesake(" in JOBS
    assert "self._escape_namesake(" in JOBS
    assert 'opts["__sv_path_owner"] = self._path_belongs_to' in JOBS
    assert "class SafeRemuxPP" in EXTRACT
    assert "_guard_remux_overwrites(ydl)" in EXTRACT
    assert "_deliver_notice(" in EXTRACT


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # v0.46.18 "the nickname" shortened long ids — this round's entry
    # stays among the living ten (the strict current-version pin moved
    # to that release's test file, per the retirement policy)
    assert any(e["version"] == "0.46.17"
               and e["title"].lower() == "the namesake"
               for e in whatsnew.ENTRIES)
