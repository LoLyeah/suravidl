"""v0.39.2 — the engine is findable.

The reported bug: the app was open, the token was configured, and the
extension's popup still said "suravidl isn't running". Root cause: when the
engine's preferred port was busy at launch (a previous session, another
app), the app silently moved to a *random* port — a place the extension
would never look. The engine now walks a fixed ladder (8787→8792), and the
extension walks the same ladder before declaring anything dead. The CORS
origin check also stops caring what a Firefox uuid looks like.
"""
from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _app(tmp_path):
    from suravidl_engine.api import create_app

    return create_app(download_dir=tmp_path, auth_token="t")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _blocked(p: int):
    s = socket.socket()
    s.bind(("127.0.0.1", p))
    s.listen(1)
    return s


# -- the engine walks a ladder, never a random port ---------------------------

def test_the_engine_port_ladder_is_fixed():
    from suravidl_engine.__main__ import find_free_port

    base = _free_port()
    assert find_free_port(base) == base

    b1, b2 = _blocked(base), _blocked(base + 1)
    try:
        assert find_free_port(base) == base + 2, "a busy rung moves one step, not anywhere"
    finally:
        b1.close()
        b2.close()


def test_a_full_ladder_falls_back_to_any_free_port():
    from suravidl_engine.__main__ import _port_candidates, find_free_port

    base = _free_port()
    occupied = [base + i for i in range(len(_port_candidates(base)))]
    blockers = [_blocked(p) for p in occupied]
    try:
        chosen = find_free_port(base)
        assert chosen not in occupied, "the ladder is full: anywhere free is honest"
        with socket.socket() as s:
            s.bind(("127.0.0.1", chosen))  # and actually free
    finally:
        for b in blockers:
            b.close()


def test_the_extension_scans_the_same_ladder():
    """background.js and __main__.py must agree, or the extension looks in the
    wrong place — the exact bug this fixes. Pin both sides to one list."""
    from suravidl_engine.__main__ import _ENGINE_PORT, _port_candidates

    src = (ROOT / "extension" / "background.js").read_text()
    m = re.search(r"const PORT_LADDER = \[([^\]]+)\]", src)
    assert m, "background.js grows a PORT_LADDER"
    js = [int(x) for x in m.group(1).split(",")]
    assert js == _port_candidates(_ENGINE_PORT), \
        "the extension and the engine must walk the same ladder"


def test_the_extension_resolves_before_it_fetches():
    src = (ROOT / "extension" / "background.js").read_text()
    # every engine call goes through the resolver — no caller remembers 8787
    assert src.count("await resolveEngine()") >= 5
    assert "discoveredUrl" in src, "where it was found is remembered"


# -- any sane extension origin passes CORS ------------------------------------

def test_a_future_shaped_firefox_origin_is_allowed(tmp_path):
    """The regex pinned moz uuids to hex: one uuid outside that alphabet would
    read as "not running" for every request. Origin is browser-set — a page
    cannot forge moz-extension://, so accept the shape, not the alphabet."""
    with TestClient(_app(tmp_path)) as c:
        r = c.get("/health", headers={
            "Origin": "moz-extension://z9y8x7w6-v5u4-t3s2-r1q0-p9o8n7m6l5k4"})
        assert r.headers.get("access-control-allow-origin", "").startswith("moz-extension://"), \
            "a non-hex moz-extension origin still gets its answer"


def test_the_hex_uuid_case_still_passes(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.get("/health", headers={
            "Origin": "moz-extension://a3e57a10-a528-4673-bc81-eb9e40a5b705"})
        assert r.headers.get("access-control-allow-origin", "").startswith("moz-extension://")


def test_chrome_ids_are_still_pinned_to_a_p(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        good = c.get("/health", headers={
            "Origin": "chrome-extension://habomdhpjdcddccplapkncnfokpknfle"})
        assert good.headers.get("access-control-allow-origin") == \
            "chrome-extension://habomdhpjdcddccplapkncnfokpknfle"
        bad = c.get("/health", headers={
            "Origin": "chrome-extension://not-a-real-chrome-id-at-all"})
        assert "access-control-allow-origin" not in bad.headers
