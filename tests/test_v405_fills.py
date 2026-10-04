"""v0.40.5 "the fill" — two honest reads at the desk:
  * quality chips say what each pick will weigh (the site's own sizes, added
    the way the pick works) — engine-computed, per probe;
  * the batch line says exactly what it counted, live — links AND the lines
    it skipped.
RED first: both are silent on 0.40.4.
"""
import functools
import http.server
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text()
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text()
FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer testtoken"}


def _seg(source, start, end="\nfunction "):
    body = source.split(start)[1]
    return body.split(end, 1)[0]


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_the_estimate_adds_up_the_sites_own_sizes():
    from suravidl_engine.download_opts import quality_estimates

    fmts = [
        {"format_id": "137", "vcodec": "avc1", "acodec": "none",
         "height": 1080, "filesize": 100_000_000},
        {"format_id": "136", "vcodec": "avc1", "acodec": "none",
         "height": 720, "filesize": 50_000_000},
        {"format_id": "140", "vcodec": "none", "acodec": "mp4a",
         "abr": 128, "filesize": 3_000_000},
        {"format_id": "18", "vcodec": "avc1", "acodec": "mp4a",
         "height": 360, "filesize": 5_000_000},
    ]
    est = quality_estimates(fmts)
    assert est["1080"] == 103_000_000     # tallest <= 1080 + the best audio
    assert est["720"] == 53_000_000
    assert est["480"] == 5_000_000        # the muxed row carries its own sound
    assert est["1440"] == 103_000_000     # nothing taller than 1080 exists
    assert est["best"] == 103_000_000


def test_unknown_sizes_leave_a_quality_unpriced():
    from suravidl_engine.download_opts import quality_estimates

    fmts = [{"format_id": "137", "vcodec": "avc1", "acodec": "none",
             "height": 1080}]
    assert quality_estimates(fmts) == {}, \
        "an estimate that is really a guess is worse than none"


def test_the_probe_serves_the_estimates(fixture_server, tmp_path):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir()
    app = api.create_app(download_dir=d, auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        info = c.post("/probe", json={"url": f"{fixture_server}/tiny.mp4"},
                      headers=AUTH).json()
    assert isinstance(info.get("quality_estimates"), dict), \
        "every probe answer carries the map (possibly empty, never absent)"


def test_the_ui_renders_what_each_quality_weighs():
    assert "let QUALITY_EST = {};" in APP
    assert "QUALITY_EST = info.quality_estimates || {};" in APP
    seg = _seg(APP, "function renderQualityRow(")
    assert "QUALITY_EST[" in seg
    assert '"qsize"' in seg
    assert "humanBytes(est)" in seg
    assert "#qualityBtns .qsize" in CSS


def test_the_batch_line_names_what_it_skipped():
    assert "function pastedTokens(" in APP
    seg = _seg(APP, "function renderBatchRow(")
    assert "pastedTokens()" in seg and "pastedUrls()" in seg
    assert "skipped — not" in seg, "a skipped line is named, not uncounted"
    assert 'urls.length === 1' in seg and 't("1 link") : t("{n} links", { n: urls.length })' in seg, "one link is one link"
    assert "over || urls.length < 2" in seg, \
        "one link is not a batch — the button stays off"
    assert "only 20 fit in one batch" in seg, "the cap still speaks"
