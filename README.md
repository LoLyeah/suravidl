# vidl

Universal web-video downloader: a yt-dlp wrapper engine + UI, with a browser
extension for detecting videos on any site (VideoDownloadHelper-style, but the
engine is yt-dlp).

Planned targets: Windows, macOS, Linux, Android (web postponed).

## Layout

- `src/vidl_engine/` — Python engine (FastAPI + yt-dlp as a module)
- `extension/` — browser extension (detects videos, hands off to the engine)
- `tests/` — pytest suite, fully offline (local fixture server, real ffmpeg)

## Status (M0)

- [x] Engine PoC: probe, background jobs with progress, HLS merge, header pass-through
- [x] HTTP API: `/health`, `/probe`, `/jobs` (token auth)
- [ ] Extension handoff spike
- [ ] GH Actions: lint + test + Android skeleton build

## Dev

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests/ -q
VIDL_TOKEN=x .venv/bin/python -m vidl_engine.api --port 8787
```

## Limits

DRM-protected streams (Widevine etc.) are out of scope — same as every
downloader of this kind.
