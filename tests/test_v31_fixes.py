"""v0.31.0 — the two cobalt ideas worth keeping (the ideas, not the code:
its `api/` is AGPL-3.0 and `web/` is CC-BY-NC, so nothing was copied).

1. **The transplant.** A download that dies on a signed link that expired
   mid-transfer is not a refusal — it's a stale URL. `retry_refresh=True`
   watches for bytes that had already arrived and, on an HTTP 403/410 after
   them, re-runs the extraction once for fresh links; yt-dlp's own `continuedl`
   resumes the `.part` from where it stopped. No bytes, no transplant: a
   refusal before any progress is the site's answer, passed through untouched.

2. **An estimated size for HLS.** A manifest never says how big the stream is,
   so `/classify` reads the playlist (the best variant of a master), takes ONE
   segment's size and multiplies by the playlist's duration span, and marks the
   verdict `estimated`. The shells show "HLS · ~42 MB"; an unmeasurable stream
   keeps its bare name.

Offline: fake YoutubeDL, fake fetches; one real HLS round trip over HTTP.
"""
import functools
import http.server
import threading
import types
from pathlib import Path

import pytest
import yt_dlp

from suravidl_engine import extract
from suravidl_engine.classify import Response, classify

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

# -- 1. the transplant -------------------------------------------------------

EXPIRED_MSG = "ERROR: unable to download video data: HTTP Error 403: Forbidden"


class _FlakyYDL:
    """Fails the first `fails` runs; `progress=True` reports bytes first."""

    def __init__(self, opts, fails=1, message=EXPIRED_MSG, progress=False):
        self.opts = opts
        self.fails = fails
        self.message = message
        self.progress = progress

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        type(self).calls.append(url)
        if len(type(self).calls) <= self.fails:
            if self.progress:
                for h in self.opts.get("progress_hooks") or []:
                    h({"status": "downloading", "downloaded_bytes": 1024,
                       "total_bytes": 4096})
            raise yt_dlp.utils.DownloadError(self.message)
        return {"id": "ok"}

    def sanitize_info(self, info):
        return info


def _install(monkeypatch, fails=1, message=EXPIRED_MSG, progress=False):
    _FlakyYDL.calls = []
    seen = {}

    def build(opts):
        seen["opts"] = opts
        return _FlakyYDL(opts, fails=fails, message=message, progress=progress)

    monkeypatch.setattr(extract, "yt_dlp", types.SimpleNamespace(
        YoutubeDL=build, utils=yt_dlp.utils))
    return seen


def test_a_download_that_died_on_an_expired_link_re_extracts_and_resumes(monkeypatch):
    _install(monkeypatch, fails=1, progress=True)
    sleeps, events = [], []
    opts = {"progress_hooks": [events.append]}
    out = extract.extract_info(opts, "https://www.instagram.com/reel/x",
                               download=True, retry_refresh=True,
                               sleep=sleeps.append)
    assert out == {"id": "ok"}
    assert len(_FlakyYDL.calls) == 2, "one refusal, then the fresh extraction"
    assert sleeps == [extract.REFRESH_PAUSE], "a beat, not an instant hammer"
    assert events and events[0]["downloaded_bytes"] == 1024, \
        "the caller's own hook still hears every progress event"
    assert opts["progress_hooks"] == [events.append], \
        "the caller's options are not mutated"


def test_a_refusal_before_any_progress_is_an_answer_not_a_transplant(monkeypatch):
    _install(monkeypatch, fails=1, progress=False)
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://x/a.mp4", download=True,
                             retry_refresh=True, sleep=lambda s: None)
    assert len(_FlakyYDL.calls) == 1, "no bytes arrived — nothing to resume onto"


def test_the_transplant_is_offered_once(monkeypatch):
    _install(monkeypatch, fails=99, progress=True)
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://x/a.mp4", download=True,
                             retry_refresh=True, sleep=lambda s: None)
    assert len(_FlakyYDL.calls) == 2, "one fresh extraction; no endless loop"


def test_a_plain_failure_is_not_transplanted(monkeypatch):
    _install(monkeypatch, fails=1, progress=True,
             message="ERROR: Unsupported URL: https://vidmonstr.com/e/z8")
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://vidmonstr.com/e/z8", download=True,
                             retry_refresh=True, sleep=lambda s: None)
    assert len(_FlakyYDL.calls) == 1, "only expired-link refusals get the refresh"


def test_probes_never_transplant(monkeypatch):
    seen = _install(monkeypatch, fails=1, progress=True)
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({"progress_hooks": []}, "https://x/a.mp4",
                             download=False, retry_refresh=True,
                             sleep=lambda s: None)
    assert len(_FlakyYDL.calls) == 1
    assert seen["opts"].get("progress_hooks") == [], "no watching on a probe"


def test_the_transplant_is_opt_in(monkeypatch):
    _install(monkeypatch, fails=1, progress=True)
    with pytest.raises(yt_dlp.utils.DownloadError):
        extract.extract_info({}, "https://x/a.mp4", download=True,
                             sleep=lambda s: None)
    assert len(_FlakyYDL.calls) == 1, "a caller must ask for the refresh"


def test_downloads_enable_the_transplant_and_probes_never_do():
    jobs_src = (ROOT / "src/suravidl_engine/jobs.py").read_text()
    assert ('extract_info(opts, job["url"], download=True, retry_refresh=True)'
            in jobs_src), "the engine's downloads opt into the refresh"
    probe_src = (ROOT / "src/suravidl_engine/probe.py").read_text()
    assert "retry_refresh" not in probe_src, "a probe has nothing to resume"


# -- 2. an estimated size for HLS --------------------------------------------

MIME_HLS = "application/vnd.apple.mpegurl"


class FakeFetch:
    """URL → Response; unlisted URLs are 404s. Records every call."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, headers, method, range_bytes):
        self.calls.append({"url": url, "method": method, "range": range_bytes})
        got = self.routes.get(url)
        if got is None:
            return Response(status=404, final_url=url, error="http 404")
        return got


MASTER = (b"#EXTM3U\n"
          b"#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=640x360\nlow/index.m3u8\n"
          b"#EXT-X-STREAM-INF:BANDWIDTH=2400000,RESOLUTION=1920x1080\nhi/index.m3u8\n")
MEDIA_8S = (b"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n"
            b"#EXTINF:4.0,\nseg1.ts\n#EXTINF:4.0,\nseg2.ts\n#EXT-X-ENDLIST\n")


def test_hls_size_is_one_segment_times_the_playlists_span():
    base = "https://cdn.example/hls/master.m3u8"
    hi = "https://cdn.example/hls/hi/index.m3u8"
    seg = "https://cdn.example/hls/hi/seg1.ts"
    f = FakeFetch({
        base: Response(200, {"Content-Type": MIME_HLS}, MASTER, base),
        hi: Response(200, {"Content-Type": MIME_HLS}, MEDIA_8S, hi),
        seg: Response(200, {"Content-Length": "150000",
                            "Content-Type": "video/mp2t"}, b"", seg),
    })
    out = classify(base, fetch=f)
    assert out["kind"] == "hls" and out["estimated"] is True
    assert out["size"] == 300000, "150000 B x an 8s span / a 4s segment"
    urls = [c["url"] for c in f.calls]
    assert hi in urls and seg in urls, "the best variant, then one segment"
    assert "low" not in " ".join(urls), "BANDWIDTH decides, not document order"
    assert urls.count(base) == 2, "the peek already held the whole master — no refetch"
    assert f.calls[-1]["method"] == "HEAD", "one segment is probed, never read"


def test_the_estimate_follows_the_duration_span_not_the_segment_count():
    base = "https://cdn.example/live/index.m3u8"
    seg = "https://cdn.example/live/seg-a.ts"
    media = (b"#EXTM3U\n#EXTINF:3.0,\nseg-a.ts\n#EXTINF:9.0,\nseg-b.ts\n"
             b"#EXT-X-ENDLIST\n")
    f = FakeFetch({
        base: Response(200, {"Content-Type": MIME_HLS}, media, base),
        seg: Response(200, {"Content-Length": "30000",
                            "Content-Type": "video/mp2t"}, b"", seg),
    })
    out = classify(base, fetch=f)
    assert out["size"] == 120000, "30000 B x a 12s span / a 3s segment"
    assert out["estimated"] is True


def test_a_manifest_that_cannot_be_measured_keeps_its_bare_name():
    base = "https://cdn.example/hls/master.m3u8"
    f = FakeFetch({base: Response(200, {"Content-Type": MIME_HLS}, MASTER, base)})
    out = classify(base, fetch=f)
    assert out["kind"] == "hls" and out["size"] is None
    assert out["estimated"] is False

    one = "https://cdn.example/one/index.m3u8"
    g = FakeFetch({one: Response(200, {"Content-Type": MIME_HLS}, MEDIA_8S, one)})
    out = classify(one, fetch=g)
    assert out["kind"] == "hls" and out["size"] is None
    assert out["estimated"] is False


def test_a_segment_without_a_head_length_is_measured_by_one_ranged_byte():
    base = "https://cdn.example/v/index.m3u8"
    seg = "https://cdn.example/v/seg1.ts"
    f = FakeFetch({
        base: Response(200, {"Content-Type": MIME_HLS}, MEDIA_8S, base),
        seg: Response(206, {"Content-Range": "bytes 0-0/75000"}, b"\x00", seg),
    })
    out = classify(base, fetch=f)
    assert out["size"] == 150000, "75000 B x an 8s span / a 4s segment"
    assert out["estimated"] is True
    assert f.calls[-1]["range"] == 1, "one byte, not the file"


def test_a_manifests_own_byte_length_is_not_the_streams_size():
    base = "https://cdn.example/hls/index.m3u8"
    seg = "https://cdn.example/hls/seg1.ts"
    f = FakeFetch({
        base: Response(200, {"Content-Type": MIME_HLS, "Content-Length": "65"},
                       MEDIA_8S, base),
        seg: Response(200, {"Content-Length": "150000",
                            "Content-Type": "video/mp2t"}, b"", seg),
    })
    out = classify(base, fetch=f)
    assert out["size"] == 300000, "the segment estimate, not the 65-byte manifest"
    assert out["estimated"] is True

    g = FakeFetch({base: Response(
        200, {"Content-Type": MIME_HLS, "Content-Length": "65"}, MEDIA_8S, base)})
    out = classify(base, fetch=g)
    assert out["size"] is None and out["estimated"] is False, \
        "unmeasurable: the manifest's own size is not an answer"


def test_every_verdict_carries_the_estimated_flag():
    f = FakeFetch({"https://x/a.mp4": Response(
        200, {"Content-Type": "video/mp4", "Content-Length": "123"}, b"",
        "https://x/a.mp4")})
    assert classify("https://x/a.mp4", fetch=f)["estimated"] is False
    assert classify("https://gone.example/a.mp4",
                    fetch=FakeFetch({}))["estimated"] is False


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_a_real_hls_fixture_reports_an_estimate(fixture_server):
    out = classify(f"{fixture_server}/hls/index.m3u8")
    assert out["kind"] == "hls" and out["estimated"] is True
    assert out["size"] == 2 * (FIXTURES / "hls/seg1.ts").stat().st_size


# -- the shells speak the same language --------------------------------------


def test_the_browser_shows_estimates_as_estimates():
    src = (ROOT / "android/app/src/main/java/com/suravidl/app/BrowserActivity.kt"
           ).read_text()
    assert 'if (v.optBoolean("estimated")) "~" else ""' in src
    assert '"$kind · $about${humanSize(size)}"' in src


def test_the_plan_documents_the_estimated_flag():
    doc = (ROOT / "docs/PLAN-android-sniffing.md").read_text()
    assert "estimated" in doc
