"""v0.38.8 — the certificate the bundle never had (macOS update check).

A frozen macOS bundle's Python has no discoverable CA store — OpenSSL's
compiled-in paths do not exist there and Python never consults the Keychain —
so every stdlib `urlopen` that would verify a real certificate dies with
`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. The app's
update check did exactly that; direct-media probes were next in line. yt-dlp
never noticed because it loads certifi's bundle itself.

Reproduced without a Mac by hiding the store:
  SSL_CERT_FILE=/nonexistent SSL_CERT_DIR=/nonexistent python -c
  "urllib.request.urlopen('https://api.github.com/...')"
  -> <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify
     failed: unable to get local issuer certificate>

The engine's own fetches now build their context through `net.ssl_context()`,
which ADDS certifi's bundle on top of whatever the platform offers.
"""
from __future__ import annotations

import json
import ssl
import urllib.error

import pytest


def test_the_context_carries_a_real_ca_store():
    from suravidl_engine import net

    ctx = net.ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    # certifi alone carries ~121 CAs; anything near that proves a real store
    assert ctx.cert_store_stats()["x509_ca"] > 50


def test_the_context_adds_certifi_never_substitutes(monkeypatch):
    """Platform stores (corporate CAs, Linux) must survive the addition."""
    certifi = pytest.importorskip("certifi")
    from suravidl_engine import net

    loaded = []
    real = ssl.SSLContext.load_verify_locations

    def spy(self, *args, **kwargs):
        loaded.append(kwargs.get("cafile"))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", spy)
    ctx = net.ssl_context()
    assert certifi.where() in loaded
    assert ctx.cert_store_stats()["x509_ca"] > 50


def test_update_check_verifies_through_the_context(monkeypatch):
    from suravidl_engine import updater

    sentinel = object()
    seen = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"tag_name": "v99.0.0",
                               "html_url": "https://example.test/x"}).encode()

    def fake_urlopen(req, timeout=None, context=None):
        seen["context"] = context
        seen["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(updater, "urlopen", fake_urlopen)
    monkeypatch.setattr(updater, "ssl_context", lambda: sentinel)
    out = updater.check_update("0.38.8")
    assert seen["context"] is sentinel, "urlopen must verify through our context"
    assert seen["url"].endswith("/releases/latest")
    assert out["latest"] == "99.0.0" and out["update_available"] is True
    assert "error" not in out


def test_a_certificate_failure_is_reported_not_raised(monkeypatch):
    """The check must keep answering — with the reason — never crash."""
    from suravidl_engine import updater

    def boom(req, timeout=None, context=None):
        raise urllib.error.URLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
            "unable to get local issuer certificate")

    monkeypatch.setattr(updater, "urlopen", boom)
    out = updater.check_update("0.38.8")
    assert out["update_available"] is False
    assert "CERTIFICATE_VERIFY_FAILED" in out["error"]


def test_classify_fetch_verifies_through_the_context(monkeypatch):
    from suravidl_engine import classify

    sentinel = object()
    seen = {}

    class _Resp:
        status = 200
        headers = {"Content-Type": "video/mp4"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=None):
            return b"\x00" * 16

        def geturl(self):
            return "https://cdn.example.test/x.mp4"

    def fake_urlopen(req, timeout=None, context=None):
        seen["context"] = context
        return _Resp()

    monkeypatch.setattr(classify, "ssl_context", lambda: sentinel)
    monkeypatch.setattr(classify.urlrequest, "urlopen", fake_urlopen)
    resp = classify._http_fetch("https://cdn.example.test/x.mp4")
    assert seen.get("context") is sentinel, "probe fetches must verify through it too"
    assert resp.ok() and resp.status == 200


def test_the_update_row_says_what_a_certificate_failure_means():
    """The UI maps the one error class a user can act on; raw text stays raw."""
    from pathlib import Path

    app_js = Path(__file__).resolve().parents[1] / "src" / "suravidl_engine" / "web" / "app.js"
    text = app_js.read_text(encoding="utf-8")
    assert "CERTIFICATE_VERIFY_FAILED" in text, "the cert branch must be detectable"
    assert "can't verify server certificates in this build" in text
