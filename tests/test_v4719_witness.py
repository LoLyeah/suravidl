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


def test_the_notes_name_this_release():
    assert __version__ == "0.47.19"
    assert ENTRIES[0]["version"] == __version__
    assert ENTRIES[0]["title"].lower() == "the witness"
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
