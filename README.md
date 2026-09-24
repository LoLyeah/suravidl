# suravidl

<img src="assets/logo.png" width="96" align="right" alt="suravidl logo" />

Universal web-video downloader: a yt-dlp wrapper engine + UI, with a browser
extension for detecting videos on any site (VideoDownloadHelper-style, but the
engine is yt-dlp).

Planned targets: Windows, macOS, Linux, Android (web postponed).

## Layout

- `src/suravidl_engine/` — Python engine (FastAPI + yt-dlp as a module)
- `extension/` — browser extension (detects videos, hands off to the engine)
- `android/` — Android app (Chaquopy: same engine, embedded Python)
- `tests/` — pytest suite, fully offline (local fixture servers, real ffmpeg)

## Status (M1)

- [x] M0 — engine PoC, extension spike, CORS, CI, Chaquopy APK with yt-dlp bundled
- [x] Job persistence (SQLite): history survives restarts; crashed jobs → `interrupted`
- [x] Cancel (queued instantly, running via progress-hook interrupt) + retry (reuses url/fmt/headers)
- [x] Format selection (`fmt` on `/jobs`), yt-dlp self-update (`POST /update`), `/version`
- [ ] M2 — web UI MVP + desktop binaries (PyInstaller)
- [ ] M3 — extension MVP polish (cookie capture, Firefox)
- [ ] M4 — Android app (foreground service, downloads UI)

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
