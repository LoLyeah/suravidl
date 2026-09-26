# Capturing video from pages yt-dlp cannot read

yt-dlp extracts video from 1000+ sites by reading the page. When a page hands the
video to a player as a `blob:`/MSE stream, or only after a click, a session or a
same-origin iframe, there is nothing for an extractor to read — so suravidl does
what a browser does: it *watches the page* while you play it, and hands the real
stream to the engine.

The split matters everywhere else in this project: **the engine decides what a
find is** (`POST /classify`) and **what is worth showing** (`POST /sniff/rank`),
so the desktop extension and the phone's in-app browser hide the same fragments
and refuse the same DRM for the same reasons. Shells collect; the engine judges.

## What is promised

- **Direct media URLs** (`.mp4`, `.m3u8`, `.mpd`, `.mp3`, …) work everywhere,
  including on Android's share sheet, with the browser's own headers.
- **A page whose player fetches its stream** — the common case for JS-only sites
  — is found on desktop by the extension and on Android by the in-app browser,
  and handed over with that page's **cookies, User-Agent and the frame it came
  from as the referer**. A guarded stream (signed URL, session cookie, referer
  check) therefore downloads the way it plays.
- **Your verdict is the engine's**: `HLS · 42 MB`, `video · 3.4 MB`,
  `DRM — not downloadable`. A DMCA'd or geo-blocked stream says so, in one line.
- **Hiding is visible.** When a playlist and its fragments are both seen, the
  fragments are hidden *and counted* ("3 fragments belong to a playlist above"),
  never silently dropped.
- **Removing data is specific.** "Clear browsing data" in the in-app browser
  clears cookies, site storage and cache that *this* browser collected, plus
  the list of finds on screen — a record of what was watched — and says both
  of those things, and that your downloads, the vault and any imported
  `cookies.txt` are not touched.

## What is deliberately not promised

- **DRM.** Widevine, PlayReady, FairPlay, SAMPLE-AES: detected, refused, and not
  pursued. This is a boundary, not a backlog item.
- **Fighting ad gates, anti-bot walls or anti-debug JavaScript.** The in-app
  browser is a browser: if a page wants you to watch an ad or solve a challenge,
  you do that yourself. Nothing here defeats detections on purpose — that is how
  a downloader turns into a bot and the site turns into an arms race.
- **A `blob:` stream inside a *cross-origin* frame on Android.** Android's
  `shouldInterceptRequest` is never called for `blob:` URLs at all, so that stream
  has to be seen by hooks *inside* that frame. Ours ride into same-origin frames
  only; a cross-origin frame would need `androidx.webkit`'s document-start
  injection (~100 KB), which is deliberately not taken yet. Its *network*
  requests are still visible, so an ordinary `.m3u8` or `.mp4` inside such a
  frame is found anyway.
- **Segment-only MSE** — a player that never requests a manifest because the
  JavaScript builds one in memory. There is no URL to hand over.
- **Live and growing streams.** A capture hands over a URL, and a live playlist
  is a snapshot; recording it is a different feature (see the plan's backlog).
- **Subtitles for captured streams.** They are not sniffed, because they are not
  media requests. Downloading a video without its subtitles beats not
  downloading it.
- **Any hosted, public version of this.** The engine is loopback-only on
  purpose.

## Desktop (browser extension)

1. Play the video for a second or two — the player has to ask for its stream.
2. Click the suravidl toolbar icon. The badge is the number of finds on the tab.
3. Press **Download with suravidl** on the row you want (the playlist, not the
   fragments — those are hidden with the count shown).

The extension captures requests that *look* like media and responses that *are*
media (`Content-Type: video/*`), so a stream whose URL looks like nothing is
still found. Only media-ish requests are ever inspected — ordinary browsing's
cookies never reach extension storage.

## Android (in-app browser)

Download tab → **🔍 Find a video on a page**:

1. The page opens in an in-app browser. Sign in or dismiss consent if needed —
   whatever you do there is what the handoff will send.
2. **Press play for a second or two.** A player that was never asked for its
   stream has nothing to sniff.
3. Tap **Scan**. Finds are listed newest-first, each with how it was found
   (`network`, `script`, `player`, `MSE`) and the engine's verdict.
4. Tap **Download** on the one you want. It joins the app's Queue tab.
5. **Clear data** in the browser's toolbar wipes what that browser collected —
   cookies, storage, cache *and* the find list above it;
   **Clear list** only empties the find list.

A `blob:`/`MSE` find is shown for context — it is proof the player is streaming,
not something to download. The manifest a few rows above it is the one you want.

## Firefox on Android (a stopgap, and the token)

If you would rather not use the in-app browser, the desktop extension design
also runs in **Firefox for Android**:

1. Install the signed `.xpi` from the release (or add it from
   [addons.mozilla.org](https://addons.mozilla.org) after signing).
2. In the extension's options, set the engine URL to `http://127.0.0.1:8787`
   and paste the token.

The token comes from the engine: **Settings → Network → API token** (masked,
with **Copy**), or `~/.suravidl/token` on a desktop install. Android apps cannot
read each other's private files, so the Settings row is the only in-app way to
get it — which is why it exists.

This route is a stopgap, not the plan: it needs a second browser on the phone and
the extension's own cookie jar, where the in-app browser hands over the cookies
of the very session that is playing.

## How this is verified

- **The engine's rules** are unit-tested (`tests/test_classify.py`,
  `tests/test_rank.py`) and exercised by `POST /classify` / `POST /sniff/rank`.
- **The handoff** is proven **on an emulator** by an instrumented test whose
  fixture is *guarded*: `/guarded.mp4` answers **403** unless the request carries
  the browser's session cookie **and** a referer from the page that embedded it.
  A green run therefore means the captured headers genuinely reached yt-dlp — a
  test that would also pass without them would be decoration.
- **Capture itself** is proven the same way: a fixture page starts a player from
  a shell document, and the test asserts the URL is found and *how* (`via`).
- Both run on API 30 and on a 16 KB page-size API 36 emulator in CI.

## Manual checklist (only a real device can show these)

1. The case this whole feature was
   built against: no `<video>`, a same-origin iframe, an obfuscated player. Open
   it in the in-app browser, play, Scan; if the manifest appears, download it.
   If it does not, that is a data point, not a bug: see "what is not promised".
2. A site you are signed in to: sign in inside the in-app browser, play, Scan,
   Download — and confirm the download succeeds where a plain paste would 403.
3. An HLS page with many fragments: confirm the list shows the playlist and says
   how many fragments were hidden.
4. **Clear data**, then reload the page: confirm a site login is gone (that is
   the point), the find list is empty, and the Queue tab's downloads are not.
