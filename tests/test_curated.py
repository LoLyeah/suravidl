"""Curated option groups (verbosity · workarounds · geo · extractor args).

These are the *named* settings the yt-dlp tab exposes, as opposed to raw
arguments: each one is validated here and mapped to yt-dlp's own option keys
in download_opts.py. The mapping is checked against yt-dlp's CLI parser, so a
yt-dlp update that changes a key fails this file instead of silently
breaking the feature.
"""
import pytest

from suravidl_engine.download_opts import (CURATED_KEYS, build_download_opts,
                                           parse_extractor_args)
from suravidl_engine.settings import Settings


@pytest.fixture()
def s(tmp_path):
    return Settings(path=tmp_path / "settings.json")


def _opts(settings: dict, **kw):
    return build_download_opts(settings, "/tmp/dl", **kw)


# ---------------------------------------------------------------- defaults
def test_defaults_are_inert(s):
    d = s.get()
    assert d["ip_version"] == "auto"
    assert d["no_check_certificates"] is False
    assert d["sleep_requests"] == 0
    assert d["geo_bypass"] is False
    assert d["geo_bypass_country"] == ""
    assert d["extractor_args"] == ""
    assert d["verbose"] is False
    opts = _opts(d)
    for key in ("source_address", "nocheckcertificate",
                "sleep_interval_requests", "geo_bypass",
                "geo_bypass_country", "extractor_args", "verbose"):
        assert key not in opts, f"{key} must stay unset on defaults"


def test_curated_keys_cover_every_curated_setting(s):
    known = set(s.get())
    # every curated key is a real setting (catches typos in the group list)
    assert set(CURATED_KEYS) <= known


# ------------------------------------------------------------ workarounds
def test_ip_version_maps_to_source_address(s):
    s.update({"ip_version": "ipv4"})
    assert _opts(s.get())["source_address"] == "0.0.0.0"
    s.update({"ip_version": "ipv6"})
    assert _opts(s.get())["source_address"] == "::"
    s.update({"ip_version": "auto"})
    assert "source_address" not in _opts(s.get())


def test_ip_version_rejects_junk(s):
    with pytest.raises(ValueError):
        s.update({"ip_version": "ipv5"})


def test_no_check_certificates(s):
    s.update({"no_check_certificates": True})
    assert _opts(s.get())["nocheckcertificate"] is True


def test_sleep_requests_is_seconds_and_clamped(s):
    s.update({"sleep_requests": 1.5})
    assert _opts(s.get())["sleep_interval_requests"] == 1.5
    s.update({"sleep_requests": 0})
    assert "sleep_interval_requests" not in _opts(s.get())
    with pytest.raises(ValueError):
        s.update({"sleep_requests": 120})
    with pytest.raises(ValueError):
        s.update({"sleep_requests": -1})


# ------------------------------------------------------------------- geo
def test_geo_bypass_and_country(s):
    s.update({"geo_bypass": True, "geo_bypass_country": "id"})
    opts = _opts(s.get())
    assert opts["geo_bypass"] is True
    assert opts["geo_bypass_country"] == "ID"       # normalised upper-case
    s.update({"geo_bypass_country": ""})
    assert "geo_bypass_country" not in _opts(s.get())


def test_geo_country_must_be_two_letters(s):
    for bad in ("I", "IDN", "1D", "i d"):
        with pytest.raises(ValueError):
            s.update({"geo_bypass_country": bad})


# --------------------------------------------------------- extractor args
def test_extractor_args_parse_to_yt_dlp_shape():
    assert parse_extractor_args("youtube:player_client=web_safari") == {
        "youtube": {"player_client": ["web_safari"]}}
    # multiple values, multiple keys, multiple extractors
    got = parse_extractor_args(
        "youtube:player_client=web_safari,ios;youtube:skip=hls,dash;"
        "generic:impersonate=chrome")
    assert got == {
        "youtube": {"player_client": ["web_safari", "ios"],
                    "skip": ["hls", "dash"]},
        "generic": {"impersonate": ["chrome"]},
    }


def test_extractor_args_reject_junk():
    for bad in ("youtube", ":x=y", "youtube:", "youtube:novalue",
                "youtube:a=", "youtube:a=b=c", "--exec rm"):
        with pytest.raises(ValueError):
            parse_extractor_args(bad)


def test_extractor_args_setting_round_trip(s):
    s.update({"extractor_args": "youtube:player_client=web_safari"})
    assert _opts(s.get())["extractor_args"] == {
        "youtube": {"player_client": ["web_safari"]}}


# --------------------------------------------------------------- verbosity
def test_verbose_flips_quiet_and_warnings(s):
    s.update({"verbose": True})
    opts = _opts(s.get())
    assert opts["verbose"] is True
    assert opts["quiet"] is False
    assert opts["no_warnings"] is False


# ------------------------------------------- mapping vs yt-dlp's own CLI
def _cli_opts(argv: list) -> dict:
    """What yt-dlp's CLI would produce for these flags (index 3 of the tuple)."""
    import yt_dlp

    return yt_dlp.parse_options(argv).ydl_opts


def test_mapping_matches_the_cli_where_the_cli_has_one(s):
    """Our Python mapping must agree with yt-dlp's own flag translation."""
    s.update({"ip_version": "ipv4"})
    assert _opts(s.get())["source_address"] == _cli_opts(["--force-ipv4"])["source_address"]
    s.update({"ip_version": "ipv6"})
    assert _opts(s.get())["source_address"] == _cli_opts(["--force-ipv6"])["source_address"]
    s.update({"ip_version": "auto",
              "no_check_certificates": True,
              "sleep_requests": 2})
    ours = _opts(s.get())
    cli = _cli_opts(["--no-check-certificates", "--sleep-requests", "2"])
    assert ours["nocheckcertificate"] == cli["nocheckcertificate"]
    assert ours["sleep_interval_requests"] == cli["sleep_interval_requests"]
    s.update({"geo_bypass": True, "geo_bypass_country": "id"})
    ours = _opts(s.get())
    cli = _cli_opts(["--geo-bypass", "--geo-bypass-country", "id"])
    assert ours["geo_bypass"] == cli["geo_bypass"]
    # we normalise the code to upper case on purpose (the CLI passes it through)
    assert ours["geo_bypass_country"] == cli["geo_bypass_country"].upper()
    s.update({"extractor_args": "youtube:player_client=web_safari"})
    assert _opts(s.get())["extractor_args"] == \
        _cli_opts(["--extractor-args", "youtube:player_client=web_safari"])["extractor_args"]


# ------------------------------------------------------------------- probe
def test_probe_accepts_extra_opts(monkeypatch):
    """The probe path gets geo/network options too, so a region-locked video
    can at least be probed."""
    import suravidl_engine.probe as probe_mod

    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def sanitize_info(self, info):
            return info or {}

        def extract_info(self, url, download=False):
            return {"id": "x", "title": "t", "formats": []}

    monkeypatch.setattr(probe_mod.yt_dlp, "YoutubeDL", FakeYDL)
    probe_mod.probe("http://example.test/v", extra_opts={"geo_bypass": True,
                                                         "proxy": "socks5://127.0.0.1:9050"})
    assert seen["geo_bypass"] is True
    assert seen["proxy"] == "socks5://127.0.0.1:9050"
    # and the probe defaults still hold
    assert seen["skip_download"] is True and seen["quiet"] is True


def test_probe_extra_opts_cannot_steal_engine_keys(monkeypatch):
    """extra_opts must not be able to turn a probe into something else."""
    import suravidl_engine.probe as probe_mod

    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def sanitize_info(self, info):
            return info or {}

        def extract_info(self, url, download=False):
            return {"id": "x", "title": "t", "formats": []}

    monkeypatch.setattr(probe_mod.yt_dlp, "YoutubeDL", FakeYDL)
    probe_mod.probe("http://example.test/v",
                    extra_opts={"skip_download": False, "paths": {"home": "/etc"},
                                "outtmpl": "/etc/x", "quiet": False})
    assert seen["skip_download"] is True      # probe never downloads
    assert "paths" not in seen and seen.get("outtmpl") is None
