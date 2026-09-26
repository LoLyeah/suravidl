"""URL classification: what is this thing, before anyone downloads it?

Every shell's sniffer collects candidate URLs while the user watches — and an
ad creative is an .mp4 too, a page is not a video, and only a real round trip
(with the caller's own cookies) can tell them apart. That judgement lives in
the engine, once. These tests drive it with canned responses: no network.
"""
import re
from pathlib import Path

import pytest

from suravidl_engine.classify import Response, classify, media_regex, patterns

ROOT = Path(__file__).parent.parent


class FakeFetch:
    """A fake fetch that records every call; `result` may be a callable."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, url, headers, method, range_bytes):
        self.calls.append({"url": url, "headers": headers, "method": method,
                           "range": range_bytes})
        if callable(self.result):
            return self.result(url, headers, method)
        return self.result


def served(mime, body=b"", status=200):
    """A fetch that always answers the same thing for any URL."""
    return FakeFetch(lambda u, h, m: Response(
        status=status, headers={"Content-Type": mime} if mime else {},
        body=body, final_url=u))


def hls_body(extra=b""):
    return (b"#EXTM3U\n#EXT-X-VERSION:3\n" + extra
            + b"#EXTINF:2.0,\nseg1.ts\n#EXT-X-ENDLIST\n")


def test_head_first_then_a_ranged_get_when_head_says_no():
    def result(url, headers, method):
        if method == "HEAD":
            return Response(status=405, final_url=url)
        return Response(status=206,
                        headers={"Content-Type": "video/mp4",
                                 "Content-Range": "bytes 0-4095/999999"},
                        body=b"\x00\x00\x00\x18ftypmp42", final_url=url)

    f = FakeFetch(result)
    out = classify("https://cdn.example/a.mp4", fetch=f)
    assert [c["method"] for c in f.calls] == ["HEAD", "GET"]
    assert f.calls[1]["range"] == 4096, "the peek must be bounded"
    assert out["kind"] == "video"
    assert out["size"] == 999999, "size comes from Content-Range, not the peek"


def test_hls_manifest_is_hls():
    out = classify("https://cdn.example/master.m3u8",
                   fetch=served("application/vnd.apple.mpegurl", hls_body()))
    assert out["kind"] == "hls" and out["drm"] is False


def test_aes128_hls_is_not_drm():
    """The one that matters: an ordinary encrypted HLS is still downloadable."""
    body = hls_body(b'#EXT-X-KEY:METHOD=AES-128,URI="https://cdn.example/k.bin"\n')
    out = classify("https://cdn.example/index.m3u8",
                   fetch=served("application/x-mpegURL", body))
    assert out["kind"] == "hls" and out["drm"] is False


def test_sample_aes_hls_is_drm():
    body = hls_body(b'#EXT-X-KEY:METHOD=SAMPLE-AES,URI="skd://key",'
                    b'KEYFORMAT="com.apple.streamingkeydelivery"\n')
    out = classify("https://cdn.example/drm.m3u8",
                   fetch=served("application/vnd.apple.mpegurl", body))
    assert out["kind"] == "drm" and out["drm"] is True
    assert "sample-aes" in out["note"]


def test_dash_manifest_is_dash_and_widevine_makes_it_drm():
    plain = (b'<?xml version="1.0"?><MPD xmlns="urn:mpeg:dash:schema:mpd:2011">'
             b'<Period><AdaptationSet/></Period></MPD>')
    wide = (b'<?xml version="1.0"?><MPD><Period><AdaptationSet>'
            b'<ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"/>'
            b'</AdaptationSet></Period></MPD>')
    out = classify("https://cdn.example/m.mpd", fetch=served("application/dash+xml", plain))
    assert out["kind"] == "dash" and out["drm"] is False
    out = classify("https://cdn.example/m.mpd", fetch=served("application/dash+xml", wide))
    assert out["kind"] == "drm" and "widevine" in out["note"]


def test_kind_from_mime_then_from_bytes_then_from_the_extension():
    out = classify("https://cdn.example/no-extension",
                   fetch=served("application/octet-stream", b"\x00\x00\x00\x18ftypisom"))
    assert out["kind"] == "video"

    # a mime that lies, and bytes that do not
    out = classify("https://cdn.example/watch",
                   fetch=served("text/plain", b"#EXTM3U\n#EXTINF:2.0,\nseg.ts\n"))
    assert out["kind"] == "hls"

    # nothing to go on but the URL
    out = classify("https://cdn.example/clip.mp4", fetch=served("", b""))
    assert out["kind"] == "video"


def test_pages_images_and_audio_are_named():
    assert classify("https://x/page", fetch=served("text/html"))["kind"] == "page"
    assert classify("https://x/a.jpg", fetch=served("image/jpeg"))["kind"] == "image"
    assert classify("https://x/a.mp3", fetch=served("audio/mpeg"))["kind"] == "audio"


def test_a_segment_knows_it_is_a_segment():
    out = classify("https://cdn.example/seg-42.ts", fetch=served("", b""))
    assert out["kind"] == "video" and "manifest" in out["note"]


def test_the_callers_headers_reach_the_fetch():
    f = served("video/mp4")
    classify("https://cdn.example/a.mp4",
             headers={"Cookie": "sid=1", "Referer": "https://site/e/1"}, fetch=f)
    assert f.calls[0]["headers"]["Cookie"] == "sid=1"
    assert f.calls[0]["headers"]["Referer"] == "https://site/e/1"


def test_the_final_url_survives_a_redirect():
    f = FakeFetch(lambda u, h, m: Response(status=200,
                                           headers={"Content-Type": "video/mp4"},
                                           body=b"",
                                           final_url="https://cdn2.example/real.mp4"))
    assert classify("https://cdn.example/go", fetch=f)["final_url"] == "https://cdn2.example/real.mp4"


def test_a_non_http_scheme_is_refused():
    with pytest.raises(ValueError):
        classify("file:///etc/passwd")


def test_a_dead_url_is_unknown_not_an_exception():
    f = FakeFetch(lambda u, h, m: Response(status=0, body=b"", final_url="",
                                           error="connection refused"))
    out = classify("https://gone.example/a.mp4", fetch=f)
    assert out["kind"] == "unknown" and "refused" in out["note"]


def test_a_refusal_is_explained_not_just_named():
    """A 403 from a page is usually 'bring the browser's cookies'."""
    f = FakeFetch(lambda u, h, m: Response(status=403, final_url=u,
                                           error="http 403"))
    out = classify("https://blocked.example/watch", fetch=f)
    assert out["kind"] == "unknown"
    assert "403" in out["note"] and "cookie" in out["note"]


def test_fairplay_is_detected_even_under_an_ordinary_method():
    """The docs promise FairPlay is refused. A playlist can name the key system
    in KEYFORMAT while using METHOD=AES-128, so the KEYFORMAT has to decide."""
    body = (b"#EXTM3U\n"
            b'#EXT-X-KEY:METHOD=AES-128,URI="https://keys.example/k",'
            b'KEYFORMAT="com.apple.streamingkeydelivery"\n'
            b"#EXTINF:4.0,\nseg.ts\n")
    out = classify("https://cdn.example/film.m3u8",
                   fetch=served("application/vnd.apple.mpegurl", body))
    assert out["kind"] == "drm" and out["drm"] is True


def test_a_metadata_address_is_not_fetched():
    """A page can smuggle a URL into the pipeline; the engine must not poke the
    cloud metadata service on its behalf."""
    def must_not_run(*a, **k):
        raise AssertionError("the engine reached for a link-local address")

    out = classify("http://169.254.169.254/latest/meta-data/", fetch=must_not_run)
    assert out["kind"] == "unknown" and "link-local" in out["note"]


def test_a_lan_address_is_still_fetched():
    """The boundary is deliberate and narrow: a NAS is a fine place to keep
    films, so private ranges stay reachable."""
    f = served("video/mp4", b"\x00\x00\x00\x18ftypisom")
    out = classify("http://192.168.1.50/film.mp4", fetch=f)
    assert out["kind"] == "video" and f.calls


def test_the_real_fetch_asks_like_a_browser_and_lets_callers_override():
    from suravidl_engine.classify import DEFAULT_UA, _headers_with_defaults

    assert DEFAULT_UA.startswith("Mozilla/5.0")
    assert _headers_with_defaults(None)["User-Agent"] == DEFAULT_UA
    got = _headers_with_defaults({"user-agent": "Custom/1.0", "Cookie": "a=1"})
    assert got["user-agent"] == "Custom/1.0", "the caller's headers win"
    assert "Cookie" in got
    assert list(got).count("User-Agent") == 0, "and are not duplicated"


def test_the_prefilter_list_has_one_owner():
    """M4: the extension fetches the engine's list (`/sniff/patterns`). The
    baked-in fallback exists only for "the engine is not up yet", so keep it a
    subset — a shell may look at fewer URLs than the engine, never at more."""
    js = (ROOT / "extension/background.js").read_text()
    assert '"/sniff/patterns"' in js, "the extension must fetch the engine's list"
    m = re.search(r"FALLBACK_EXT = \[([^\]]+)\]", js)
    assert m, "extension fallback list not found — did it move?"
    fallback = set(re.findall(r'"([a-z0-9]+)"', m.group(1)))
    assert fallback, "no extensions found in the fallback list"
    assert fallback <= set(patterns()["ext"])


def test_patterns_are_usable_by_a_shell():
    body = patterns()
    assert {"m3u8", "mp4", "ts"} <= set(body["ext"])
    assert body["hints"], "a hint list keeps extension-less streams visible"
    rx = media_regex()
    assert rx.search("https://x/a.M3U8?t=1")
    assert rx.search("https://x/a.mp4")
    assert not rx.search("https://x/page.html")
