"""Probe: yt-dlp-as-module metadata extraction, offline via local fixture server."""
import functools
import http.server
import threading
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_probe_direct_mp4_returns_metadata(fixture_server):
    from vidl_engine.probe import probe

    info = probe(f"{fixture_server}/tiny.mp4")
    assert info["ext"] == "mp4"
    assert "tiny" in info["title"]
    assert info["formats"], "expected at least one format"


def test_probe_unsupported_url_raises_clear_error():
    from vidl_engine.probe import probe

    with pytest.raises(Exception) as exc:
        probe("http://127.0.0.1:1/nonexistent.mp4")
    assert "unable to" in str(exc.value).lower() or "error" in str(exc.value).lower()
