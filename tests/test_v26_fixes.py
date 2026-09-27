"""The 2026-09-27 second report, pinned — its screenshots and its words.

- "Can you use highlights for the chosen subtitle language? I can't unclick
  the one I accidentally click": chips are toggles now, the picked ones stay
  lit, and the list opens with the languages a person is actually after.
- "not all languages are available, depends on the video": a pick made on
  the last video is pruned against the one being probed, out loud.
- "the engine refuses to download if the language chosen isn't available":
  it must not — a missing language is skipped, never a failed job (tested
  against a real fixture download, sidecar and embed).
- "don't put 'video only — sound included' on every row; only show 'video
  only — no sound' when the checklist is checked."
- "what's the difference between … size calculated and unknown size?" — the
  unknown must be able to explain itself where a hover cannot reach (a
  phone): tap it.
- "the quality quick download should be below the title" — the chips move
  into the video card, under the title row.
- "TikTok is still broken": its webpage fetch is refused intermittently on
  some networks (yt-dlp#17604) and succeeds on the next attempt — the
  engine retries the flake and says so if it still fails.
"""
import functools
import http.server
import threading
import time
import types
from pathlib import Path

import pytest
import yt_dlp
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
ENGINE = ROOT / "src" / "suravidl_engine"
WEB = ENGINE / "web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()
PROBE_SRC = (ENGINE / "probe.py").read_text()
JOBS_SRC = (ENGINE / "jobs.py").read_text()
AUTH = {"Authorization": "Bearer testtoken"}

FIXTURES = Path(__file__).parent / "fixtures"


def _seg(source: str, start: str, end: str = "\nfunction ", first: bool = True) -> str:
    body = source.split(start)[1] if first else source.split(start)[-1]
    return body.split(end, 1)[0]


# -- 1. subtitle chips: highlight, unpick, and only what this video has -----

def test_a_picked_subtitle_chip_stays_lit_and_unpicks_on_the_second_click():
    seg = _seg(APP, "function renderSubsChips(")
    assert "chip.dataset.lang = lang" in seg, "chips carry their language"
    assert 'chip.classList.toggle("on", on)' in seg, \
        "a picked language shows as picked"
    assert 'chip.setAttribute("aria-pressed", on)' in seg, \
        "the highlight is announced, not just painted"
    # the second click takes the language OUT again
    assert "have.includes(lang)" in seg
    assert "have.filter((x) => x !== lang)" in seg, \
        "clicking a picked language removes it"
    assert "[...have, lang]" in seg, "clicking an unpicked one adds it"
    assert ".chip[aria-pressed=\"true\"]" in CSS, \
        "the picked state needs a style of its own"


def test_the_chip_list_opens_with_the_languages_people_want():
    seg = _seg(APP, "function renderSubsChips(")
    assert "navigator.language" in seg, \
        "the device's own language comes first, not Abkhazian"
    assert "k === \"en\"" in seg or '"en"' in seg
    # fourteen chips was a hard wall when the language lives at 100-something
    assert "SUBS_EXPANDED" in seg
    assert '"chip more"' in seg, "an expander for the rest of the list"
    assert "$(\"subsRow\").classList.toggle(\"hidden\", !all.length)" in seg


def test_a_stale_subtitle_pick_is_pruned_against_the_new_probe():
    probe = _seg(APP, "function renderProbe(")
    assert "syncSubLangsWithProbe(info)" in probe, \
        "the prune runs on every successful probe"
    seg = _seg(APP, "function syncSubLangsWithProbe(")
    assert "function pickedSubs(" in APP
    assert "available.includes(l)" in seg
    assert "not on this video" in seg, "a prune is said, not silent"
    assert "Object.keys(info.subtitles" in seg
    assert "Object.keys(info.automatic_captions" in seg


def test_a_missing_subtitle_language_does_not_block_the_download(tmp_path):
    """The engine must never refuse the video because of a subtitle wish
    (verified live against the dev engine, then pinned here)."""
    import suravidl_engine.api as api

    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(FIXTURES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        app = api.create_app(download_dir=tmp_path / "dl",
                             auth_token="testtoken", db_path=tmp_path / "jobs.db")
        with TestClient(app) as c:
            for mode in ("sidecar", "embed"):
                j = c.post("/jobs", headers=AUTH, json={
                    "url": f"{base}/tiny.mp4",
                    "overrides": {"subtitles_mode": mode,
                                  "subtitles_langs": "zz, en"},
                }).json()
                row: dict = {"status": "timeout"}
                for _ in range(150):
                    row = c.get(f"/jobs/{j['id']}", headers=AUTH).json()
                    if row["status"] in ("completed", "error", "cancelled"):
                        break
                    time.sleep(0.2)
                assert row["status"] == "completed", \
                    f"{mode}: the job must not fail on a missing language"
                assert "subtitle" not in (row.get("error") or "").lower()
    finally:
        srv.shutdown()

    assert list((tmp_path / "dl").glob("*.mp4")), "the video landed anyway"


# -- 2. the sound note only speaks when it is on ----------------------------

def test_no_sound_only_appears_when_the_box_is_ticked():
    assert "sound included" not in APP, \
        "the 'sound included' suffix is gone from every row"
    seg = _seg(APP, "function soundChoiceLabel()")
    assert '"video only — no sound"' in seg
    assert '"video only"' in seg, "unticked rows carry no sound note at all"


# -- 3. an unknown size explains itself on a phone --------------------------

def test_an_unknown_size_explains_itself_on_tap():
    seg = _seg(APP, "function sizeCell(")
    assert '"unknown"' in seg
    assert "td.title = why" in seg, "desktop keeps the hover note"
    assert "td.onclick = () => toast(why)" in seg, \
        "a phone has no hover — the explanation must survive a tap"
    assert "the site does not advertise a size" in seg


# -- 4. the quality chips belong under the title ----------------------------

def test_the_quality_chips_sit_below_the_title():
    assert 'id="qualityRow"' not in HTML.split('id="probeCard"')[0], \
        "the chips have left the paste card"
    card = HTML.split('id="probeCard"')[1].split('id="formats"')[0]
    assert 'id="qualityRow"' in card, "they live in the video card now"
    assert HTML.index('id="qualityRow"') > HTML.index('id="probeMeta"'), \
        "below the title"
    assert HTML.index('id="qualityRow"') < HTML.index('id="audioRow"'), \
        "and above the audio picks"


# -- 5. TikTok's intermittent refusal is retried ----------------------------

class _FlakyYDL:
    """Fails with the TikTok refusal for the first `fails` attempts."""

    def __init__(self, opts, fails=2, message=None):
        self.fails = fails
        self.message = message or (
            "ERROR: [TikTok] 7685267152395554066: Unexpected response from "
            "webpage request; please report this issue")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        type(self).calls.append(url)
        if type(self).calls and len(type(self).calls) <= self.fails:
            raise yt_dlp.utils.DownloadError(self.message)
        return {"id": "ok"}

    def sanitize_info(self, info):
        return info


def _install(monkeypatch, fails=2, message=None):
    _FlakyYDL.calls = []
    box = {}

    def build(opts):
        box["ydl"] = _FlakyYDL(opts, fails=fails, message=message)
        return box["ydl"]

    from suravidl_engine import extract
    monkeypatch.setattr(extract, "yt_dlp", types.SimpleNamespace(
        YoutubeDL=build, utils=yt_dlp.utils))
    return extract


def test_a_tiktok_refusal_is_retried_until_it_answers(monkeypatch):
    extract = _install(monkeypatch, fails=2)
    sleeps = []
    out = extract.extract_info({}, "https://www.tiktok.com/@x/video/1",
                               download=False, sleep=sleeps.append)
    assert out == {"id": "ok"}
    assert len(_FlakyYDL.calls) == 3, "two refusals, then the answer"
    assert sleeps == [0.8, 2.0], "a pause between attempts, not a hammer"
    assert extract.ATTEMPTS == 3


def test_other_failures_are_not_retried(monkeypatch):
    extract = _install(monkeypatch, fails=1,
                       message="ERROR: [youtube] xyz: This video is unavailable")
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://youtube.com/watch?v=x", download=True)
    assert len(_FlakyYDL.calls) == 1, "only TikTok's flake gets a second chance"


def test_a_persistent_tiktok_refusal_still_raises_after_the_attempts(monkeypatch):
    extract = _install(monkeypatch, fails=99)
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://www.tiktok.com/@x/video/1", download=False)
    assert len(_FlakyYDL.calls) == extract.ATTEMPTS


def test_probe_and_download_both_go_through_the_retrying_extractor():
    assert "from .extract import extract_info" in PROBE_SRC
    assert "extract_info(opts, url, download=False)" in PROBE_SRC
    assert "from .extract import extract_info" in JOBS_SRC
    assert 'extract_info(opts, job["url"], download=True)' in JOBS_SRC
    assert "with yt_dlp.YoutubeDL(" not in PROBE_SRC, \
        "no direct extraction outside the retrying wrapper (probe)"
    seg = JOBS_SRC.split("with yt_dlp.YoutubeDL(")
    assert len(seg) == 1, "no direct extraction outside the retrying wrapper (jobs)"


def test_a_tiktok_refusal_comes_back_with_a_next_step():
    from suravidl_engine.auth import explain_download_error

    raw = ("ERROR: [TikTok] 7685267152395554066: Unexpected response from "
           "webpage request; please report this issue")
    msg = explain_download_error(raw)
    assert msg.startswith(raw), "the raw words stay first, the hint is added"
    assert "Retry" in msg and "Find a video on a page" in msg
    # and nothing else changes: other errors are left exactly as yt-dlp said
    plain = "ERROR: Unsupported URL: https://example.invalid/x"
    assert explain_download_error(plain) == plain
    wall = "Sign in to confirm you're not a bot"
    assert "cookies" in explain_download_error(wall)
