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

- **Chrome/Edge/Brave**: `chrome://extensions` → Developer mode → Load unpacked
  → select `extension/`
- **Firefox**: same, selecting `extension/` after copying
  `extension/firefox/manifest.json` over `extension/manifest.json`
  (or `npx web-ext run --source-dir <dir-with-firefox-manifest>`)

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

Releases ship both raw binaries (`suravidl-windows-x64.exe`, `suravidl-linux-x64`,
`suravidl-macos-arm64`) and zips — unzip preserves the executable bit, which
plain downloads don't; on macOS/Linux use `chmod +x suravidl-*` after a raw
download.

## Desktop app

`pyinstaller suravidl.spec` → single-file binary: serves the engine on
127.0.0.1, opens the browser, tray icon (Open / Downloads / Quit) when a
display is available. `--selftest` boots and health-checks itself (used by CI).
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

## Status (M4)

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
