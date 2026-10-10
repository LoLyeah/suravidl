# suravidl

<img src="assets/logo.png" width="96" align="right" alt="suravidl logo" />

Universal web-video downloader. One engine (Python + [yt-dlp](https://github.com/yt-dlp/yt-dlp)
as a library, FastAPI on top), one UI, and thin shells around them: browser
extension, desktop app, Android app. It downloads anything yt-dlp understands
(1000+ sites) plus raw `.mp4`/`.webm`/`.m3u8`/`.mpd` links, and never touches DRM.

[![release](https://img.shields.io/github/v/release/LoLyeah/suravidl?style=for-the-badge&label=release&logo=github&logoColor=white)](https://github.com/LoLyeah/suravidl/releases/latest)
[![build](https://img.shields.io/github/actions/workflow/status/LoLyeah/suravidl/ci.yml?style=for-the-badge&label=build&logo=githubactions&logoColor=white)](https://github.com/LoLyeah/suravidl/actions/workflows/ci.yml)
[![downloads](https://img.shields.io/github/downloads/LoLyeah/suravidl/total?style=for-the-badge&label=downloads&logo=github&logoColor=white)](https://github.com/LoLyeah/suravidl/releases)

[![mozilla add-on](https://img.shields.io/amo/v/suravidl.svg)](https://addons.mozilla.org/en-US/firefox/addon/suravidl/)
[![chrome / edge](https://img.shields.io/badge/chrome%20%2F%20edge-zip-blue.svg)](https://github.com/LoLyeah/suravidl/releases/latest/download/suravidl-extension-chrome.zip)

[releases](https://github.com/LoLyeah/suravidl/releases/latest) ·
history: [docs/PLAN-full-ytdlp.md](docs/PLAN-full-ytdlp.md) ·
next: [docs/PLAN-next-features.md](docs/PLAN-next-features.md) ·
reviews: [docs/audits/](docs/audits/)

## What it does

- **Probe first**: paste a link, see the real formats, pick one, download.
- **Paste a list**: several links at once are each checked and named before
  anything queues — tick the good ones, queue just those.
- **Live streams**: a live link records while it plays (● REC, time on air,
  no fake percentage); **Stop & keep** keeps everything recorded so far.
- **Watch list**: follow a playlist or channel — new videos come in on their
  own, and nothing you already have is ever grabbed again.
- **Playlists and channels**: browse entries, tick the ones you want or type a range.
- **Audio only**: keep the native stream, or convert to m4a / MP3 192–320k / FLAC / Opus.
- **Subtitles**: pick a language from what the site actually offers; download as
  files, embed them, or convert to `.srt` for TVs.
- **Clips**: `0:10-0:20` for one download, or click a chapter to fill the times.
- **Batch**: paste up to 20 links, queue them all; bad lines are named, not swallowed.
- **Pause and resume**: pause keeps the bytes it already fetched.
- **Tidy output**: subfolder per playlist or per site, and MP4/MKV remuxing so the
  file opens in QuickTime, iOS Files and Smart TVs — not only in VLC.
- **Editable retries**: a failed job's settings load back into the form.
- **Play it here**: finished downloads play in the page, no file hunting.
- **Signed-in sites**: import a `cookies.txt`, read cookies from a desktop browser,
  or sign in inside the phone's in-app browser — [docs/AUTH.md](docs/AUTH.md) has the
  route that fits each site.
- **Pages yt-dlp cannot read**: the extension (desktop) and the in-app browser
  (Android) watch a page as it plays, then hand the stream to the engine with the
  page's own cookies — see [docs/SNIFFING.md](docs/SNIFFING.md) for what that
  catches and what it deliberately does not.
- Also: SponsorBlock, metadata/thumbnail embedding, speed limits, retries,
  per-download overrides and saved presets, auto-resume after a restart,
  Light/Dark/AMOLED themes, and a storage view with a guarded wipe.

## Install

From [Releases](https://github.com/LoLyeah/suravidl/releases/latest):

- `suravidl-windows-x64-setup.exe` — the installer: per-user, no admin
  prompts, Start Menu entry and an uninstall in Windows Settings.
- `suravidl-windows-x64.exe` — the portable exe: double-click to run; it needs
  nothing installed. Run it once with `--install-desktop` and it appears in
  your Start Menu like an installed app (`--uninstall-desktop` takes it back
  out).
- `suravidl-linux-x64.AppImage` — `chmod +x`, then run it (needs FUSE; otherwise
  `--appimage-extract-and-run`). `--install-desktop` puts it in your applications
  menu (and lights up docks that read the launcher count).
- `suravidl-macos-arm64.dmg` — drag to Applications. Unsigned, so the first
  launch needs right-click → Open; after that it updates itself in place, like
  Windows.
- `app-release.apk` — Android (see below). [Obtainium](https://github.com/ImranR98/Obtainium/releases/latest) can also watch these releases and install the updates for you.
- Extension: Firefox — [Mozilla Add-ons](https://addons.mozilla.org/en-US/firefox/addon/suravidl/);
  Chrome/Edge/Brave — `suravidl-extension-chrome.zip` (load unpacked), both below.

From source:

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m suravidl_engine.api        # UI on http://127.0.0.1:8787
```

The engine binds to loopback, keeps its database in `~/.suravidl/`, and prints
an API token on start (or takes `SURAVIDL_TOKEN`).

## Browser extension

Watches media requests on every page and hands the interesting ones to the
engine with that site's cookies/UA/referer, so logged-in sites work. The
popup keeps it simple: it names what the page is playing, and hands the
stream over — the engine probes it (with those captured details) and the
app's window opens on the format list, where you pick the quality. When a
page offered several streams, the chooser names each one — its resolution
or its real filename when the URL shows one — and a small URL door on any
row unfolds the full raw link, for when you want the details. In a
hurry, *Quick download* takes the best quality straight away instead. The
tab badge shows how many videos were detected.

- **Firefox**: install from [Mozilla Add-ons](https://addons.mozilla.org/en-US/firefox/addon/suravidl/) —
  signed and reviewed by Mozilla, and it updates itself from there.
- **Chrome / Edge / Brave**: download `suravidl-extension-chrome.zip` from
  [Releases](https://github.com/LoLyeah/suravidl/releases/latest), unzip it,
  then `chrome://extensions` → Developer mode → *Load unpacked* → the
  unzipped folder. (Chrome takes extensions only from its Web Store or an
  unpacked folder in developer mode; off-store `.crx` installs have been
  blocked since ~2019 and no Web Store listing exists, so unpacked is the
  supported route. After an update that touches the extension, re-download
  the zip and hit *Reload* on that page.)
- **From the repo** (working on the extension itself): the same *Load
  unpacked* flow with `extension/` — for a Firefox copy, overwrite
  `extension/manifest.json` with `extension/firefox/manifest.json` first
  (that swap is exactly what the Mozilla Add-ons build does).
- Paste the engine token once in the extension's options page — the engine's
  **Settings → Authentication** shows it (masked, with a Copy button) if you don't want
  to open `~/.suravidl/token`. The popup's footer links straight to it.
- The media list it watches for comes from the engine (`GET /sniff/patterns`),
  so a new format is an engine update, not an extension update; a response that
  says `video/*` is picked up even when its URL looks like nothing.

## Desktop app

`pyinstaller suravidl.spec` builds one file that serves the engine on loopback
and opens **its own window** (pywebview: WebView2 / WKWebView / WebKitGTK). With
no webview runtime it falls back to your browser and shows a tray icon instead.
`--selftest` boots and health-checks itself (CI uses it); `release.yml` builds
all three platforms on tags.

Linux note: the frozen build deliberately falls back to the browser — bundling
GTK/PyGObject isn't practical. Run from source (plus `pywebview`, `python3-gi`,
`gir1.2-webkit2-4.1`) for the native window.

## Android app

Same engine, same UI: Chaquopy embeds Python 3.11 + the engine + yt-dlp in the
APK. A foreground service runs uvicorn on `127.0.0.1:8787` (notification with
the active-download count) and the activity is a WebView kiosk of the engine UI.

- **Installs on Android 7.0 (API 24) and newer — 64-bit devices only**
  (`arm64-v8a`, `x86_64`). API 24 isn't arbitrary: it is Chaquopy's own floor
  for Python 3.11. 32-bit-only phones are left out on purpose — an extra
  `armeabi-v7a` build would nearly double the APK for hardware that stopped
  shipping years ago. Newer Android is what CI tests against (15, including
  16 KB page-size builds).
- Files: `Android/data/com.suravidl.app/files/Movies/suravidl` (video) and
  `…/Music/suravidl` (audio). On **Android 10+** the app also makes a
  Gallery/Music copy, which is the part your phone's apps can open — on
  Android 7–9 the app folder is already reachable, so no copy is made and the
  UI says so instead of pointing at an empty place. Finished jobs get **Open**
  and **Share** either way.
- Share a link from any app and it lands in the download box, probed and ready.
- If something misbehaves, the in-app error page shows the log; on Android 10+
  a copy readable by any file manager sits at
  `Android/media/com.suravidl.app/logs/`.
- 16 KB page-size devices (Android 15+) are supported: native libs are
  aligned, and CI runs the suite on a 16 KB emulator. The UI needs a current
  **Android System WebView** (Play Store updates it independently of the OS);
  an older one gets a "update WebView" note instead of a blank page, since the
  UI's JavaScript needs Chrome 80.
- Build: `gradle -p android assembleDebug` (needs the Android SDK; CI does it).
  Emulator tests cover the on-device engine download, the full boot path, the
  share target, the sniffer browser, and the handoff.
- **🔍 Find a video on a page** (Download tab) opens an in-app browser: play the
  video for a second, tap **Scan**, then **Download** on what it found. It uses
  the phone's own Android System WebView — nothing browser-sized ships in the
  APK (~+17 KB) — and the finds come back with the page's cookies, its
  User-Agent and the frame they came from, so guarded streams still work.

## Pages yt-dlp cannot read

Not every site is a yt-dlp site. Some hand the video to the player as a
`blob:`/MSE stream, some only after a click, some behind a session or a
same-origin iframe. For those, suravidl *watches the page* instead of parsing
it — and the judgement about what it found stays in the engine, so every shell
agrees on it:

| where the video is | desktop | Android | CLI |
| --- | --- | --- | --- |
| a direct media URL (`.mp4`, `.m3u8`, `.mpd`) | paste it | paste or share it | `suravidl <url>` |
| a site yt-dlp knows (1000+) | paste it | share it | `suravidl <url>` |
| a plain `<video>` tag | paste it (generic extractor) | paste it | `suravidl <url>` |
| a player that fetches its own stream (often JS-only, `blob:`/MSE) | extension: play, then *Choose quality in suravidl* | **🔍 Find a video on a page** → play → **Scan** → **Download** | — |
| DRM (Widevine, PlayReady, SAMPLE-AES) | detected and refused | detected and refused | detected and refused |
| a `blob:` inside a *cross-origin* frame | extension sees the network request | network layer only | — |

What all of that means in practice — including the parts that are deliberately
not attempted — is in **[docs/SNIFFING.md](docs/SNIFFING.md)**.

## Updates

- **yt-dlp**: one button in the UI (`POST /update`) — a pip setup upgrades in
  place; packaged builds fetch the newest release from PyPI (sha256-verified)
  and apply it on the next start. The downloaded copy can be removed again
  from the same tab — the bundled one takes over from the next start.
- **suravidl**: the app reads the newest release's manifest (`GET /update-check`),
  downloads the right asset, verifies its SHA-256, and installs it in place — one
  tap on Windows and macOS, one system confirmation on Android; every other
  platform keeps the download link. Details: [docs/UPDATES.md](docs/UPDATES.md).
- **Obtainium (Android)**: [Obtainium](https://github.com/ImranR98/Obtainium/releases/latest) watches this
  repo's releases and offers every new `app-release.apk` — install it, tap *Add app*, paste
  `https://github.com/LoLyeah/suravidl`. It installs the same signed APKs as the in-app updater,
  so the two never conflict. One-tap link once Obtainium is on the phone (send it over and
  open it):
  `obtainium://app/%7B%22id%22%3A%22com.suravidl.app%22%2C%22url%22%3A%22https%3A%2F%2Fgithub.com%2FLoLyeah%2Fsuravidl%22%2C%22author%22%3A%22LoLyeah%22%2C%22name%22%3A%22suravidl%22%7D`

## Privacy and security

- Cookies are credentials: the Android vault encrypts imports with AES-256-GCM
  and a Keystore-held key; API responses and the database only ever carry a
  placeholder.
- Only `cookie`, `user-agent`, `referer`, `origin` and `accept` are allowed from
  the extension — nothing else from a page reaches yt-dlp.
- The engine listens on loopback only, and every route but `/health` needs the
  token. On Android the page holding that token is gated behind a per-install
  key, because loopback is shared with every other app on the phone.
- No accounts, no cloud, no telemetry. Downloads stay on your machine.

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | – | liveness + version |
| `GET /version` | ✓ | engine + yt-dlp versions |
| `POST /probe` | ✓ | metadata, formats, subtitles, chapters, live flag |
| `POST /jobs` | ✓ | queue one download |
| `POST /jobs/batch` | ✓ | queue up to 20 links |
| `GET /jobs`, `GET /jobs/{id}` | ✓ | history / status |
| `GET /jobs/{id}/stream` | ✓¹ | play a finished file (Range/206) |
| `POST /jobs/{id}/cancel` / `pause` / `resume` / `retry` | ✓ | job control |
| `POST /jobs/{id}/delete` | ✓ | one job: file + sidecars + row |
| `POST /jobs/{id}/reveal` | ✓ | open the finished file (desktop only) |
| `GET /archive`, `POST /archive/forget` | ✓ | the download archive |
| `GET/POST /settings`, `GET /presets` | ✓ | settings and presets |
| `GET /files/summary`, `POST /files/clear` | ✓ | storage; the wipe needs `{"confirm": "delete"}` |
| `POST /update` | ✓ | self-update yt-dlp |
| `POST /classify` | ✓ | what is this URL? (video/hls/dash/drm/audio/page/unknown) |
| `GET /sniff/patterns` | ✓ | the one media-pattern list every shell prefilters with |
| `POST /sniff/rank` | ✓ | which finds are worth showing (hides fragments of a playlist that is also here, and says why) |
| `GET /app/info`, `POST /app/minimize`, `/app/quit` | ✓ | desktop window controls |

¹ Also accepts `?token=` because an HTML `<video>` cannot send a header.

## Layout

- `src/suravidl_engine/` — engine (FastAPI + yt-dlp), plus the UI it serves at `/`
- `extension/` — Chrome MV3 / Firefox MV2 extension
- `android/` — Kotlin + Chaquopy app
- `suravidl.spec`, `scripts/` — desktop bundling, smoke test, extension E2E
- `tests/` — pytest suite, fully offline (fixture servers + real ffmpeg)

## Dev

```bash
.venv/bin/python -m pytest tests/ -q -n auto   # 1209 tests, no network
.venv/bin/python scripts/smoke.py        # live end-to-end against a real engine
node --check src/suravidl_engine/web/app.js
```

## Limits

- **DRM is out of scope.** Widevine and friends are not supported, and that will
  not change.
- **No hosted web version.** A public downloader is an abuse magnet; the engine
  is loopback-only. Exposing it yourself is your call.
- **Live streams** are recorded as the site serves them; "from the beginning"
  works only while the site still has it.
- **MKV/WebM playback** depends on the device: Android and browsers vary, which
  is why remuxing to MP4 exists.
- **Capturing a JS-only player is not always possible.** A stream the browser
  never sees as a URL (segment-only MSE, a `blob:` inside a cross-origin frame
  on Android, live and growing HLS) cannot be handed over, however hard anything
  looks. The app says so instead of producing a broken file — the details are in
  [docs/SNIFFING.md](docs/SNIFFING.md).
- **Android logins** are still cookie imports, and the in-app browser is the
  other way in: sign in *there* and its cookies are the ones handed to the
  engine. It borrows the phone's Android System WebView, so nothing
  Chromium-sized ships in the APK.

## Licence

MIT — see [LICENSE](LICENSE). The privacy policy and the store details are in
[docs/PRIVACY.md](docs/PRIVACY.md) and [docs/AMO-SUBMISSION.md](docs/AMO-SUBMISSION.md).
