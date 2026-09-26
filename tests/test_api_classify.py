"""The /classify and /sniff/patterns endpoints, and the "unsupported" answer.

Offline: a local fixture server provides real bytes over real HTTP.
"""
import functools
import http.server
import re
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture()
def client(tmp_path):
    import suravidl_engine.api as api

    app = api.create_app(download_dir=tmp_path, auth_token="testtoken")
    with TestClient(app) as c:
        yield c


AUTH = {"Authorization": "Bearer testtoken"}


def test_classify_requires_auth(client):
    assert client.post("/classify", json={"url": "https://x/a.mp4"}).status_code == 401


def test_classify_reads_a_real_manifest_over_http(client, fixture_server):
    r = client.post("/classify", json={"url": f"{fixture_server}/hls/index.m3u8"},
                    headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "hls" and body["drm"] is False
    assert body["mime"].startswith("application")


def test_classify_reads_a_real_mp4_over_http(client, fixture_server):
    r = client.post("/classify", json={"url": f"{fixture_server}/tiny.mp4"},
                    headers=AUTH)
    assert r.json()["kind"] == "video"
    assert r.json()["size"] and r.json()["size"] > 0


def test_classify_refuses_a_non_http_url(client):
    r = client.post("/classify", json={"url": "file:///etc/passwd"}, headers=AUTH)
    assert r.status_code == 400


def test_sniff_patterns_requires_auth_and_is_usable(client):
    assert client.get("/sniff/patterns").status_code == 401
    body = client.get("/sniff/patterns", headers=AUTH).json()
    assert {"m3u8", "mp4", "ts"} <= set(body["ext"])
    assert re.compile(body["regex"], re.I).search("https://x/a.M3U8?t=1")


def test_unsupported_probe_answers_with_a_hint(client, monkeypatch):
    import suravidl_engine.api as api

    def boom(*a, **k):
        raise Exception("ERROR: Unsupported URL: https://vidmonstr.com/e/z8")

    monkeypatch.setattr(api, "probe", boom)
    r = client.post("/probe", json={"url": "https://vidmonstr.com/e/z8"},
                    headers=AUTH)
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["unsupported"] is True
    assert "browser" in d["hint"]
    assert "Unsupported URL" in d["message"]


def test_an_ordinary_probe_error_stays_a_plain_string(client, monkeypatch):
    import suravidl_engine.api as api

    def boom(*a, **k):
        raise Exception("ERROR: unable to download webpage: HTTP Error 404")

    monkeypatch.setattr(api, "probe", boom)
    r = client.post("/probe", json={"url": "https://x/gone"}, headers=AUTH)
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], str)
