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
import re
import shutil
import tempfile
from pathlib import Path


# --- auto (v0.49.11) -------------------------------------------------------
# "cookies from browser: auto" picks the browser on this machine that is
# actually signed in. A host_key match alone is not a login — a logged-out
# visit still leaves consent and tracking cookies behind — so the scan asks
# for the session cookie each site sets on sign-in, ranks profiles by when
# that cookie was last used, and answers with "browser:profile", which is the
# form yt-dlp takes (Gemini 4 Carbon, 2026-11-12).
_SESSION_COOKIES = {
    "facebook.com": ("c_user", "xs"),
    "instagram.com": ("sessionid",),
    "x.com": ("auth_token",),
    "youtube.com": ("SID", "SAPISID"),
    "tiktok.com": ("sessionid",),
}
_CHROMIUM_EPOCH = 11644473600  # seconds between 1601-01-01 and 1970-01-01


def _roots() -> list[tuple[str, Path, str]]:
    """(browser, root, family) for this OS, Snap and Flatpak included."""
    import sys

    home = Path.home()
    if sys.platform == "darwin":
        cfg = home / "Library" / "Application Support"
        return [
            ("chrome", cfg / "Google/Chrome", "chromium"),
            ("chromium", cfg / "Chromium", "chromium"),
            ("edge", cfg / "Microsoft Edge", "chromium"),
            ("brave", cfg / "BraveSoftware/Brave-Browser", "chromium"),
            ("vivaldi", cfg / "Vivaldi", "chromium"),
            ("opera", cfg / "com.operasoftware.Opera", "chromium"),
            ("firefox", cfg / "Firefox/Profiles", "firefox"),
        ]
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData/Local")
        roaming = Path(os.environ.get("APPDATA") or home / "AppData/Roaming")
        return [
            ("chrome", local / "Google/Chrome/User Data", "chromium"),
            ("edge", local / "Microsoft/Edge/User Data", "chromium"),
            ("brave", local / "BraveSoftware/Brave-Browser/User Data", "chromium"),
            ("firefox", roaming / "Mozilla/Firefox/Profiles", "firefox"),
        ]
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return [
        ("chrome", cfg / "google-chrome", "chromium"),
        ("chromium", cfg / "chromium", "chromium"),
        ("edge", cfg / "microsoft-edge", "chromium"),
        ("brave", cfg / "BraveSoftware/Brave-Browser", "chromium"),
        ("vivaldi", cfg / "vivaldi", "chromium"),
        ("opera", cfg / "opera", "chromium"),
        ("firefox", home / ".mozilla/firefox", "firefox"),
        ("chromium", home / "snap/chromium/common/chromium", "chromium"),
        ("firefox", home / "snap/firefox/common/.mozilla/firefox", "firefox"),
        ("chrome", home / ".var/app/com.google.Chrome/config/google-chrome", "chromium"),
        ("firefox", home / ".var/app/org.mozilla.firefox/.mozilla/firefox", "firefox"),
    ]


def _chromium_profiles(root: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if not root.is_dir():
        return out
    for profile in [root / "Default"] + sorted(root.glob("Profile *")):
        db = profile / "Cookies"
        if db.is_file():
            out.append((profile.name, db))
    if not out and (root / "Cookies").is_file():   # Opera keeps it at the root
        out.append(("Default", root / "Cookies"))
    return out


def _firefox_profiles(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in sorted(root.iterdir())
            if (p / "cookies.sqlite").is_file()]


def _cookie_dbs() -> list[tuple[str, str, Path]]:
    out: list[tuple[str, str, Path]] = []
    for browser, root, family in _roots():
        if family == "chromium":
            out.extend((browser, profile, db)
                       for profile, db in _chromium_profiles(root))
        else:
            out.extend((browser, p.name, p / "cookies.sqlite")
                       for p in _firefox_profiles(root))
    return out


def _read_cookie_stats(db: Path, host: str, names: tuple[str, ...]):
    """Copy the database beside its wal/shm and read it; None when unreadable.

    A live browser keeps fresh writes in the -wal file, and Chromium's own
    database can be locked (Windows holds it exclusively while running), so
    the copy is the only safe read — and a failed copy just means "skip".
    """
    import sqlite3
    import time

    workdir = Path(tempfile.mkdtemp(prefix="suravidl-db-"))
    try:
        copy = workdir / db.name
        for suffix in ("", "-wal", "-shm"):
            src = db.with_name(db.name + suffix)
            if src.is_file():
                shutil.copy2(src, workdir / (db.name + suffix))
        if not copy.is_file():
            return None
        con = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        try:
            now = time.time()
            if db.name.startswith("cookies.sqlite"):
                rows = con.execute(
                    "SELECT MAX(lastAccessed), COUNT(*) FROM moz_cookies "
                    "WHERE host LIKE ? AND (expiry = 0 OR expiry > ?)",
                    (host, int(now))).fetchone()
                when = (rows[0] or 0) / 1e6 if rows else 0
                count = rows[1] if rows else 0
            else:
                chrome_now = int((now + _CHROMIUM_EPOCH) * 1e6)
                rows = con.execute(
                    "SELECT MAX(last_access_utc), COUNT(*) FROM cookies "
                    "WHERE host_key LIKE ? AND (expires_utc = 0 OR expires_utc > ?)",
                    (host, chrome_now)).fetchone()
                when = ((rows[0] or 0) / 1e6 - _CHROMIUM_EPOCH) if rows else 0
                count = rows[1] if rows else 0
            if not count:
                return None
            has_session = False
            if names:
                placeholders = ",".join("?" for _ in names)
                table = "moz_cookies" if db.name.startswith("cookies.sqlite") else "cookies"
                host_col = "host" if table == "moz_cookies" else "host_key"
                hit = con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {host_col} LIKE ? "
                    f"AND name IN ({placeholders})", (host, *names)).fetchone()
                has_session = bool(hit and hit[0])
            return has_session, float(when or 0)
        finally:
            con.close()
    except Exception:
        return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def detect_browser(site: str = "facebook.com") -> str:
    """'browser:profile' of the signed-in browser for this site, or ''."""
    import sys

    names = _SESSION_COOKIES.get(site, ())
    host = "%" + site
    best = None
    for browser, profile, db in _cookie_dbs():
        got = _read_cookie_stats(db, host, names)
        if got is None:
            continue
        has_session, when = got
        # A cookie is not a login: the site sets consent and tracking cookies
        # in a logged-out window too, and picking that browser means the
        # download fails later with "login required" (Carbon, 2026-11-12)
        if names and not has_session:
            continue
        # a session cookie beats one that is merely present; latest use wins
        # (Carbon: file mtime moves on unrelated traffic, last_access does not)
        rank = (has_session, when)
        if best is None or rank > best[0]:
            best = (rank, browser, profile)
        elif rank == best[0] and sys.platform == "win32" and browser == "firefox":
            # Chrome 127+ on Windows encrypts cookies with app-bound keys that
            # an unprivileged downloader cannot read — prefer Firefox there
            best = (rank, browser, profile)
    return f"{best[1]}:{best[2]}" if best else ""


def resolve_auto(site: str = "facebook.com") -> str:
    found = detect_browser(site)
    if not found:
        raise ValueError(
            "no signed-in browser found for " + site + " — set Settings -> "
            "Authentication -> Browser cookies, or export a cookies.txt")
    return found


def parse_browser(value: str):
    """'chrome' / 'firefox:Profile 2' / 'auto' -> yt-dlp cookiesfrombrowser tuple."""
    from yt_dlp.cookies import SUPPORTED_BROWSERS, _parse_browser_specification

    spec = value.strip()
    if spec.lower() == "auto":
        spec = resolve_auto()
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


# The phrases yt-dlp uses when a site asks for a sign-in. Kept in ONE place:
# the UI used to carry its own copy, which drifted and started matching "age"
# inside "webpage" — every 404 came with a bogus "add cookies" hint.
WALL_PHRASES = (
    "sign in to confirm", "sign in", "log in", "login",
    "private video", "members-only", "members only",
    "age-restricted", "age restricted", "not a bot", "cookies",
)


def looks_like_signin_wall(text: str) -> bool:
    """Is this yt-dlp failure the site asking for an account?

    Specific phrases only: a bare "age" matches "webpage" (a 404 then got a
    "add cookies" hint, which sent people on a wild goose chase — the v0.21.1
    audit found the UI still carrying its own, sloppier copy of this test).
    """
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in WALL_PHRASES)


# TikTok's web front refuses a fraction of fetches on any given network —
# yt-dlp's own tracker treats it as intermittent ("the same videos download
# fine individually", yt-dlp/yt-dlp#17604). The engine retries; this is the
# hint for when it still refused every attempt.
TIKTOK_FLAKE_HINT = (
    "TikTok refused this attempt — it answers like that intermittently on "
    "some networks, and the engine already retried. Hit Retry once more; if "
    "it keeps refusing, use “Find a video on a page” to grab it from the "
    "browser instead."
)

# Scrambled playlists (v0.47.0 "the veil"): yt-dlp fetched the playlist and
# got a base64 blob instead of #EXTM3U — the site obfuscates its playlists
# and this attempt carried no decode key (a paste), or a stale one.
_OBFUSCATED_BODY = re.compile(r"no m3u header|does not decode", re.IGNORECASE)

# ffmpeg could not OPEN the output file while finishing a download
# (v0.47.4 "the minutes"): on Windows this is a name the filesystem
# refuses, a full disk (reported as this same error), or antivirus/OneDrive
# holding the file — never a broken download.
_OUTPUT_OPEN = re.compile(
    r"opening output files|error opening output file"
    r"|unable to choose an output format", re.IGNORECASE)

# Query credentials that must never ride out inside an error message the
# user reads or the row the engine persists: signed links commonly carry
# these in the URL itself.
_SECRET_QUERY_RE = re.compile(
    r"(?i)([?&](?:token|auth|sig|signature|key|api[_-]?key"
    r"|access[_-]?token|hdnts|hdnea|policy|hash)=)([^&\s\"'<>]+)")


# user:pass@ inside a URL authority (proxy strings, redirected targets)
_USERINFO_RE = re.compile(r"://([^:/@\s]+):([^@\s]+)@")

# an Authorization / Cookie header value on a log line — plain
# (`Authorization: Bearer x`) and dict-repr (`'Authorization': 'x'`)
# shapes both ride verbose logs (v0.46.10 audit A/F4+A/F6)
_HEADER_SECRET_RE = re.compile(
    r"(?i)(['\"]?(?:proxy-)?(?:authorization|set-cookie|cookie)['\"]?\s*:\s*)"
    r"(?:'[^'\r\n]*'|\"[^\"\r\n]*\"|[^\r\n,}]+)")


def scrub_secrets(text: str) -> str:
    """Redact credentials: URL query values, URL userinfo, header values.

    v0.46.10 audit A/F4+A/F6: the scrubber only knew query strings — a
    proxy password in `http://user:pass@host` and verbose-log header
    values (`Authorization: …`, `Cookie: …`) passed through verbatim
    into diagnostics and GET /logs (both live-verified leaks).
    """
    text = _SECRET_QUERY_RE.sub(r"\1[redacted]", text)
    # URL userinfo: scheme://user:password@host → scheme://user:[redacted]@
    text = _USERINFO_RE.sub(r"://\1:[redacted]@", text)
    # header-shaped secrets on log lines (Bearer/Basic tokens, cookie jars)
    text = _HEADER_SECRET_RE.sub(lambda m: m.group(1) + "[redacted]", text)
    return text


def explain_download_error(text: str) -> str:
    """A failure the user reads: yt-dlp's words, plus the one hint we know."""
    from .extract import is_tiktok_flake

    text = scrub_secrets(text)
    if looks_like_signin_wall(text):
        return (f"{text} — this looks like the site asking for an account: "
                "add cookies in Settings → Authentication (if some are "
                "already added, they may have expired — Instagram sessions "
                "last only hours).")
    if _OBFUSCATED_BODY.search(text):
        return (f"{text} — this site scrambles its playlists (a plain "
                "downloader only ever gets the scrambled blob); sniff the "
                "stream from the page with the suravidl extension so the "
                "decode key rides along, then download again.")
    if _OUTPUT_OPEN.search(text):
        return (f"{text} — the download itself finished; finishing it "
                "(joining video and audio) could not open the output file. "
                "On Windows that is usually a filename the filesystem "
                "refuses, a full disk, or antivirus holding the file. "
                "View log has the exact ffmpeg line.")
    if is_tiktok_flake(text):
        return f"{text} — {TIKTOK_FLAKE_HINT}"
    return text


UNSUPPORTED_HINT = (
    "yt-dlp has no extractor for this page — open it in the browser, press "
    "play for a second, and pick the stream suravidl finds (on desktop the "
    "extension does the same)."
)

# A TikTok photo post (/@user/photo/<id>) is a slideshow of images with a
# music track — not a video at all, and yt-dlp has no extractor for it. The
# share link resolves fine and then dies as "Unsupported URL", which sent the
# owner hunting for a broken thing that was never a download (2026-10-10):
# say what it actually is. The resolved /photo/ address rides inside the
# yt-dlp error text, so the pattern is checkable even when the input was a
# vt.tiktok.com short link.
UNSUPPORTED_PHOTO_HINT = (
    "this is a TikTok photo post — a slideshow of images with music, not a "
    "video, so there is nothing for a downloader to save; open it in the "
    "browser and Scan — the audio track is often a plain media file the "
    "sniffer can catch."
)
_TIKTOK_PHOTO = re.compile(r"tiktok\.com/\S*/photo/", re.IGNORECASE)


def unsupported_error(text: str) -> dict | None:
    """Is yt-dlp simply refusing to guess this site?

    "Unsupported URL" is not a failure to explain away — it is the signal that
    a sniffer is the way to this video, so the UI must be able to tell it
    apart from a real error (which stays a plain string). A TikTok photo post
    gets its own sentence: it is not a video, and "no extractor" would be
    true but useless.
    """
    text = scrub_secrets(text)
    if "unsupported url" not in text.lower():
        return None
    hint = (UNSUPPORTED_PHOTO_HINT if _TIKTOK_PHOTO.search(text)
            else UNSUPPORTED_HINT)
    return {"message": f"{text} — {hint}",
            "unsupported": True, "hint": hint}


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
        plural = "" if info["count"] == 1 else "s"
        result["message"] = (f"{info['count']} cookie{plural} for {where}"
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
            if looks_like_signin_wall(text):
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
