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
