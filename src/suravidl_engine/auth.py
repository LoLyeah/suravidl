"""Cookie authentication for yt-dlp (age-restricted, private, bot-gated videos).

Two sources, both optional and set in Settings:
  * `cookies_file`          — path to a Netscape-format cookies.txt export
  * `cookies_from_browser`  — read cookies from an installed desktop browser

The cookies file is never handed to yt-dlp directly: each run gets a private
copy, because yt-dlp writes refreshed cookies back on close and two concurrent
downloads would race (or a crash could truncate the user's export).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path


def parse_browser(value: str):
    """'chrome' / 'firefox:Profile 2' -> yt-dlp cookiesfrombrowser tuple."""
    from yt_dlp.cookies import SUPPORTED_BROWSERS, _parse_browser_specification

    spec = value.strip()
    browser, _, profile = spec.partition(":")
    browser = browser.strip().lower()
    if browser not in SUPPORTED_BROWSERS:
        known = ", ".join(sorted(SUPPORTED_BROWSERS))
        raise ValueError(f"unsupported browser {browser!r} (known: {known})")
    return _parse_browser_specification(browser, profile.strip() or None, None, None)


@contextlib.contextmanager
def cookie_session(settings: dict):
    """Yield yt-dlp opts for this run; cleans up the private copies afterwards."""
    opts: dict = {}
    workdir: Path | None = None
    try:
        path = str(settings.get("cookies_file") or "").strip()
        if path:
            src = Path(path).expanduser()
            if not src.is_file():
                raise FileNotFoundError(
                    f"cookies file not found: {src} (Settings -> Authentication)")
            workdir = Path(tempfile.mkdtemp(prefix="suravidl-ck-"))
            copy = workdir / "cookies.txt"
            shutil.copyfile(src, copy)
            os.chmod(copy, 0o600)  # nobody but us reads the cookies
            opts["cookiefile"] = str(copy)
        browser = str(settings.get("cookies_from_browser") or "").strip()
        if browser:
            opts["cookiesfrombrowser"] = parse_browser(browser)
        yield opts
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
