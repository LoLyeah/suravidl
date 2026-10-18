"""v0.47.3 "the legend" — labels from the manifest, and a card that stays away.

Two shelf-level bugs the field found. The popup's rows said "Playlist 1,
Playlist 2" because they were named from the URL, whose last token is
"video" or "native" — the resolution lives in the master's STREAM-INF and
the audio language in its EXT-X-MEDIA, so the engine now maps both
(/sniff/shape) and the popup labels from that answer. And the what's-new
card came back on every desktop launch: pywebview defaults to
private_mode=True (ephemeral storage), so the "seen" marker never survived
a restart — the shell now starts with persistent storage.
"""
import json
from pathlib import Path

from suravidl_engine.classify import manifest_shape

ROOT = Path(__file__).resolve().parents[1]

MASTER = (
    "#EXTM3U\n"
    '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",LANGUAGE="jpn",NAME="Native",'
    'DEFAULT=YES,AUTOSELECT=YES,URI="audio/native.m3u8"\n'
    '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",LANGUAGE="eng",NAME="English",'
    'DEFAULT=NO,AUTOSELECT=YES,URI="audio/english.m3u8"\n'
    '#EXT-X-STREAM-INF:BANDWIDTH=5184,RESOLUTION=1920x1080,AUDIO="audio"\n'
    "video.m3u8\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=2304,RESOLUTION=1280x720,AUDIO="audio"\n'
    "video-720p.m3u8\n"
)


class _Resp:
    def __init__(self, body, url="", status=200):
        self.body = body
        self.status = status
        self.headers = {}
        self.final_url = url
        self.error = ""

    def ok(self):
        return 200 <= self.status < 300


def test_manifest_shape_maps_variants_and_audio():
    """The master answers the question the URL cannot: which row is 1080p,
    which is a Japanese audio track, and where each lives."""
    def fetch(url, headers, method, n):
        return _Resp(MASTER.encode(), url)

    got = manifest_shape(["https://h/_v7/abc/master.m3u8"], fetch=fetch)
    it = got["items"][0]
    assert it["master"] is True
    assert [(v["url"], v["res"]) for v in it["variants"]] == [
        ("https://h/_v7/abc/video.m3u8", "1920x1080"),
        ("https://h/_v7/abc/video-720p.m3u8", "1280x720"),
    ]
    assert [a["name"] for a in it["audio"]] == ["Native", "English"]
    assert it["audio"][0]["lang"] == "jpn"
    assert it["audio"][0]["url"] == "https://h/_v7/abc/audio/native.m3u8"


def test_manifest_shape_is_silent_on_a_failure():
    """Labels are a courtesy: a gate or a dead host never raises."""
    def fetch(url, headers, method, n):
        raise OSError("gate")

    got = manifest_shape(["https://h/master.m3u8"], fetch=fetch)
    assert got["items"][0]["master"] is False
    assert got["items"][0]["variants"] == []


def test_the_engine_answers_the_shape_question():
    api = (ROOT / "src/suravidl_engine/api.py").read_text()
    assert '"/sniff/shape"' in api and "class ShapeRequest" in api
    assert "manifest_shape(" in api


def test_the_popup_labels_come_from_the_engine():
    """The rows must name themselves from the engine's manifest read, not
    from a URL token that says nothing (the 2026-10-18 field report)."""
    popup = (ROOT / "extension/popup.js").read_text()
    assert "function shapeChild(" in popup
    assert "function shapeMaster(" in popup
    assert 'type: "shape"' in popup
    bg = (ROOT / "extension/background.js").read_text()
    assert "function shapeWithEngine(" in bg
    assert '"/sniff/shape"' in bg
    shape_fn = bg.split("async function shapeWithEngine", 1)[1][:1400]
    assert "pkFor(tabId)" in shape_fn, "a scrambled master needs the key to parse"


def test_the_applier_never_refuses_silently():
    """The 2026-10-18 Windows report: "the applier refused to run" with no
    reason anywhere on the machine. Every refusal now carries its cause to
    the toast (verbatim) and to ~/.suravidl/update.log."""
    main = (ROOT / "src/suravidl_engine/__main__.py").read_text()
    assert "the updater could not start" in main
    assert "applier refused:" in main
    assert "the staged installer is gone" in main
    assert "_update_log_trail(" in main


def test_the_desktop_webview_keeps_its_storage():
    """The what's-new card returned on every desktop launch because
    pywebview's private_mode default is True — ephemeral storage, so the
    seen marker never survived a restart (the 2026-10-18 field report)."""
    main = (ROOT / "src/suravidl_engine/__main__.py").read_text()
    assert "private_mode=False" in main
    assert "storage_path" in main


def test_whatsnew_opens_with_this_release():
    from suravidl_engine import __version__, whatsnew

    top = whatsnew.ENTRIES[0]
    assert top["version"] == __version__, "ENTRIES[0] is the current version"
    assert len(whatsnew.ENTRIES) == 10
    # v0.47.4 "the minutes" — this round's entry stays among the living
    # ten (the strict current-version pin moved to that release's file)
    assert any(e["version"] == "0.47.3"
               and e["title"].lower() == "the legend"
               for e in whatsnew.ENTRIES)
    assert "0.46.13" not in [e["version"] for e in whatsnew.ENTRIES]


def test_the_extension_versions_agree():
    m = json.loads((ROOT / "extension/manifest.json").read_text())
    f = json.loads((ROOT / "extension/firefox/manifest.json").read_text())
    html = (ROOT / "extension/popup.html").read_text()
    assert m["version"] == f["version"] == "0.5.18"
    assert "v0.5.18" in html
