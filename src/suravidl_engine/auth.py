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


def describe_cookies_file(path: str | Path) -> dict:
    """Read a Netscape cookies.txt and say what is in it.

    Never returns the cookie values: the answer goes to the UI, and a value is
    exactly what must not travel there.
    """
    import time

    src = Path(path).expanduser()
    out = {"exists": src.is_file(), "count": 0, "domains": [], "expired": 0,
           "session": 0, "newest": None}
    if not src.is_file():
        return out
    now = time.time()
    domains: list[str] = []
    for line in src.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 7:
            continue
        domain, _flag, _path, _secure, expiry, _name, _value = fields[:7]
        out["count"] += 1
        if domain and domain not in domains:
            domains.append(domain)
        if expiry.strip() in ("", "0"):
            out["session"] += 1
            continue
        try:
            when = float(expiry)
        except ValueError:
            continue
        if when < now:
            out["expired"] += 1
        elif out["newest"] is None or when > out["newest"]:
            out["newest"] = when
    out["domains"] = domains[:8]
    return out


def check_auth(settings: dict, url: str | None = None) -> dict:
    """Answer "are my cookies actually working?" — statically and, if a URL is
    given, by proving it with a real yt-dlp extraction.

    The live probe is the only thing that can really tell: a cookies.txt can
    parse perfectly and still be expired, logged out, or from another browser.
    """
    from .download_opts import probe_extra_opts
    from .probe import probe

    path = str(settings.get("cookies_file") or "").strip()
    browser = str(settings.get("cookies_from_browser") or "").strip()
    result: dict = {"ok": False, "source": "none", "url": url or None,
                    "cookies": None, "message": "", "detail": None}

    if not path and not browser:
        result["message"] = ("Nothing configured yet — export a cookies.txt or "
                             "pick a browser in Settings → Authentication.")
        return result

    if path:
        result["source"] = "file"
        info = describe_cookies_file(path)
        result["cookies"] = info
        if not info["exists"]:
            result["message"] = f"Cookies file not found: {path}"
            return result
        if not info["count"]:
            result["message"] = ("That file has no cookies in it — is it a real "
                                 "Netscape-format export?")
            return result
        if info["expired"] and info["expired"] == info["count"]:
            result["message"] = (f"All {info['count']} cookies in the file are "
                                 "expired — export a fresh one.")
            return result
        where = ", ".join(info["domains"][:4]) or "unknown domains"
        result["message"] = (f"{info['count']} cookies for {where}"
                             + (f" ({info['expired']} expired)"
                                if info["expired"] else ""))
    else:
        result["source"] = "browser"
        result["message"] = f"Reading cookies from {browser}"

    if not url:
        if result["source"] == "browser":
            result["message"] += (" — a browser source can only be proven with a "
                                  "real URL: paste one and test again.")
        else:
            result["ok"] = True
            result["message"] += " — looks usable (test with a URL to be sure)."
        return result

    with cookie_session(settings) as cookie_opts:
        try:
            info = probe(url, cookie_opts=cookie_opts,
                         extra_opts=probe_extra_opts(settings))
        except Exception as e:  # noqa: BLE001 - yt-dlp raises many shapes
            text = str(e).strip() or e.__class__.__name__
            result["detail"] = text
            lowered = text.lower()
            # specific phrases only: a bare "age" matches "webpage"
            walls = ("sign in to confirm", "sign in", "log in", "login",
                     "private video", "members-only", "members only",
                     "age-restricted", "age restricted", "not a bot", "cookies")
            if any(s in lowered for s in walls):
                result["message"] += (" — but the site still asked for a sign-in: "
                                      "the cookies are stale, or came from a "
                                      "browser where you are logged out.")
            else:
                result["message"] += " — the test download did not get through."
            return result

    result["ok"] = True
    title = (info or {}).get("title") or (info or {}).get("id") or url
    result["message"] += f" — worked: “{title}” came back"
    return result
