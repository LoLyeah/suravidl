"""Per-site format memory (M20).

Picking "720p" for a site is also a preference: the engine remembers it and
offers it again next time the same site is probed. It is only ever an offer —
a remembered pick never changes what a download actually uses, and an
arbitrary format expression teaches the engine nothing.
"""
import functools
import http.server
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from suravidl_engine import settings as settings_mod
from suravidl_engine import site_memory
from suravidl_engine.download_opts import QUALITY_PRESETS

FIXTURES = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Bearer testtoken"}


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture()
def client(tmp_path):
    import suravidl_engine.api as api

    d = tmp_path / "dl"
    d.mkdir()
    app = api.create_app(download_dir=d, auth_token="testtoken",
                         db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        yield c


def _fmt(key: str) -> str:
    return next(p["fmt"] for p in QUALITY_PRESETS if p["key"] == key)


def test_a_quality_pick_is_remembered_for_the_site(client, fixture_server):
    url = f"{fixture_server}/video-test.html"
    r = client.post("/jobs", json={"url": url, "fmt": _fmt("720")}, headers=AUTH)
    assert r.status_code == 200, r.text

    stored = client.get("/settings", headers=AUTH).json()["site_quality"]
    assert stored == {"127.0.0.1": "720"}


def test_only_a_known_quality_is_remembered(client, fixture_server):
    """A hand-written expression is a one-off, not a preference."""
    url = f"{fixture_server}/video-test.html"
    for fmt in ["bv*[ext=mp4]+ba[ext=m4a]/b", "worst", "height<=361", ""]:
        r = client.post("/jobs", json={"url": url, "fmt": fmt}, headers=AUTH)
        assert r.status_code == 200, r.text
    assert client.get("/settings", headers=AUTH).json()["site_quality"] == {}

    # an audio-only job says nothing about video quality
    r = client.post("/jobs", json={"url": url, "preset": "audio-m4a"}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert client.get("/settings", headers=AUTH).json()["site_quality"] == {}


def test_the_probe_offers_the_remembered_quality(client, fixture_server):
    url = f"{fixture_server}/video-test.html"
    client.post("/jobs", json={"url": url, "fmt": _fmt("480")}, headers=AUTH)

    info = client.post("/probe", json={"url": url}, headers=AUTH).json()
    assert info["site"] == "127.0.0.1"
    assert info["site_quality"] == "480"

    # a playlist URL on the same host gets the same offer
    pl = client.post("/probe", json={"url": f"{fixture_server}/playlist.html?x=2"},
                     headers=AUTH).json()
    assert pl["playlist"] is True and pl["site_quality"] == "480"


def test_a_site_with_no_pick_reports_nothing(fixture_server, tmp_path):
    """No memory must be an honest null, never a guessed default."""
    import suravidl_engine.api as api

    d = tmp_path / "fresh"
    d.mkdir()
    with TestClient(api.create_app(download_dir=d, auth_token="testtoken",
                                   db_path=tmp_path / "fresh.db")) as c:
        info = c.post("/probe", json={"url": f"{fixture_server}/video-test.html"},
                      headers=AUTH).json()
        assert info["site"] == "127.0.0.1"
        assert info.get("site_quality") is None


@pytest.mark.parametrize("url,expected", [
    ("https://www.example.com/watch?v=1", "example.com"),
    ("http://example.com/", "example.com"),
    ("https://m.youtube.com/watch?v=1", "m.youtube.com"),   # a subdomain is its own site
    ("https://WWW.YouTube.COM/watch?v=1", "youtube.com"),
    ("http://127.0.0.1:8891/tiny.mp4", "127.0.0.1"),
    ("not a url", None),
    ("file:///tmp/x.mp4", None),
    ("", None),
])
def test_the_site_of_a_url(url, expected):
    assert site_memory.host_of(url) == expected


def test_settings_validation_cleans_the_memory():
    """Junk must never reach the file: unknown qualities and fake hosts drop."""
    cleaned = settings_mod.Settings._validate("site_quality", {
        "youtube.com": "720",
        "WWW.Example.COM": "best",   # normalized; the last entry wins
        "bad host": "1080",          # a space → not a host
        "nope.example": "360",       # 360 is not one of our qualities
    })
    assert cleaned == {"youtube.com": "720", "example.com": "best"}

    with pytest.raises(ValueError):
        settings_mod.Settings._validate("site_quality", ["youtube.com"])


def test_the_memory_is_bounded_and_the_oldest_site_goes_first():
    mapping = {f"site{i}.example": "720" for i in range(site_memory.MAX_SITES + 5)}
    cleaned = site_memory.clean(mapping)
    assert len(cleaned) == site_memory.MAX_SITES
    assert "site0.example" not in cleaned            # oldest evicted
    assert f"site{site_memory.MAX_SITES + 4}.example" in cleaned


def test_a_job_override_cannot_touch_the_memory():
    with pytest.raises(ValueError):
        settings_mod.validate_overrides({"site_quality": {"youtube.com": "1080"}})


def test_every_quality_preset_maps_back_to_its_own_key():
    from suravidl_engine.download_opts import QUALITY_BY_FMT

    assert len(QUALITY_BY_FMT) == len(QUALITY_PRESETS)
    for p in QUALITY_PRESETS:
        assert QUALITY_BY_FMT[p["fmt"]] == p["key"]
