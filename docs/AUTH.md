# Authenticated downloads — the routes to a signed-in video

Some videos are only visible to a signed-in account: age-restricted YouTube,
private Facebook or Instagram videos, members-only pages. suravidl never asks
for your password and never signs in for you — it uses the **session your
browser already has**, in the standard form yt-dlp understands: cookies.

A cookie file is as sensitive as a password: whoever holds it can act as you
on that site until it expires. Where cookies live, how they are protected,
and what leaves your machine: [PRIVACY.md](PRIVACY.md) and
[THREAT-MODEL.md](THREAT-MODEL.md).

## The routes

**Desktop / web UI — Settings → Authentication**

- **Cookies file** — a Netscape-format `cookies.txt` (any "Get cookies.txt"
  browser extension exports one). Once set, it is written 0600 and used for
  every download.
- **Cookies from a browser** — read them straight out of an installed
  Chrome / Firefox / Edge / … on the same machine (close that browser
  first). Always fresh; nothing to export by hand.
- **Impersonate (Chrome / Firefox / Safari / Edge)** — for sites that
  fingerprint the browser itself rather than check a cookie: with cookies
  alone they answer "Cannot parse data". The desktop builds include the
  impersonation backend; leave it off everywhere except where it is needed.
- **Test cookies** — proves the setup against a real URL (a title comes
  back, or the reason it failed) before you rely on it.

**Desktop — the extension.** Navigate the site in your already signed-in
browser and hand the video off with the extension: the request travels with
that page's cookies, referer and User-Agent. Nothing to configure, and the
session is exactly as fresh as your browsing.

**Phone — sign in inside the app's browser.** "Find a video on a page" is a
real browser with a sniffer attached: if the video needs an account, sign in
on the page first (it says so), then press play, then Scan, then Download.
That browser's session goes with the handoff. One caveat: Meta (Facebook /
Instagram) often refuses logins from embedded browsers, so on the phone those
two sites want the next route instead.

**Phone — import a cookies.txt.** Export the file from a desktop browser,
copy it to the phone, then Settings → Authentication → Import. It is
encrypted with this device's Keystore key and only decrypted while the app is
running; the screen shows "stored and encrypted, imported <date>" and
**Delete stored cookies** wipes it.

## Per-site notes

- **Facebook** — private / limited videos on desktop need **both** cookies
  and **Impersonate**: cookies prove who you are, impersonation gets past the
  browser fingerprint check. On the phone, import cookies exported from a
  desktop browser. Some videos stay "Cannot parse data" even then — that is
  an upstream extractor limit, not a setting you are missing.
- **Instagram** — cookies work, but the login (`sessionid`) expires in hours,
  and heavy use trips rate limits ("rate-limit reached"). Export or import as
  fresh as you can, use it sparingly, and treat the account as at risk if it
  is precious — Instagram can flag third-party tooling. Logging in from an
  embedded browser is usually refused.
- **YouTube** — age-restricted videos work with cookies from any account
  that can watch them. Bot checks vary by network; when one hits, the desktop
  extension route is the most reliable path.
- **DRM (Netflix, Disney+, Prime Video, Spotify, …)** — never. Cookies do
  not remove Widevine. suravidl says "DRM — not downloadable" instead of
  downloading 60% and failing.

## Verify it yourself

Desktop, five minutes:

1. Log in to the site in your browser.
2. Settings → Authentication: set the cookies file (or pick the browser),
   then press **Test cookies** with a video URL — a title must come back.
3. Facebook only: set Impersonate: Chrome and test again.
4. Queue the video. If it still asks for a sign-in, the cookies went stale —
   redo the export with the login fresh.

Phone, five minutes:

1. Open "Find a video on a page", load the video's page, sign in if asked.
2. Press play for a second, tap Scan, then Download on the strongest find.
3. For Facebook / Instagram instead: export `cookies.txt` on the desktop,
   transfer it, Settings → Authentication → Import — check the stored line,
   then queue the video.
