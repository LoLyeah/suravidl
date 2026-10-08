"""The 2026-09-27 report, pinned — its screenshots and its words.

- "ERROR: Unable to down…": every failed row cut its message to 160 chars in
  one ellipsised line; the full text is what a user must be able to read,
  expand and copy.
- "wrong turn baby" (a playlist) offered only Delete while single-file rows
  offered Open / Share / Play: a playlist row must expose its own files, each
  with the same hand-offs, and Play must stream an entry by name.
- "video only — sound is added on download" read as a contradiction; the
  user asked for a checklist to keep a video silent, with sound the default.
- "Add the open folder button too, below copy path": desktop reveals the
  folder; Android cannot open Android/data for anyone, so it lists the
  folder in the app instead.
"""
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src" / "suravidl_engine" / "web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()
AUTH = {"Authorization": "Bearer testtoken"}

ERR_BRANCH = '} else if (j.status === "error" || j.status === "interrupted") {'


def _error_branch() -> str:
    return APP.split(ERR_BRANCH)[1].split("} else if (j.filepath)")[0]


# -- 1. the whole error, readable and copyable ------------------------------

def test_a_failed_row_shows_the_whole_error():
    """`(j.error || "").slice(0, 160)` + a one-line ellipsis turned yt-dlp's
    explanation into "ERROR: Unable to down…" — the text the user needs to
    act on was the part that was hidden."""
    assert ".slice(0, 160)" not in APP, "a failed row still cuts its message"
    seg = _error_branch()
    assert 'el("div", "jerr", errText)' in seg, \
        "the row must render the whole message"
    assert 'classList.add("clamp")' in seg, \
        "a long message starts clamped to two lines"
    assert "tap to show the whole message" in seg


def test_the_error_clamp_lifts_on_tap():
    assert ".jerr.clamp" in CSS
    assert "-webkit-line-clamp: 2" in CSS
    assert ".jerr.clamp.open" in CSS


def test_an_error_can_be_copied_whole():
    assert "async function copyText(" in APP, "one copy helper for every copy"
    seg = _error_branch()
    assert "copyText(errText)" in seg, "the failed row needs a Copy button"
    # the footer's copy path goes through the same helper (WebViews refuse
    # navigator.clipboard on some hosts; the helper has the fallback)
    foot = APP.split("function wireCopyPath()")[1].split("function ", 1)[0]
    assert "copyText(" in foot


# -- 2. a playlist row exposes its files ------------------------------------

def test_a_playlist_row_is_recognised_by_its_files_not_its_path():
    """A single-file row's filepath is one of its own files; a playlist's
    filepath is the folder and its files are the entries — a folder is never
    among them. That difference decides which hand-offs make sense.

    The merged case matters as much: a video+audio download also lists its
    fragments (…f200.mp4, …f64.mp4, final) in `files`, and the final file is
    one of them — treating that as a playlist took Play/Open/Share off the
    most common YouTube-style download (caught live, 2026-09-27)."""
    assert ("const playlistRow = !!(j.files && j.files.length\n"
            "    && j.files[0] !== j.filepath && !j.files.includes(j.filepath));"
            ) in APP


def test_playlist_rows_get_an_openable_file_list():
    assert "function jobFileItem(" in APP
    seg = APP.split("function jobFileItem(")[1].split("\nfunction ", 1)[0]
    assert "window.AndroidHost.openFile(file)" in seg, \
        "each entry gets its own Open"
    assert "window.AndroidHost.shareFile(file)" in seg, \
        "each entry gets its own Share"
    assert "openPlayer(j, file)" in seg, "each entry can be played in-page"
    # and the row offers the list itself, still with Delete beside it
    row = APP.split("const playlistRow = !!")[1].split("} else if (j.status ===")[0]
    assert 't("Files ({n})", { n: count })' in row
    assert 't("Hide files ({n})", { n: count })' in row


def test_playing_a_playlist_entry_streams_by_name(tmp_path):
    """The stream route must serve one recorded entry of a playlist job by
    basename — and must never become a way to read other files."""
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        # a dead local port fails in milliseconds and leaves the worker
        # finished before the state below is fabricated — a cancelled job
        # only flips its status, the worker may still be writing (this test
        # raced it once under load)
        job = c.post("/jobs", json={"url": "http://127.0.0.1:1/list"},
                     headers=AUTH).json()
        cur = None
        for _ in range(300):
            cur = next((j for j in c.get("/jobs", headers=AUTH).json()["jobs"]
                        if j["id"] == job["id"]), None)
            if cur and cur["status"] in ("error", "cancelled", "interrupted"):
                break
            time.sleep(0.05)
        assert cur and cur["status"] != "queued", cur
        dl = c.app.state.download_dir
        dl.mkdir(parents=True, exist_ok=True)
        first = dl / "e1.mp4"
        first.write_bytes(b"first-file")
        second = dl / "e2.mp4"
        second.write_bytes(b"second-file")
        files = [str(first), str(second)]
        mgr = c.app.state.manager
        with mgr._lock, mgr._con:                       # noqa: SLF001
            mgr._jobs[job["id"]]["status"] = "completed"    # noqa: SLF001
            mgr._jobs[job["id"]]["filepath"] = str(dl)      # noqa: SLF001
            mgr._jobs[job["id"]]["files"] = files           # noqa: SLF001
            mgr._con.execute(                               # noqa: SLF001
                "UPDATE jobs SET status='completed', filepath=?, files=? "
                "WHERE id=?", (str(dl), json.dumps(files), job["id"]))

        ok = c.get(f"/jobs/{job['id']}/stream", params={"name": "e2.mp4"},
                   headers=AUTH)
        assert ok.status_code == 200, ok.text
        assert ok.content == b"second-file"

        # not in the job's recorded list → refused
        outsider = dl / "other.mp4"
        outsider.write_bytes(b"nope")
        r = c.get(f"/jobs/{job['id']}/stream", params={"name": "other.mp4"},
                  headers=AUTH)
        assert r.status_code == 404
        # a path, not a basename → refused
        r = c.get(f"/jobs/{job['id']}/stream", params={"name": "../escape.mp4"},
                  headers=AUTH)
        assert r.status_code in (403, 404)


# -- 3. plain wording + an explicit "no sound" choice -----------------------

def test_video_wording_is_plain_and_has_a_no_sound_state():
    # 2026-09-27 second report: the suffix lives on the checkbox, not on
    # every row — "only show 'video only — no sound' when it is checked"
    assert "sound included" not in APP
    assert "video only — no sound" in APP
    assert "video only — no sound available" in APP, \
        "a site with no separate audio must not promise sound"
    assert "video + audio" in APP and "audio only" in APP


def test_the_no_sound_checklist_exists_and_the_labels_follow_it():
    assert 'id="noSound"' in HTML and 'id="soundRow"' in HTML
    assert 'id="soundRow"' in HTML.split('id="formats"')[0], \
        "the choice sits with the format table it explains"
    assert '$("soundRow").classList.toggle("hidden", !anyVideo)' in APP
    assert '$("noSound").addEventListener("change", refreshSoundLabels)' in APP
    # the switch re-labels the rows it applies to, in place
    assert "function refreshSoundLabels(" in APP
    assert "[data-sound]" in APP
    seg = APP.split("function refreshSoundLabels(")[1].split("\nfunction ", 1)[0]
    assert 'querySelectorAll("#formats .fmt-kind[data-sound]")' in seg


def test_the_sound_choice_rides_every_start_from_this_card():
    """Chips, best-quality and playlist starts go through startJob — the
    checkbox must ride them all, and the engine must know the key."""
    assert 'if ($("noSound").checked) ov = { ...(ov || {}), no_audio: true };' in APP
    assert "if (ov) body.overrides = ov;" in APP
    # a video-only pick is not paired when the user said "no sound"
    spec = APP.split("function fmtSpec(")[1].split("\nfunction ", 1)[0]
    assert '!$("noSound").checked' in spec


def test_no_audio_is_a_per_job_override_the_engine_accepts(tmp_path):
    from suravidl_engine.settings import validate_overrides

    assert validate_overrides({"no_audio": True}) == {"no_audio": True}
    assert validate_overrides({}) == {}

    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path / "dl", auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        j = c.post("/jobs", headers=AUTH, json={
            "url": "http://example.invalid/v.mp4",
            "overrides": {"no_audio": True},
        }).json()
    assert j["overrides"] == {"no_audio": True}


def test_strip_audio_pairing_reads_an_expression_video_only():
    from suravidl_engine.download_opts import strip_audio_pairing

    # a concrete stream id: exactly that stream
    assert strip_audio_pairing("137+bestaudio/best") == "137"
    # a selector: keep its fallback ladder so a site without video-only
    # streams still yields a file
    assert strip_audio_pairing("bv*+ba/b") == "bv*/b"
    assert strip_audio_pairing(
        "bv*[height<=1080]+ba/b[height<=1080]/b"
    ) == "bv*[height<=1080]/b[height<=1080]/b"
    # nothing to strip stays as it is
    assert strip_audio_pairing("bestaudio/best") == "bestaudio/best"
    assert strip_audio_pairing("137") == "137"


def test_no_audio_reaches_yt_dlp_as_a_silent_format(tmp_path, monkeypatch):
    """The override must reach the REAL options builder: with it a paired
    pick downloads the video stream alone, a bare 'best' pairs nothing, and
    without it nothing changes."""
    from suravidl_engine import jobs as jobs_mod

    seen: list[dict] = []

    class Rec:
        def __init__(self, opts, *a, **k):
            seen.append(dict(opts))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=True):
            raise RuntimeError("offline: options captured")

    monkeypatch.setattr(jobs_mod.yt_dlp, "YoutubeDL", Rec)

    def run_one(fmt, overrides):
        seen.clear()
        mgr = jobs_mod.JobManager(download_dir=tmp_path / "dl",
                                  db_path=str(tmp_path / "jobs.db"))
        mgr.create("https://example.invalid/v", fmt=fmt, overrides=overrides)
        # `seen` is fed by a CLASS-level patch of YoutubeDL, so a worker
        # left alive by another test can construct one inside our window
        # and its capture (e.g. the no-fmt 'bv/b' shape) would land as
        # ours — flaked under the full suite, 2026-10-08. Match only the
        # options aimed at THIS run's unique download folder.
        mine = str(tmp_path / "dl")
        deadline = time.monotonic() + 10
        ours = None
        while time.monotonic() < deadline:
            ours = next((o for o in seen
                         if mine in str(o.get("outtmpl") or "")), None)
            if ours:
                break
            time.sleep(0.05)
        assert ours, "the options never reached the downloader"
        # settle our worker before the next sub-run shares `seen`
        while mgr._running and time.monotonic() < deadline:
            time.sleep(0.02)
        return ours

    opts = run_one("137+bestaudio/best", {"no_audio": True})
    assert opts["format"] == "137"
    opts = run_one(None, {"no_audio": True})
    assert opts["format"] == "bv/b", "a bare 'best' pairs no audio at all"
    opts = run_one("137+bestaudio/best", None)
    assert opts["format"] == "137+bestaudio/best", \
        "without the choice the pairing is untouched"


# -- 4. "open folder", below copy path --------------------------------------

def test_the_footer_offers_open_folder_next_to_copy_path():
    assert 'id="openDir"' in HTML
    foot = HTML.split("<footer")[1].split("</footer>")[0]
    assert 'id="copyDir"' in foot and 'id="openDir"' in foot


def test_open_folder_reveals_on_desktop_and_lists_on_a_phone():
    assert '$("openDir").onclick' in APP
    assert '"/app/reveal-dir"' in APP, "desktop shells reveal the real folder"
    seg = APP.split('$("openDir").onclick')[1].split("function ", 1)[0]
    assert "openFolderSheet()" in seg, "no shell → list the folder in-app"
    assert "function openFolderSheet(" in APP
    assert '"/files/list"' in APP
    sheet = APP.split("function openFolderSheet(")[1].split("\nfunction ", 1)[0]
    assert "folderList" in sheet
    assert "function folderItem(" in APP
    item = APP.split("function folderItem(")[1].split("\nfunction ", 1)[0]
    assert 'f.kind === "video" || f.kind === "audio"' in item, \
        "only media gets Play"
    assert '"/files/stream?path="' in item
    assert "window.AndroidHost.openFile(f.path)" in item
    assert "window.AndroidHost.shareFile(f.path)" in item
    # the modal announces itself like every other dialog
    for ident in ("folderModal", "folderTitle", "folderList", "folderClose"):
        assert f'id="{ident}"' in HTML, ident
