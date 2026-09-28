"""v0.32.1 — regressions from the SECOND agy audit (run over the v0.32.0
tree). Six findings reproduced here before anything was fixed; each test
failed against `703c48a` with the behaviour the report described.

1. `/files/stream` built `Content-Disposition` from the raw file name: any
   non-latin-1 name (CJK, Cyrillic, emoji) crashed the response with a
   `UnicodeEncodeError` — the file could not be played or opened at all.
2. HLS estimation fetched whatever a playlist pointed at: `file:///…` read
   the local disk, link-local hosts (cloud metadata) were contacted. The
   main URL was always vetted; its playlist's URLs were not.
3. deleting a job removed ANY empty parent that was not the current download
   root — after a Settings folder change, the previous download folder went
   with the row.
4. `/jobs/{id}/retry` skipped `/jobs`' preset expansion: bundle presets died
   as "unknown preset: 'subs-en-sidecar'", and switching a preset job to a
   raw format tripped create's "not both" refusal.
5. a ranged probe answered 206 carries `Content-Length: 1` — the byte that
   was asked for — and the real size in `Content-Range`; the estimate read
   the 1 and the size came out as ~2 bytes.
6. subtitle sidecars: the srt convertor leaves `Name.en.srt` (the progress
   hook only ever saw the renamed-away `.vtt`), and language-tagged files
   share no stem with the video — deleting the job left them behind.

Five findings did NOT survive confirmation and have no test here: a
`_cmp_version` helper (no such code in the tree), an `exportForEngine` in
the cookie vault (no such function — the vault stores bytes and never parses
cookies), an api.py stem-prefix sidecar match (no such line), the opus mime
mapping (already present as `audio/ogg`), and the extension's fetch error
handling (both paths already guard and answer). The audit's line numbers
drifted from the tree it claimed to read; those five read as hallucinations.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from suravidl_engine.classify import Response, classify

AUTH = {"Authorization": "Bearer testtoken"}
ROOT = Path(__file__).resolve().parent.parent
MIME_HLS = "application/vnd.apple.mpegurl"


def _client(tmp_path, cache_dir=None):
    import suravidl_engine.api as api

    return TestClient(api.create_app(download_dir=tmp_path / "dl",
                                     auth_token="testtoken",
                                     cache_dir=cache_dir or tmp_path / "cache"))


def _app(tmp_path, **kw):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir(parents=True, exist_ok=True)
    kw.setdefault("auth_token", "testtoken")
    etc = {k: kw.pop(k) for k in ("settings_path",) if k in kw}
    return api.create_app(download_dir=d, db_path=tmp_path / "jobs.db",
                          **etc, **kw)


class MethodFetch:
    """(url, method) → Response; a (url, "*") route matches any method.
    Unlisted pairs are 404s. Records every call."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, headers, method, range_bytes):
        self.calls.append((method, url))
        got = (self.routes.get((url, method))
               or self.routes.get((url, "*")))
        if got is None:
            return Response(status=404, final_url=url, error="http 404")
        return got

    def urls(self):
        return [u for _m, u in self.calls]


MEDIA_8S = (b"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n"
            b"#EXTINF:4.0,\nseg1.ts\n#EXTINF:4.0,\nseg2.ts\n#EXT-X-ENDLIST\n")


# -- 1. a non-ascii file name crashed /files/stream -------------------------

def test_streaming_a_non_ascii_file_name_does_not_crash(tmp_path):
    with _client(tmp_path) as c:
        dl = tmp_path / "dl"
        dl.mkdir(parents=True, exist_ok=True)
        name = "视频 摘录.mp4"
        (dl / name).write_bytes(b"x" * 100)
        r = c.get("/files/stream", params={"path": name}, headers=AUTH)
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "filename*=UTF-8''" in cd, cd
        assert r.content == b"x" * 100


# -- 2. the estimator fetched whatever the playlist said ---------------------

def test_hls_estimation_never_fetches_a_file_url():
    base = "https://cdn.example/e/index.m3u8"
    seg2 = "https://cdn.example/e/seg2.ts"
    media = (b"#EXTM3U\n#EXTINF:4.0,\nfile:///etc/passwd\n"
             b"#EXTINF:4.0,\nseg2.ts\n")
    f = MethodFetch({
        (base, "*"): Response(200, {"Content-Type": MIME_HLS}, media, base),
        (seg2, "*"): Response(200, {"Content-Length": "40000"}, b"", seg2),
    })
    out = classify(base, fetch=f)
    assert not any(u.startswith("file:") for u in f.urls()), f.calls
    assert out["size"] == 40000, "the fetchable segment still measures the span"
    assert out["estimated"] is True


def test_a_master_pointing_at_a_local_file_is_refused():
    base = "https://cdn.example/m/master.m3u8"
    master = (b"#EXTM3U\n"
              b"#EXT-X-STREAM-INF:BANDWIDTH=2400000,RESOLUTION=1920x1080\n"
              b"file:///etc/hosts\n")
    f = MethodFetch({(base, "*"): Response(200, {"Content-Type": MIME_HLS},
                                           master, base)})
    out = classify(base, fetch=f)
    assert out["kind"] == "hls"
    assert out["size"] is None, "a variant that must not be fetched is refused"
    assert not any(u.startswith("file:") for u in f.urls()), f.calls


def test_a_link_local_segment_is_never_contacted():
    base = "https://cdn.example/l/index.m3u8"
    seg2 = "https://cdn.example/l/seg2.ts"
    media = (b"#EXTM3U\n"
             b"#EXTINF:4.0,\nhttp://169.254.169.254/latest/meta-data/\n"
             b"#EXTINF:4.0,\nseg2.ts\n")
    f = MethodFetch({
        (base, "*"): Response(200, {"Content-Type": MIME_HLS}, media, base),
        (seg2, "*"): Response(200, {"Content-Length": "30000"}, b"", seg2),
    })
    out = classify(base, fetch=f)
    assert not any("169.254.169.254" in u for u in f.urls()), f.calls
    assert out["size"] == 30000


# -- 3. delete removed an older download folder ------------------------------

def test_deleting_a_job_never_removes_an_older_download_folder(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    old_dir = Path(mgr.download_dir)
    f = old_dir / "old.mp4"
    f.write_bytes(b"video")
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x"},
                     headers=AUTH).json()["id"]
        with mgr._lock:
            j = mgr._jobs[jid]
            j["status"] = "completed"
            j["filepath"] = str(f)
            j["files"] = [str(f)]
            mgr._save(j)
        new_dir = tmp_path / "dl2"
        new_dir.mkdir()
        r = c.post("/settings", json={"download_dir": str(new_dir)},
                   headers=AUTH)
        assert r.status_code == 200, r.text
        r = c.post(f"/jobs/{jid}/delete", headers=AUTH)
        assert r.status_code == 200, r.text
        assert not f.exists()
        assert old_dir.is_dir(), "the previous download folder was deleted"


def test_deleting_still_prunes_its_own_empty_subfolder(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    sub = Path(mgr.download_dir) / "Some Playlist"
    sub.mkdir(parents=True)
    f = sub / "a.mp4"
    f.write_bytes(b"video")
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x"},
                     headers=AUTH).json()["id"]
        with mgr._lock:
            j = mgr._jobs[jid]
            j["status"] = "completed"
            j["filepath"] = str(f)
            j["files"] = [str(f)]
            mgr._save(j)
        assert c.post(f"/jobs/{jid}/delete", headers=AUTH).status_code == 200
        assert not f.exists()
        assert not sub.exists(), "the playlist's own folder should be pruned"
        assert Path(mgr.download_dir).is_dir()


# -- 4. retry skipped preset expansion, and tripped the lane refusal ---------

def _fail_it(mgr, jid):
    with mgr._lock:
        j = mgr._jobs[jid]
        j["status"] = "error"
        j["error"] = "boom"
        mgr._save(j)


def test_retrying_with_a_bundle_preset_works_like_the_first_queue(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x"},
                     headers=AUTH).json()["id"]
        _fail_it(mgr, jid)
        r = c.post(f"/jobs/{jid}/retry", headers=AUTH,
                   json={"preset": "subs-en-sidecar"})
        assert r.status_code == 200, r.text
        new = mgr.get(r.json()["id"])
        assert (new.get("overrides") or {}).get("subtitles_mode") == "sidecar"
        assert not new.get("preset")


def test_retrying_a_preset_job_with_a_format_switches_lanes(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x",
                                    "preset": "audio-mp3"},
                     headers=AUTH).json()["id"]
        _fail_it(mgr, jid)
        r = c.post(f"/jobs/{jid}/retry", headers=AUTH, json={"fmt": "bv*+ba/b"})
        assert r.status_code == 200, r.text
        new = mgr.get(r.json()["id"])
        assert new["fmt"] == "bv*+ba/b"
        assert not new.get("preset")


def test_retrying_a_format_job_with_a_preset_switches_lanes(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x",
                                    "fmt": "best"},
                     headers=AUTH).json()["id"]
        _fail_it(mgr, jid)
        r = c.post(f"/jobs/{jid}/retry", headers=AUTH,
                   json={"preset": "audio-mp3"})
        assert r.status_code == 200, r.text
        new = mgr.get(r.json()["id"])
        assert new["preset"] == "audio-mp3"
        assert not new.get("fmt")


def test_retrying_with_an_unknown_preset_answers_400(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x"},
                     headers=AUTH).json()["id"]
        _fail_it(mgr, jid)
        r = c.post(f"/jobs/{jid}/retry", headers=AUTH,
                   json={"preset": "no-such-preset"})
        assert r.status_code == 400, r.text
        assert "unknown preset" in r.json()["detail"]


# -- 5. a 206's Content-Length is the byte we asked for ----------------------

def test_a_ranged_probe_is_measured_by_its_content_range():
    base = "https://cdn.example/v2/index.m3u8"
    seg = "https://cdn.example/v2/seg1.ts"
    f = MethodFetch({
        (base, "*"): Response(200, {"Content-Type": MIME_HLS}, MEDIA_8S, base),
        (seg, "HEAD"): Response(405, {}, b"", seg),
        (seg, "GET"): Response(206, {"Content-Length": "1",
                                     "Content-Range": "bytes 0-0/75000"},
                             b"\x00", seg),
    })
    out = classify(base, fetch=f)
    assert out["size"] == 150000, "75000 B x an 8s span / a 4s segment"
    assert out["estimated"] is True


# -- 6. subtitle sidecars were left behind on delete --------------------------

def test_deleting_a_download_takes_language_tagged_subtitles_too(tmp_path):
    app = _app(tmp_path)
    mgr = app.state.manager
    dl = Path(mgr.download_dir)
    with TestClient(app) as c:
        jid = c.post("/jobs", json={"url": "http://example.com/x"},
                     headers=AUTH).json()["id"]
        (dl / "clip.mp4").write_bytes(b"v")
        (dl / "clip.en.srt").write_bytes(b"s")
        (dl / "clip.id.vtt").write_bytes(b"s")
        (dl / "clip.2.srt").write_bytes(b"x")      # not a language: spared
        with mgr._lock:
            j = mgr._jobs[jid]
            j["status"] = "completed"
            j["filepath"] = str(dl / "clip.mp4")
            j["files"] = [str(dl / "clip.mp4")]
            mgr._save(j)
        r = c.post(f"/jobs/{jid}/delete", headers=AUTH)
        assert r.status_code == 200, r.text
        assert not (dl / "clip.mp4").exists()
        assert not (dl / "clip.en.srt").exists()
        assert not (dl / "clip.id.vtt").exists()
        assert (dl / "clip.2.srt").exists(), "'.2' is not a language tag"
        assert dl.is_dir()


def test_the_run_records_subtitles_under_their_final_names(tmp_path):
    from suravidl_engine.jobs import _subtitle_files

    srt = tmp_path / "clip.en.srt"
    srt.write_text("1")
    gone = tmp_path / "clip.en.vtt"      # the convertor renamed and deleted it
    info = {"requested_subtitles": {"en": {"filepath": str(srt)},
                                    "id": {"filepath": str(gone)}}}
    assert _subtitle_files(info) == [str(srt)]
    assert _subtitle_files({}) == []


def test_both_run_branches_capture_subtitle_files():
    src = (ROOT / "src/suravidl_engine/jobs.py").read_text()
    assert src.count("_subtitle_files(") >= 3, "helper + both run branches"
    assert "_subtitle_files(info)" in src
    assert "_subtitle_files(e)" in src
