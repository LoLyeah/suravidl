"""v0.40.1 "the dial" — multi-language audio: the probe's languages become a
chooser in the patch bay, the formats list stops collapsing language tracks,
and a video-only take pairs the chosen language (with a plain fallback).

RED first: the dial does not exist on 0.40.0.
"""
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text()
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text()


def _seg(source, start, end="\nfunction "):
    body = source.split(start)[1]
    return body.split(end, 1)[0]


def test_the_patch_bay_gains_an_audio_track_dial():
    assert 'id="audioLangRow"' in HTML
    assert 'id="audioLangChips"' in HTML
    assert "function renderAudioLangRow(" in APP
    assert "function audioLangs(" in APP


def test_the_dial_lists_the_languages_the_probe_actually_found():
    seg = _seg(APP, "function audioLangs(")
    assert "f.language" in seg, "the languages come from the formats"
    assert "hasVideo(f)" in seg and "!hasAudio(f)" in seg, \
        "only separate audio tracks count"


def test_the_dial_hides_when_there_is_nothing_to_choose():
    seg = _seg(APP, "function renderAudioLangRow(")
    assert "langs.length < 2" in seg, "one language is not a choice"
    assert 'classList.add("hidden")' in seg
    assert 'AUDIO_LANG = ""' in seg, \
        "a pick that the new video does not offer is dropped"


def test_a_video_only_take_pairs_the_chosen_language_with_a_fallback():
    spec = _seg(APP, "function fmtSpec(")
    assert '!$("noSound").checked' in spec, "the no-sound rule survives"
    assert "bestaudio[language=${lang}]" in spec, \
        "the filter yt-dlp understands"
    assert "]/${f.format_id}+bestaudio/best" in spec, \
        "a miss still yields the plain pair"
    assert ".replace(/[^A-Za-z0-9-]/g" in spec, \
        "only a language code ever lands in the format string"


def test_the_take_buttons_re_read_the_dial_when_clicked():
    assert "() => armTake(fmtSpec(f, separateAudio)" in APP, \
        "the pick used to be frozen at render time"


def test_the_formats_list_stops_collapsing_language_tracks():
    seg = _seg(APP, "function dedupeFormats(")
    assert "f.language" in seg, \
        "two dubs of one quality are two real choices"
    assert "fmt-lang" in APP, "a language track says which language it is"
    assert "renderAudioLangRow(info)" in APP, \
        "every probe refreshes the dial"


def test_the_language_filter_and_fallback_pick_the_dubbed_track():
    """The exact grammar fmtSpec emits — verified against yt-dlp's real
    selector, so a language pick can not silently become a lie.
    (Guard: passes before and after; it protects the grammar.)"""
    import yt_dlp

    base = {
        "id": "x", "title": "t", "webpage_url": "http://x/watch",
        "extractor": "generic", "extractor_key": "Generic",
        "formats": [
            {"format_id": "137", "url": "http://v", "vcodec": "avc1",
             "acodec": "none", "ext": "mp4", "height": 1080,
             "protocol": "https"},
            {"format_id": "140", "url": "http://a", "vcodec": "none",
             "acodec": "mp4a", "ext": "m4a", "language": "en",
             "protocol": "https"},
            {"format_id": "141", "url": "http://b", "vcodec": "none",
             "acodec": "mp4a", "ext": "m4a", "language": "hi",
             "protocol": "https"},
        ],
    }

    def pick(fmt, formats=None):
        ydl = yt_dlp.YoutubeDL({"quiet": True, "format": fmt})
        info = copy.deepcopy(base)
        if formats:
            info["formats"] = formats
        out = ydl.process_video_result(info, download=False)
        return [f["format_id"] for f in (out.get("requested_formats") or [out])]

    assert pick("137+bestaudio[language=hi]/137+bestaudio/best") == \
        ["137", "141"], "the chosen dub is the one paired"
    assert pick("137+bestaudio[language=xx]/137+bestaudio/best",
                formats=[base["formats"][0], base["formats"][1]]) == \
        ["137", "140"], "a language the site lacks falls back to the pair"
