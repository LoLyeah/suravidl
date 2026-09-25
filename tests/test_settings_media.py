"""Validation for the tier-1 settings: template, subtitles, network, sponsorblock."""
import pytest

from suravidl_engine.download_opts import build_download_opts
from suravidl_engine.settings import Settings


@pytest.fixture()
def s(tmp_path):
    return Settings(path=tmp_path / "settings.json")


def test_defaults_present(s):
    d = s.get()
    assert d["filename_template"] == "%(title).100B.%(ext)s"
    assert d["subtitles_mode"] == "off"
    assert d["subtitles_langs"] == "en"
    assert d["embed_metadata"] is False and d["embed_thumbnail"] is False
    assert d["rate_limit"] == "" and d["fragments"] == 1 and d["proxy"] == ""
    assert d["archive"] is False
    assert d["sponsorblock_mode"] == "off"
    assert d["sponsorblock_categories"] == "sponsor, selfpromo"


def test_template_accepts_reasonable_values(s):
    s.update({"filename_template": "%(uploader)s - %(title)s.%(ext)s"})
    assert s.get()["filename_template"] == "%(uploader)s - %(title)s.%(ext)s"
    s.update({"filename_template": "%(title).100B.%(ext)s"})
    assert s.get()["filename_template"] == "%(title).100B.%(ext)s"
    # v0.22.0: a *relative* subfolder is how a channel or course stays tidy —
    # it used to be refused, which is why every batch landed flat
    s.update({"filename_template": "sub/dir/%(title)s.%(ext)s"})
    assert s.get()["filename_template"] == "sub/dir/%(title)s.%(ext)s"


@pytest.mark.parametrize("bad", [
    "",                      # empty
    "no-ext-placeholder",    # mandatory %(ext)s missing
    "../escape.%(ext)s",     # path traversal
    "/etc/passwd.%(ext)s",   # absolute: writes outside the download folder
    "sub\\dir.%(ext)s",      # a backslash is a separator on Windows
])
def test_template_rejects_bad_values(s, bad):
    with pytest.raises(ValueError):
        s.update({"filename_template": bad})


def test_a_tilde_in_a_template_stays_inside_the_download_folder(s):
    """Verified by running it: yt-dlp does not expand `~`, so the file lands in
    a literal `~` directory *inside* the download folder — not in $HOME."""
    s.update({"filename_template": "~/%(title)s.%(ext)s"})
    opts = build_download_opts({"filename_template": "~/%(title)s.%(ext)s"},
                               "/tmp/dl_tilde_check")
    assert opts["outtmpl"].startswith("/tmp/dl_tilde_check/~/")


def test_subtitles_validation(s):
    s.update({"subtitles_mode": "embed", "subtitles_langs": "en, id"})
    assert s.get()["subtitles_mode"] == "embed"
    with pytest.raises(ValueError):
        s.update({"subtitles_mode": "burn"})
    with pytest.raises(ValueError):
        s.update({"subtitles_langs": "en; rm -rf"})
    s.update({"subtitles_auto": True})
    assert s.get()["subtitles_auto"] is True


def test_rate_limit_validation(s):
    s.update({"rate_limit": "2M"})
    assert s.get()["rate_limit"] == "2M"
    for bad in ("fast", "-1M", "10 MB", "M"):
        with pytest.raises(ValueError):
            s.update({"rate_limit": bad})


def test_fragments_validation(s):
    s.update({"fragments": 8})
    assert s.get()["fragments"] == 8
    s.update({"fragments": 0})
    assert s.get()["fragments"] == 1
    s.update({"fragments": 99})
    assert s.get()["fragments"] == 16


def test_proxy_validation(s):
    s.update({"proxy": "socks5://127.0.0.1:1080"})
    assert s.get()["proxy"] == "socks5://127.0.0.1:1080"
    s.update({"proxy": "http://proxy.local:3128"})
    assert s.get()["proxy"] == "http://proxy.local:3128"
    for bad in ("ftp://x", "not a proxy", "socks5://"):
        with pytest.raises(ValueError):
            s.update({"proxy": bad})


def test_sponsorblock_validation(s):
    s.update({"sponsorblock_mode": "remove", "sponsorblock_categories": "sponsor, intro"})
    assert s.get()["sponsorblock_mode"] == "remove"
    with pytest.raises(ValueError):
        s.update({"sponsorblock_mode": "burn"})
    with pytest.raises(ValueError):
        s.update({"sponsorblock_categories": "sponsor,bogus"})


def test_remaining_keys_persist(s):
    s.update({"embed_metadata": True, "embed_thumbnail": True, "archive": True})
    d = s.get()
    assert d["embed_metadata"] and d["embed_thumbnail"] and d["archive"]
    # they survive a reload from disk
    d2 = Settings(path=s.path).get()
    assert d2["embed_metadata"] and d2["archive"]
