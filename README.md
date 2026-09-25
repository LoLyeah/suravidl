# suravidl

<img src="assets/logo.png" width="96" align="right" alt="suravidl logo" />

Universal web-video downloader. One engine (Python + [yt-dlp](https://github.com/yt-dlp/yt-dlp)
as a library, FastAPI on top), one UI, and thin shells around them: browser
extension, desktop app, Android app. It downloads anything yt-dlp understands
(1000+ sites) plus raw `.mp4`/`.webm`/`.m3u8`/`.mpd` links, and never touches DRM.

Latest release: [v0.22.0](https://github.com/LoLyeah/suravidl/releases/latest) ·
history: [docs/PLAN-full-ytdlp.md](docs/PLAN-full-ytdlp.md) ·
reviews: [docs/audits/](docs/audits/)

## What it does

- **Probe first**: paste a link, see the real formats, pick one, download.
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
- **Signed-in sites**: import a `cookies.txt`, or read cookies from a desktop browser.
- Also: SponsorBlock, metadata/thumbnail embedding, speed limits, retries,
  per-download overrides and saved presets, auto-resume after a restart,
  Light/Dark/AMOLED themes, and a storage view with a guarded wipe.

## Install

From [Releases](https://github.com/LoLyeah/suravidl/releases/latest):

- `suravidl-windows-x64.exe` — double-click.
- `suravidl-linux-x64.AppImage` — `chmod +x`, then run it (needs FUSE; otherwise
  `--appimage-extract-and-run`).
- `suravidl-macos-arm64.dmg` — drag to Applications. Unsigned, so the first launch
  needs right-click → Open.
- `app-release.apk` — Android (see below).
- Extension: `suravidl-extension-chrome.crx` / `suravidl-extension-firefox.xpi`
  (see below).

From source:

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m suravidl_engine.api        # UI on http://127.0.0.1:8787
```

The engine binds to loopback, keeps its database in `~/.suravidl/`, and prints
an API token on start (or takes `SURAVIDL_TOKEN`).

## Browser extension

Watches media requests on every page and hands the interesting ones to the
engine with that site's cookies/UA/referer, so logged-in sites work. The tab
badge shows how many videos were detected.

- **From the repo**: `chrome://extensions` → Developer mode → Load unpacked →
  pick `extension/`. For Firefox, copy `extension/firefox/manifest.json` over
  `extension/manifest.json` first.
- **Install caveats, so nobody is surprised**: Chrome has blocked off-store
  `.crx` installs since ~2019 (enterprise policy or Chromium builds only) — use
  *Load unpacked*, or pin the signed ID `habomdhpjdcddccplapkncnfokpknfle`.
  Firefox stable refuses unsigned `.xpi`; the release one works on Developer
  Edition/Nightly, or after signing on addons.mozilla.org.
- Paste the engine token once in the extension's options page.

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
  aligned, and CI runs the suite on a 16 KB emulator.
- Build: `gradle -p android assembleDebug` (needs the Android SDK; CI does it).
  Emulator tests cover the on-device engine download, the full boot path, and
  the share target.

## Updates

- **yt-dlp**: one button in the UI (`POST /update`) upgrades it in place.
- **suravidl**: `GET /update-check` compares against the newest GitHub release and
  the UI offers a link when there is one.

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
.venv/bin/python -m pytest tests/ -q     # 310 tests, no network
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
- **Android logins** are cookie imports — there is no in-app browser to sign in
  with (that would mean a 100 MB Chromium and constant anti-bot breakage).
