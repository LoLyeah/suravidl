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
engine downloads over HTTP on-device (`EngineDownloadTest`). Android pins
the pure-python fastapi/pydantic v1 stack — Chaquopy's wheel repo has no
pydantic-core.

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
