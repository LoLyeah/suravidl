"""v0.47.19 "the witness" — the error line stops guessing.

A real report: https://pahindot.org/watch/hubad-self-video/ failed with "the
secure connection could not be verified — a TLS-inspecting proxy can cause
this". The page itself is fine; its player points at
`https://cdnserver23.cloudmp4.top/media/hubad-self-video.mp4`, and that domain
returns NXDOMAIN (checked against 1.1.1.1). On a network that resolves it to
an interception box, the same dead host surfaces as a certificate error — which
is what the phone saw.

So the message was wrong twice: it named a proxy as the cause of every
certificate failure, and it hid the real finding (a host that no longer
exists). It now names expired / self-signed / hostname-mismatch certificates,
offers a per-job retry with checks off where that could help, and shows the
file's name instead of the whole URL when a row has no title.
"""
import pathlib

from suravidl_engine import __version__, download_opts
from suravidl_engine.whatsnew import ENTRIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_notes_still_carry_this_release():
    # 0.47.19 never published (the macOS image was retired mid-cut); its
    # notes shipped under 0.47.20, and the current version is pinned by the
    # newest release's test
    assert len(ENTRIES) == 10
    assert any(e["version"] == "0.47.20" and e["title"].lower() == "the witness"
               for e in ENTRIES)
    assert len(ENTRIES) == 10
    for item in ENTRIES[0]["items"]:
        assert 0 < len(item) <= 220


def test_a_certificate_failure_names_its_cause():
    assert "the site's certificate has expired" in APP
    assert "does not trust (self-signed)" in APP
    assert "issued for a different host name" in APP
    # the old guess survives only as the last resort
    proxy = APP.index("a TLS-inspecting proxy can cause this\";")
    expired = APP.index("the site's certificate has expired")
    assert expired < proxy, "the specific arms must be tried before the guess"


def test_a_certificate_failure_offers_the_one_retry_that_can_help():
    assert 't("Retry without certificate check")' in APP
    assert "no_check_certificates: true" in APP
    # scoped to the row's own error, never shown for other failures
    assert '/certificate|SSL/i.test(j.error)' in APP


def test_a_failed_row_shows_a_name_not_a_url():
    assert "function prettySource(" in APP
    assert APP.count("prettySource(j.url)") >= 2
    assert "document.createTextNode(j.title || j.url)" not in APP


def test_the_retry_override_really_reaches_yt_dlp(tmp_path):
    """The button is only honest if the engine honours the per-job flag."""
    opts = download_opts.build_download_opts({"no_check_certificates": True}, tmp_path)
    assert opts.get("nocheckcertificate") is True
    assert "nocheckcertificate" not in download_opts.build_download_opts({}, tmp_path)


def test_the_indonesian_strings_exist():
    for pin in ("tanpa memeriksa sertifikat", "sudah kedaluwarsa",
                "hanya unduhan ini"):
        assert pin in APP, pin


def test_the_poll_does_not_wipe_the_chevron():
    """updateJobRow used textContent, which deleted the fold caret on the
    first poll and fell back to the raw URL."""
    import re

    body = APP[APP.index("function updateJobRow("):]
    body = body[:body.index("function queueBucket(")]
    assert "title.textContent = " not in body, "textContent deletes the chevron"
    assert "prettySource(j.url)" in body
    assert "nodeType === Node.TEXT_NODE" in body


# --- the other half of the report: Chrome plays it, the app does not --------

def _pem(tag: str) -> str:
    return f"-----BEGIN CERTIFICATE-----\n{tag}\n-----END CERTIFICATE-----\n"


def test_the_merged_bundle_is_certifi_plus_the_platform_store(tmp_path, monkeypatch):
    from suravidl_engine import trust

    base = tmp_path / "certifi.pem"
    base.write_text(_pem("BASE1") + _pem("BASE2"), encoding="utf-8")
    store = tmp_path / "cacerts"
    store.mkdir()
    (store / "aaa.0").write_text(_pem("SYSTEM1"), encoding="utf-8")
    (store / "bbb.0").write_text(_pem("BASE1"), encoding="utf-8")   # a duplicate

    monkeypatch.setattr(trust, "_certifi_path", lambda: base)
    monkeypatch.setattr(trust, "_SYSTEM_FILES", ())
    monkeypatch.setattr(trust, "_SYSTEM_DIRS", (str(store),))
    monkeypatch.setenv("SURAVIDL_CA_BUNDLE", str(tmp_path / "merged.pem"))

    out = trust.merged_bundle()
    text = out.read_text(encoding="utf-8")
    assert trust._MARKER in text
    for tag in ("BASE1", "BASE2", "SYSTEM1"):
        assert tag in text
    assert text.count("BEGIN CERTIFICATE") == 3, "duplicates must not pile up"


def test_install_points_every_trust_hook_at_the_merge(tmp_path, monkeypatch):
    from suravidl_engine import trust

    base = tmp_path / "certifi.pem"
    base.write_text(_pem("BASE1"), encoding="utf-8")
    monkeypatch.setattr(trust, "_certifi_path", lambda: base)
    monkeypatch.setattr(trust, "_SYSTEM_FILES", ())
    monkeypatch.setattr(trust, "_SYSTEM_DIRS", ())
    monkeypatch.setenv("SURAVIDL_CA_BUNDLE", str(tmp_path / "merged.pem"))

    dest = trust.install()
    assert dest.is_file()
    import os
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        assert os.environ[var] == str(dest)
    import certifi
    assert certifi.where() == str(dest), "urllib3/yt-dlp ask certifi directly"


def test_the_engine_context_is_still_a_verifying_one():
    from suravidl_engine import net

    ctx = net.ssl_context()
    assert ctx.verify_mode.name == "CERT_REQUIRED"
    assert ctx.check_hostname is True


# --- AIA repair: what a browser does with an incomplete chain ---------------

def _leaf_der() -> bytes:
    import base64
    import pathlib as _p

    pem = (_p.Path(__file__).resolve().parents[1] / "tests" / "fixtures" /
           "leaf-incomplete-chain.pem").read_text()
    body = pem.split("-----BEGIN CERTIFICATE-----")[1].split("-----END CERTIFICATE-----")[0]
    return base64.b64decode("".join(body.split()))


def test_the_aia_extension_names_the_missing_issuer():
    from suravidl_engine import trust

    urls = trust.aia_issuer_urls(_leaf_der())
    assert urls == ["http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt"], urls


def test_repair_fetches_the_issuer_and_refreshes_the_bundle(tmp_path, monkeypatch):
    from suravidl_engine import trust
    import urllib.request

    monkeypatch.setenv("SURAVIDL_CA_BUNDLE", str(tmp_path / "merged.pem"))
    monkeypatch.setattr(trust, "_peer_leaf", lambda host, port=443: _leaf_der())
    der = (pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures" /
           "sectigo-intermediate.der").read_bytes()

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return der

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    monkeypatch.setattr(trust, "_verifies", lambda host, port=443, timeout=10.0: True)

    assert trust.repair_chain("https://cdnserver23.cloudmp4.to/media/x.mp4") is True
    extra = trust.extra_path().read_text()
    assert "BEGIN CERTIFICATE" in extra
    assert "BEGIN CERTIFICATE" in trust.bundle_path().read_text(), "the merge must include it"
    # a second call adds nothing new (idempotent)
    assert trust.repair_chain("https://cdnserver23.cloudmp4.to/media/x.mp4") is False


def test_a_chain_error_is_told_apart_from_other_failures():
    from suravidl_engine.jobs import _is_chain_error

    assert _is_chain_error(Exception("SSL: CERTIFICATE_VERIFY_FAILED unable to get local issuer certificate"))
    assert _is_chain_error(Exception("unable to verify the first certificate"))
    assert not _is_chain_error(Exception("HTTP Error 403: Forbidden"))
    assert not _is_chain_error(Exception("certificate has expired"))


def test_a_hotlink_redirect_is_explained():
    """The CDN answers a bare request with /404.html — the stream only exists
    for requests that carry the page as referer."""
    assert "hotlink|referer|referrer" in APP
    assert "refuses requests that do not come from its page" in APP
    # it must be decided before the generic "unsupported url" arm
    assert APP.index("hotlink|referer") < APP.index("unsupported url|no (suitable )?extractor")


def test_the_release_does_not_ask_for_a_retired_macos_image():
    """macos-14 was retired on 2026-11-02; brownouts cancelled the job with
    no runner assigned, twice."""
    wf = (pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows" /
          "release.yml").read_text()
    assert "macos-14" not in wf
    assert "macos-15" in wf


def test_only_a_ca_may_become_a_trust_anchor():
    """A hostile server must not get its own leaf trusted via AIA."""
    from suravidl_engine import trust

    root = pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    inter = (root / "sectigo-intermediate.der").read_bytes()
    leaf_pem = (root / "leaf-incomplete-chain.pem").read_text()
    assert trust.is_ca_certificate(inter) is True
    assert trust.is_ca_certificate(trust._pem_to_der(leaf_pem) or b"") is False


def test_repair_refuses_an_end_entity_certificate(tmp_path, monkeypatch):
    from suravidl_engine import trust
    import urllib.request

    monkeypatch.setenv("SURAVIDL_CA_BUNDLE", str(tmp_path / "merged.pem"))
    monkeypatch.setattr(trust, "_peer_leaf", lambda host, port=443: _leaf_der())
    leaf_pem = (pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures" /
                "leaf-incomplete-chain.pem").read_bytes()

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return leaf_pem

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    monkeypatch.setattr(trust, "_verifies", lambda host, port=443, timeout=10.0: True)
    assert trust.repair_chain("https://cdnserver23.cloudmp4.to/x.mp4") is False
    assert not trust.extra_path().exists() or "BEGIN CERTIFICATE" not in trust.extra_path().read_text()


def test_a_repair_that_does_not_verify_is_reported_as_failed(tmp_path, monkeypatch):
    """The phone kept failing after a "successful" repair: a repair only
    counts when the host actually verifies afterwards."""
    from suravidl_engine import trust
    import urllib.request

    monkeypatch.setenv("SURAVIDL_CA_BUNDLE", str(tmp_path / "merged.pem"))
    monkeypatch.setattr(trust, "_peer_leaf", lambda host, port=443: _leaf_der())
    der = (pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures" /
           "sectigo-intermediate.der").read_bytes()

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return der

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    monkeypatch.setattr(trust, "_verifies", lambda host, port=443, timeout=10.0: False)
    assert trust.repair_chain("https://cdnserver23.cloudmp4.to/x.mp4") is False
