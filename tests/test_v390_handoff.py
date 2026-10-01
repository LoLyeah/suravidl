"""v0.39.0 — browser handoffs: the extension's find becomes a probe the user
finishes in the app.

The popup hands over what a page was playing; the engine probes it *here*,
with the captured request headers, and holds the result until a suravidl
window picks it up. The quality choice therefore happens in the app (where
the formats are real), the extension stays a doorman, and captured cookies
never leave the engine: reads never include headers, and a job started from
a handoff reuses them server-side via `handoff_id`.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    from suravidl_engine.api import create_app

    seen = {"calls": []}

    def stub_probe(url, headers):
        seen["calls"].append({"url": url, "headers": dict(headers or {})})
        if "bad-one" in url:
            raise RuntimeError("yt-dlp says no")
        return {"title": "A Take", "extractor": "generic", "formats": [
            {"format_id": "hls-720", "ext": "mp4", "height": 720,
             "filesize": 1234}]}

    app = create_app(download_dir=tmp_path / "dl", auth_token="t",
                     handoff_probe_fn=stub_probe)
    with TestClient(app) as c:
        c.seen = seen
        yield c


AUTH = {"Authorization": "Bearer t"}


def _wait_ready(c, hid, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        items = c.get("/handoff", headers=AUTH).json()["items"]
        for it in items:
            if it["id"] == hid and it["status"] != "probing":
                return it
        time.sleep(0.02)
    raise AssertionError("handoff never left 'probing'")


def test_a_handoff_becomes_a_ready_probe(client):
    r = client.post("/handoff", headers=AUTH, json={
        "url": "https://cdn.example/watch/playlist.m3u8",
        "urls": ["https://cdn.example/watch/playlist.m3u8"],
        "headers": {"cookie": "sid=1", "user-agent": "UA"},
        "tab_url": "https://cdn.example/watch",
    })
    assert r.status_code == 200 and r.json()["ok"] is True
    hid = r.json()["id"]
    item = _wait_ready(client, hid)
    assert item["status"] == "ready"
    assert item["probe"]["title"] == "A Take"
    assert item["resolved_url"] == "https://cdn.example/watch/playlist.m3u8"
    # the probe ran engine-side, with the captured headers
    call = client.seen["calls"][0]
    assert call["headers"]["cookie"] == "sid=1"


def test_handoff_reads_never_leak_headers(client):
    """Cookies are credentials: GET /handoff carries the probe, never them."""
    r = client.post("/handoff", headers=AUTH, json={
        "url": "https://cdn.example/a.m3u8",
        "headers": {"cookie": "session=SECRET-VALUE"},
    })
    hid = r.json()["id"]
    _wait_ready(client, hid)
    body = client.get("/handoff", headers=AUTH).text
    assert "SECRET-VALUE" not in body
    assert "cookie" not in body.lower()


def test_a_probe_payload_never_carries_the_captured_secrets(tmp_path):
    """yt-dlp records the headers it used — `http_headers`, and the cookie
    line as `cookies`, inside the info dict AND inside every format entry.
    A handoff is readable by any shell, so those keys come off before
    storage: the captures live engine-side for the job and nowhere a reader
    can see them."""
    from suravidl_engine.api import create_app

    def stub_probe(url, headers):
        return {"title": "t", "http_headers": {"Cookie": "sid=42"},
                "formats": [{"format_id": "f1", "cookies": "sid=42; Domain=x",
                             "ext": "mp4"}]}

    app = create_app(download_dir=tmp_path / "dl", auth_token="t",
                     handoff_probe_fn=stub_probe)
    with TestClient(app) as c:
        hid = c.post("/handoff", headers=AUTH,
                     json={"url": "https://cdn.example/x.m3u8"}).json()["id"]
        _wait_ready(c, hid)
        text = c.get("/handoff", headers=AUTH).text
        assert "sid=42" not in text
        assert "http_headers" not in text
        # nothing a shell needs was lost with the secrets
        item = [i for i in c.get("/handoff", headers=AUTH).json()["items"]
                if i["id"] == hid][0]
        assert item["probe"]["title"] == "t"
        assert item["probe"]["formats"][0]["format_id"] == "f1"


def test_the_probe_endpoint_scrubs_the_same_way(tmp_path, monkeypatch):
    """The UI's own probe answer travels the same scrub: a payload shown by
    a shell must not embed the credentials the engine used."""
    import suravidl_engine.api as api_mod
    from suravidl_engine.api import create_app

    monkeypatch.setattr(api_mod, "probe", lambda url, **kw: {
        "title": "t", "http_headers": {"Cookie": "sid=42"},
        "formats": [{"cookies": "sid=42"}]})
    app = create_app(download_dir=tmp_path / "dl", auth_token="t")
    with TestClient(app) as c:
        r = c.post("/probe", headers=AUTH, json={"url": "https://cdn.example/x"})
    assert r.status_code == 200
    assert "sid=42" not in r.text and "http_headers" not in r.text
    assert r.json()["title"] == "t"


def test_scrub_secrets_is_safe_on_every_json_shape():
    from suravidl_engine.probe import scrub_secrets

    payload = {"a": 1, "http_headers": {"Cookie": "s"}, "none": None, "formats": [
        {"cookies": "s", "id": "f"}, [{"cookies": "s", "id": "g"}]]}
    out = scrub_secrets(payload)
    assert out["a"] == 1 and out["none"] is None
    assert "http_headers" not in out
    assert out["formats"][0]["id"] == "f"
    assert out["formats"][0].get("cookies") is None
    assert out["formats"][1][0]["id"] == "g"
    assert scrub_secrets("plain") == "plain"
    assert scrub_secrets(None) is None


def test_a_probe_that_fails_falls_through_the_candidates(client):
    r = client.post("/handoff", headers=AUTH, json={
        "url": "https://cdn.example/bad-one.m3u8",
        "urls": ["https://cdn.example/bad-one.m3u8",
                 "https://cdn.example/good-two.m3u8"],
    })
    item = _wait_ready(client, r.json()["id"])
    assert item["status"] == "ready"
    assert item["resolved_url"] == "https://cdn.example/good-two.m3u8"
    assert [c["url"] for c in client.seen["calls"]] == [
        "https://cdn.example/bad-one.m3u8",
        "https://cdn.example/good-two.m3u8"]


def test_when_every_candidate_fails_the_handoff_says_so(client):
    r = client.post("/handoff", headers=AUTH, json={
        "url": "https://cdn.example/bad-one.m3u8"})
    item = _wait_ready(client, r.json()["id"])
    assert item["status"] == "failed" and "yt-dlp says no" in item["error"]


def test_ack_clears_it(client):
    r = client.post("/handoff", headers=AUTH, json={
        "url": "https://cdn.example/c.m3u8"})
    hid = r.json()["id"]
    _wait_ready(client, hid)
    assert client.post("/handoff/ack", headers=AUTH,
                       json={"id": hid}).json()["ok"] is True
    assert all(it["id"] != hid for it in
               client.get("/handoff", headers=AUTH).json()["items"])


def test_headers_reach_the_manager(tmp_path, monkeypatch):
    """`handoff_id` on a job merges the captured headers into the download."""
    import suravidl_engine.api as api_mod

    calls = []

    class Manager:
        def __init__(self, *a, **k):
            self.download_dir = tmp_path

        def create(self, url, **kw):
            calls.append(kw)
            return {"id": "j9", "url": url, "status": "queued", "title": "t",
                    "filepath": None}

        def list(self):
            return []

        def get(self, jid):
            return None

        def cancel(self, jid):
            return None

    monkeypatch.setattr(api_mod, "JobManager", Manager)
    app = api_mod.create_app(download_dir=tmp_path / "dl", auth_token="t",
                             handoff_probe_fn=lambda u, h: {"formats": []})
    with TestClient(app) as c:
        hid = c.post("/handoff", headers=AUTH, json={
            "url": "https://cdn.example/x.mp4",
            "headers": {"cookie": "sid=42"},
        }).json()["id"]
        _wait_ready(c, hid)
        r = c.post("/jobs", headers=AUTH, json={
            "url": "https://cdn.example/x.mp4", "handoff_id": hid})
        assert r.status_code == 200
        # an unknown id (expired, or another window acked first) is no error:
        # the job runs with whatever headers the request itself carried
        r2 = c.post("/jobs", headers=AUTH, json={
            "url": "https://cdn.example/x.mp4", "handoff_id": "nope"})
        assert r2.status_code == 200
    assert calls[0].get("extra_headers", {}).get("cookie") == "sid=42"
    assert not calls[1].get("extra_headers")   # unknown id: no merge, no error


def test_focus_action(client):
    from suravidl_engine.api import create_app
    import tempfile, pathlib

    called = []
    tmp = pathlib.Path(tempfile.mkdtemp())
    app = create_app(download_dir=tmp / "dl", auth_token="t",
                     desktop_actions={"focus": lambda: called.append(1)},
                     handoff_probe_fn=lambda u, h: {})
    with TestClient(app) as c:
        assert c.post("/app/focus", headers=AUTH).status_code == 200
    assert called == [1]

    app2 = create_app(download_dir=tmp / "dl2", auth_token="t",
                      handoff_probe_fn=lambda u, h: {})
    with TestClient(app2) as c:
        assert c.post("/app/focus", headers=AUTH).status_code == 501  # no shell


def test_store_expiry_and_dedupe():
    from suravidl_engine.handoff import HandoffStore

    clock = {"t": 1000.0}
    store = HandoffStore(probe_fn=lambda u, h: {"ok": True},
                         now=lambda: clock["t"])
    a = store.add("https://x/1.m3u8")
    b = store.add("https://x/1.m3u8")          # same click, same handoff
    assert a["id"] == b["id"]
    clock["t"] += 31 * 60                      # half an hour later
    assert store.list() == []


def test_handoff_needs_a_real_url(client):
    assert client.post("/handoff", headers=AUTH,
                       json={"url": "not a url"}).status_code == 400
    assert client.post("/handoff", headers=AUTH, json={}).status_code == 422
