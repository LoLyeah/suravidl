"""v0.47.16 "the catch" — two guards that were wrong.

1. The release guard that proves the desktop ffmpeg fetcher is not in the
   Android APK searched for "/tools/ffmpeg/remove", an API route every build
   carries — so it rejected the phone's own artifact and v0.47.15 shipped
   without an APK. It now matches only strings that live in tools.py.
2. Impersonation asked yt-dlp for the bare alias "chrome". curl_cffi 0.17.0
   dropped that alias, so every impersonated job and probe started failing on
   CI (and would for any user who upgraded the package). The engine now
   resolves the alias to the newest concrete target the installed curl_cffi
   actually serves.
"""
import pathlib

import pytest

from suravidl_engine import download_opts

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_the_alias_is_kept_when_the_backend_knows_it(monkeypatch):
    monkeypatch.setattr(download_opts, "_curl_targets",
                        lambda: ["chrome", "chrome142", "firefox135"])
    assert download_opts.resolve_impersonate("chrome") == "chrome"


def test_a_dropped_alias_falls_back_to_the_newest_concrete_target(monkeypatch):
    # curl_cffi 0.17.0's shape: numbered targets only, no bare "chrome"
    monkeypatch.setattr(download_opts, "_curl_targets", lambda: [
        "chrome99", "chrome142", "chrome150", "chrome_android",
        "chrome131_android", "firefox135"])
    assert download_opts.resolve_impersonate("chrome") == "chrome150"


def test_mobile_profiles_are_never_picked(monkeypatch):
    monkeypatch.setattr(download_opts, "_curl_targets",
                        lambda: ["safari18_0_ios", "safari18_4", "safari_beta"])
    assert download_opts.resolve_impersonate("safari") == "safari18_4"


def test_a_backend_with_no_targets_is_left_to_yt_dlp(monkeypatch):
    monkeypatch.setattr(download_opts, "_curl_targets", lambda: [])
    assert download_opts.resolve_impersonate("chrome") == "chrome"


def test_the_job_options_carry_the_resolved_target(monkeypatch, tmp_path):
    pytest.importorskip("curl_cffi")
    monkeypatch.setattr(download_opts, "_curl_targets", lambda: ["chrome142"])
    opts = download_opts.build_download_opts({"impersonate": "chrome"}, tmp_path)
    assert "chrome142" in str(opts["impersonate"])


def test_the_release_guard_only_matches_the_fetcher():
    """"/tools/ffmpeg/remove" is an API route — matching it broke 0.47.15."""
    script = (ROOT / "android" / "scripts" / "check_no_fetcher.py").read_text()
    assert "/tools/ffmpeg/remove" not in script.split("MARKERS")[1]
    assert "def start_download" in script and "SURAVIDL_TOOLS_DIR" in script


def test_the_package_metadata_cannot_go_stale():
    """It said 0.43.1 for a dozen releases: read the version, don't copy it."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in pyproject
    assert 'attr = "suravidl_engine.__version__"' in pyproject
    assert 'version = "0.43.1"' not in pyproject


def test_the_brotli_carrying_dependency_is_pinned():
    """curl_cffi statically links a Brotli decoder (CVE-2026-111497)."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert 'curl_cffi>=0.17.0' in pyproject
    assert 'curl_cffi' in release and '>=0.17.0' in release
