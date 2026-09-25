# suravidl

<img src="assets/logo.png" width="96" align="right" alt="suravidl logo" />

Universal web-video downloader: a yt-dlp wrapper engine + UI, with a browser
extension for detecting videos on any site (VideoDownloadHelper-style, but the
engine is yt-dlp).

Planned targets: Windows, macOS, Linux, Android (web postponed).

## Layout

- `src/suravidl_engine/` — Python engine (FastAPI + yt-dlp as a module)
- `src/suravidl_engine/web/` — the UI, served by the engine at `/`
- `extension/` — browser extension (detects videos, hands off to the engine)
- `android/` — Android app (Chaquopy: same engine, embedded Python)
- `tests/` — pytest suite, fully offline (local fixture servers, real ffmpeg)

## Browser extension

Detects videos on any page (webRequest observer) and hands them to the engine
with the site's cookies/UA/referer so logged-in sites work. Badges the count
of detected media per tab.

- **From a release**: `suravidl-extension-chrome.crx` (signed, stable ID),
  `suravidl-extension-firefox.xpi`, or the `-chrome.zip` / `-firefox-src.zip`
  for loading unpacked.
- **From the repo**: `chrome://extensions` → Developer mode → Load unpacked
  → select `extension/` (Chrome/Edge/Brave). Firefox: copy
  `extension/firefox/manifest.json` over `extension/manifest.json` first
  (or `npx web-ext run --source-dir <dir-with-firefox-manifest>`).

Install caveats, so nobody is surprised: Chrome no longer installs
off-store `.crx` files by double-click (blocked since ~2019 except via
enterprise policy or Chromium builds) — for most users *Load unpacked* is
the way. The signed crx's stable identity is
`habomdhpjdcddccplapkncnfokpknfle` (that's the ID to pin in enterprise
policy). Firefox stable refuses unsigned `.xpi` — the release one installs on
Firefox Developer Edition / Nightly, or after the add-on gets signed on
addons.mozilla.org (free, automated once API keys are wired in).

The engine token is set once in the extension options page (it's printed when
the engine starts). Header capture is whitelisted engine-side (cookie,
user-agent, referer, origin, accept) — nothing else from the page reaches
yt-dlp.

## Updates

- **yt-dlp**: `POST /update` (button in the UI) pip-upgrades yt-dlp in place.
- **suravidl itself**: `GET /update-check` compares the engine version with the
  latest GitHub release; the UI shows a "⬆ update available" link when one
  exists. Anonymous checks work out of the box (public repo); set
  `SURAVIDL_GITHUB_TOKEN` if you ever point it at a private repo/fork.

Releases ship native formats: `suravidl-windows-x64.exe` (double-click),
`suravidl-linux-x64.AppImage` (chmod +x, double-click — needs FUSE, or run
with `--appimage-extract-and-run`), and `suravidl-macos-arm64.dmg` (drag
suravidl.app to Applications; it's unsigned, so first launch needs
right-click → Open). No raw binaries and no zips in the release; if you
want a bare extension-less binary, `./suravidl-linux-x64.AppImage
--appimage-extract` unpacks one to `squashfs-root/usr/bin/suravidl`.

## Desktop app

`pyinstaller suravidl.spec` → single-file binary. It serves the engine on
127.0.0.1 and opens **its own window** (pywebview: WebView2 on Windows, WKWebView
on macOS, WebKitGTK on Linux) with the same UI — no browser tab. The header has
minimize and quit buttons in window mode. If no webview runtime is present
(older systems, or the Linux frozen build without GTK bindings) it falls back
to opening your default browser. Tray icon (Open / Downloads / Quit) appears in
browser mode.

Settings (gear button in the app, persisted next to the db):
- appearance: **Light / Dark / AMOLED** themes (AMOLED = true-black for OLED screens),
  applied instantly and remembered per install
- glass style: **Frosted** (classic blur) or **Liquid** (heavier blur, saturation
  boost, specular highlights) — pick per taste
- download folder (applies to new jobs immediately)
- concurrent downloads (1–4, live-adjustable — waiting jobs start as you raise it)
- open the folder when a download finishes (desktop window app only)
Finished downloads get an "Open folder" button in the desktop app
(`POST /jobs/{id}/reveal`).

Linux note: the frozen binary falls back to the browser — bundled GTK/PyGObject
isn't practical in PyInstaller. Run from source (`pip install -e .` plus
`pywebview`, `python3-gi`, `gir1.2-webkit2-4.1`) to get the native window on
Linux.
`--selftest` boots and health-checks itself (used by CI).
CI builds Linux/Windows/macOS binaries on tags (`release.yml`).

## Android app

Same engine, same UI: Chaquopy embeds Python 3.11 + the engine + yt-dlp
inside the APK. A foreground service runs uvicorn on 127.0.0.1:8787
(persistent notification with active-download count); the activity is a
WebView kiosk of the engine UI. Files land in the app's external dir
(`Android/data/com.suravidl.app/files/Movies/suravidl`).

Build with `gradle -p android assembleDebug` (needs the Android SDK; CI does
it in `android.yml`). The emulator instrumentation test proves the real
engine downloads over HTTP on-device (`EngineDownloadTest`) and that the full
app boot path works (`AppStartupTest`: MainActivity → EngineService → /health).

- **16 KB page size devices** (Android 15+): native libs ship 16 KB-aligned
  (Chaquopy 17); CI verifies ELF alignment in the release APK and runs the
  full test suite on a 16 KB page size emulator.
- If the app ever misbehaves, it writes a log readable with any file manager
  at `Android/media/com.suravidl.app/logs/` (crash traces + engine errors);
  the in-app error page shows the same log on screen.

Android pins the pure-python fastapi/pydantic v1 stack — Chaquopy's wheel
repo has no pydantic-core.

## Status (M7)

- [x] M0 — engine PoC, extension spike, CORS, CI, Chaquopy APK with yt-dlp bundled
- [x] Job persistence (SQLite): history survives restarts; crashed jobs → `interrupted`
- [x] Cancel (queued instantly, running via progress-hook interrupt) + retry (reuses url/fmt/headers)
- [x] Format selection (`fmt` on `/jobs`), yt-dlp self-update (`POST /update`), `/version`
- [x] M2 — web UI (probe → formats → download w/ progress, history, update button)
- [x] Desktop binary: PyInstaller onefile, tray + browser open, `--selftest` for CI
- [x] M3 — extension MVP: cookie/UA/referer capture (engine whitelist), badge count,
      Firefox port (MV2 manifest, web-ext lint 0/0/0), real-Chrome E2E
      (`scripts/ext_e2e.py`: handoff, detection, header capture, popup render)
- [x] M4 — Android app: embedded engine (Chaquopy, Python 3.11), foreground service,
      WebView UI, on-device download test on CI emulator; APK verified
- [x] M5 — polish: release-signed APK (GitHub secrets), launcher icons,
      MediaStore gallery export (Android 10+), tagged release v0.5.0 with
      all binaries + APK
- [x] M6 — desktop: standalone app window (pywebview) with minimize/quit,
      settings (download folder, live concurrency, reveal-on-complete),
      extension crx/xpi in releases, AppImage + dmg native formats
- [x] M7 — UI overhaul: aurora glass design, Light/Dark/AMOLED themes,
      Frosted/Liquid glass switch, toasts + glass modals, reveal-in-folder,
      selection cards in settings
- [x] M8 — motion pass: staggered card/row entrances, animated modals,
      drift aurora, smooth in-place progress, scroll-shadow header;
      Android: background downloads (wake lock + auto-resume of interrupted
      jobs on restart) and "Quit completely" to free memory
- [x] M9 — authentication for age-restricted / private / bot-gated videos:
      cookies.txt file (desktop Browse…, on Android Import via the system
      picker) and "use cookies from <browser>" (desktop); cookies are copied
      per run so yt-dlp's refresh can never corrupt or race your export;
      sign-in errors in the UI now point at Settings → Authentication
- [x] M10a — cookie safety: cookie values are never persisted (redacted at
      rest and in API payloads; live value is memory-only), private file modes
      (jobs.db / settings / token 0600, dirs 0700, per-run copies 0600 and
      deleted), rows from older versions scrubbed on start
- [x] M11 — audio-only downloads (first tier-1 feature): "keep original"
      (no conversion, no ffmpeg anywhere), M4A and MP3 (192 kbps) presets on
      the probe card; the Android APK now bundles a static ffmpeg 8.1.3 CLI
      (arm64-v8a + x86_64, 16 KB-page aligned, LGPL) built by
      `ffmpeg-android.yml` and verified on-device by instrumentation tests.
      Desktop keeps using the system ffmpeg (errors say so and point at the
      "keep original" option when it is missing)
- [x] M11b — tier-1 download options + a settings shell that can hold them:
      **playlists** (probe detects them and lists entries; item ranges like
      `1-10,15` or *all*; a playlist URL with no explicit range still yields
      one file — mass downloads are always opt-in), **subtitles**
      (sidecar `.vtt` or embedded, language list, auto-captions),
      **metadata & thumbnail embedding** (real ffmpeg postprocessors, wired
      exactly like the CLI does), **filename templates** (validated: no paths,
      `%(ext)s` required), **network** (speed limit, parallel fragments,
      http/socks proxy), **download archive** ("skip what I already have",
      reported as such instead of silently re-fetching), and **SponsorBlock**
      (mark as chapters or remove segments). The settings modal is now
      sub-tabbed — General · Media · Network · Authentication · Advanced ·
      Device — so options stop piling into one column; progress reports
      *video 3/10* while a playlist runs.
- [x] M12 — the Advanced tier, without cluttering anything: **raw yt-dlp
      arguments** (default-OFF; a switch plus a field in Settings →
      Advanced) parsed with yt-dlp's own parser — never a shell — where the
      engine refuses the flags it owns (`--exec`/`--batch-file`/`--cookies`/
      playlists/archive/…) with the reason spelled out, and only options the
      arguments actually changed are merged (so a raw string can never
      silently clobber the app's own choices). The chosen arguments are
      snapshotted onto each job, echoed in the job row, and reused by retry.
      Plus **an option browser**: `GET /options` generates the full
      catalogue (322 options, 17 groups) from the installed parser — so it
      is complete by construction — searchable in the UI, one click inserts
      a flag into the raw-args field. Also here: the update banner is now a
      real button, because `target="_blank"` still cannot open a window from
      inside a pywebview or Android shell — it now asks the desktop shell
      (or the Android bridge) to open your actual browser.
- [x] M13 — phone-shaped, honest about Android's storage rules, and cookies
      that are unreadable at rest: the **settings dialog is a real sheet**
      on phones (one scrollable tab row, body scrolls, Save pinned at the
      bottom — it used to sit below the fold), **Frosted vs Liquid** are now
      unmistakably different (flat matte vs glossy sheen, with a one-line
      hint each) instead of two identical swatches, and the download folder
      line no longer claims you can browse `Android/data` — it says where
      the files really are *and* gives every finished job **Open** and
      **Share** buttons (a FileProvider grant, so the player can read a file
      no file manager may browse). Audio now lands in `Music/suravidl` too,
      not just video in `Movies/suravidl`. Cookies get a **Keystore vault**:
      AES-256-GCM under a non-exportable key, decrypted only into an
      owner-only session file that is deleted on quit/delete/start — plus a
      "delete stored cookies" button and a written
      [threat model](docs/THREAT-MODEL.md). And the reason the UI looked
      v0.11-old on v0.13: `/static/*` came from Starlette with a
      `Last-Modified` validator, which an Android WebView is allowed to
      serve from its heuristic cache — asset URLs are now version-stamped
      and served `no-store`, so a mixture of two releases cannot happen
      again.
- [x] M14 — the format table finally answers "what am I getting?", and
      downloads can be cleaned up where they live: every row now says what
      the stream **contains** — *video + audio*, *video only (sound is added
      on download)*, *audio only*, or *single file* for a direct link whose
      tracks the site never described — with codec names in human form
      (H.264 / VP9 / AV1 / AAC…) and the duplicate rows sites publish for the
      same stream (DASH + HLS, one without a size) collapsed to one, keeping
      the copy that knows its size. Picking a video-only stream pairs it with
      the site's audio track automatically, so a quality pick can no longer
      quietly produce a silent file. Sizes the site doesn't advertise now
      read *unknown* (with the reason on hover) instead of a bare `?`.
      Settings → Device gained **Downloaded files**: it shows how much is in
      the app's folder and wipes it (sidecars included, plus the Gallery/Music
      copies this app made) — the folder is app-private on Android, so the app
      has to offer that cleanup itself. `GET /files/summary` +
      `POST /files/clear` (completed job rows go with their files) and an
      emulator test that an imported copy is really removable.
- [ ] M15+ — what is left: curated option groups (verbosity/workarounds/geo),
      the full four-tab shell (Download · Queue · Settings · yt-dlp) →
      `docs/PLAN-full-ytdlp.md`

## API (v0.1)

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | – | liveness + engine version |
| `GET /version` | Bearer | engine + yt-dlp versions |
| `POST /update` | ✓ | self-update yt-dlp (pip) |
| `POST /probe` | ✓ | metadata + formats for a URL |
| `POST /jobs` | ✓ | enqueue download (`url`, `fmt`, `headers`) |
| `GET /jobs`, `GET /jobs/{id}` | ✓ | history / status |
| `POST /jobs/{id}/cancel` | ✓ | cancel queued/running |
| `POST /jobs/{id}/retry` | ✓ | re-run error/interrupted/cancelled |
| `POST /jobs/{id}/reveal` | ✓ | open the finished file (desktop only) |
| `GET/POST /settings` | ✓ | download dir, concurrency, reveal-on-complete |
| `GET /app/info` | ✓ | whether a desktop shell (window) is attached |
| `POST /app/minimize`, `/app/quit` | ✓ | window controls (desktop only) |

## Dev

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests/ -q
SURAVIDL_TOKEN=x .venv/bin/python -m suravidl_engine.api --port 8787
.venv/bin/python scripts/smoke.py   # full live end-to-end check
```

## Limits

DRM-protected streams (Widevine etc.) are out of scope — same as every
downloader of this kind.
