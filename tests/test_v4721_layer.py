"""v0.47.21 "the layer" — a failure names the layer that broke.

"The site never answered in time" is true and useless: it can be DNS, a
blocked port, a refused handshake, or a server that accepted and stalled. The
engine now probes the same path after a network-ish failure and says which.
"""
import pathlib
import socket

import pytest

from suravidl_engine import __version__, diagnose
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text()


def test_the_notes_still_carry_this_release():
    assert len(ENTRIES) == 10
    assert any(e["title"].lower() == "the layer" for e in ENTRIES)


def test_a_name_that_does_not_resolve_says_so():
    verdict = diagnose.explain("https://no-such-host.invalid/video.mp4", timeout=3)
    assert "does not resolve" in verdict
    assert "no-such-host.invalid" in verdict


def test_a_closed_port_is_reported_as_a_refusal():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    verdict = diagnose.explain(f"http://127.0.0.1:{port}/x.mp4", timeout=3)
    assert "refused" in verdict or "no connection" in verdict


def test_a_reachable_host_produces_no_note():
    # the engine's own loopback test server: reachable, no TLS
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert diagnose.note_for(f"http://127.0.0.1:{port}/x.mp4") == ""


def test_a_failed_job_carries_the_diagnosis():
    assert "from .diagnose import note_for" in JOBS
    assert 'job["note"] = note' in JOBS
    # only for network-shaped failures: a 404 needs no probe
    assert '"name or service"' in JOBS


def test_the_row_shows_the_note_when_it_failed():
    err = APP.index("if (j.error && /ffmpeg/i.test(j.error)")
    assert APP.index("if (j.note)", err) > err, "the error branch must render it"


def test_the_probe_uses_the_engines_trust_not_a_bare_context():
    """Otherwise it reports a certificate problem the download path has
    already repaired."""
    src = (ROOT / "src" / "suravidl_engine" / "diagnose.py").read_text()
    assert "from .trust import context as trust_context" in src
    assert "ssl.create_default_context()" not in src
