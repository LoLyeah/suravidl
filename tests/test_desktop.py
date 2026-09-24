"""Desktop entry helpers: port picking, token persistence, self-test."""
from pathlib import Path

import pytest


def test_find_free_port_returns_preferred_when_free():
    from suravidl_engine.__main__ import find_free_port

    p = find_free_port(0)  # port 0 always free -> any
    assert isinstance(p, int) and p > 0


def test_find_free_port_avoids_occupied_port(tmp_path):
    import socket

    from suravidl_engine.__main__ import find_free_port

    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    occupied = blocker.getsockname()[1]
    chosen = find_free_port(occupied)
    assert chosen != occupied
    blocker.close()


def test_token_persists_and_is_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    from suravidl_engine.__main__ import load_or_create_token

    t1 = load_or_create_token()
    assert t1, "token must be non-empty"
    assert (tmp_path / ".suravidl" / "token").exists()
    t2 = load_or_create_token()
    assert t1 == t2, "token must be stable across calls"


def test_selftest_passes_against_live_server(tmp_path):
    from suravidl_engine.__main__ import self_test

    ok = self_test(download_dir=tmp_path / "dl", port=0, timeout_s=20)
    assert ok, "self_test must pass against a live engine"
