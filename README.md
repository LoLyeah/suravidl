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
Sharing a link from another app lands in the download box (`ShareTargetTest`):
prefilled and probed, format picking unchanged.

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
- [x] M15 — the four-tab shell + the curated option groups. The one long page
      is now **Download · Queue · Settings · yt-dlp**, hash-routed
      (`#download` … `#ytdlp`) and remembered between launches: desktop gets a
      left rail, phones a bottom segmented bar with the active-downloads badge
      on Queue. Settings and the option catalogue stopped being modals — they
      are tabs now, so nothing is buried behind a button. The **yt-dlp tab**
      carries the curated groups (verbose log · IP version · skip TLS checks ·
      pause between requests · geo bypass + country · extractor arguments) with
      validation in the engine, network ones applied to probing too, and a
      picker that writes into the raw-arguments field. Raw arguments stay
      default-OFF: the editor only appears once enabled in Settings → Advanced.
- [x] M16 — one download, one trash button, and the phone's mystery blob:
      every finished row (and every error/cancelled one) now carries **Delete**,
      which asks first, names the file, and takes the file, its sidecars
      (`.info.json`, thumbnail, subtitles) and the row with it — on Android the
      Gallery/Music copy this app made goes too. A still-running download is
      stopped first, after its own confirm. `POST /jobs/{id}/delete` refuses to
      delete while the download is running, refuses paths outside the download
      folder, and reports what it actually removed (`deleted`, `freed_bytes`).
      The blob those settings fields wore was not the WebView and not the blur:
      a bare `.fill` selector (the progress bar) was also matching the settings
      layout helper `<div class="col fill">`, painting a 339×114 progress-bar
      gradient over the panel — component styles are now scoped to their
      component and a regression test keeps them there. Android also lost its
      translucency-without-blur look: where `backdrop-filter` doesn't render, a
      7 %-opaque card is a stain, not glass, so the phone app gets solid panels.
- [x] M17 — per-download options and presets. The Download tab grew a
      collapsed **“This download only”** block: subtitles, SponsorBlock, tag
      embedding and per-job yt-dlp arguments that apply to the *next* download
      and leave your saved settings alone (the audio row and playlist items
      were already per-job). Everything is a **validated patch** — same
      validators as the settings screen, and a whitelist that keeps app-level
      keys (download folder, concurrency, theme) out of a job, so the API
      cannot smuggle `cookiefile`/`outtmpl` into yt-dlp. The patch is stored
      with the job, which is why a retry re-runs exactly what you asked for,
      and every row now wears a `⚙ N options` chip (hover = which).
      **Presets** became real: Settings → Presets lists the built-in audio
      intents and saves your own bundles ("save the options that differ from
      the defaults"), validated on the way in, stored in `presets.json`
      (0600), deletable, and applicable from the Download tab — a preset's
      audio intent rides along with its patch, so `mp3 + subs + thumbnails`
      is one pick. Applying one is the same code path as a manual override,
      so there is one thing to get right. Empty states: the Download tab says
      what to do, the Queue explains where downloads live and how to open,
      share or delete them.
- [x] M18 — the bundled toolchain got its missing half and the last tier-1
      gaps closed. **ffprobe** now ships with the app (its own read-only
      build: no muxers, encoders, filters or video decoders — 2.4 MB instead
      of 7.8 MB), and `FfmpegBinaryTest` proves on the emulator that it runs
      *and* that yt-dlp resolves it from the ffmpeg path it is handed.
      Settings gained **retries** and a **playlist limit**, the probe card
      gained one-click **quality picks** (Best…480p, format expressions owned
      by the engine and validated against yt-dlp's own parser), and
      Authentication gained **Test cookies** — which reads the cookies file
      (count, domains, expiry, never a value) and, with a URL, proves it with
      a real extraction instead of guessing.
- [x] **M19 — Android share-target**: share a link from any app straight into
      suravidl. The activity is `singleTask`, so a share raises the running
      window instead of starting a second engine, and the link is handed to
      the UI (`window.suravidlShared`) only once the page is up — prefilled
      and probed, never downloaded behind the user's back.
- [x] **M20 — playlist browsing + per-site memory**: the probe's entries are a
      pick list (checkbox per row, All/None, "*n* of *m* picked", the button
      says how many videos it will start), in step with the range field the
      engine is sent. The quality you pick for a site is remembered and
      offered again as a marked chip — never applied for you.
- [x] **v0.21.1 — the audit release**: the app was probed with hostile input
      instead of being read, and six real bugs came out. A bare
      `POST /files/clear` wiped every download with no server-side confirm
      (the modal existed only in the UI) — the endpoint now refuses with a
      400 unless the body says `{"confirm": "delete"}`. `Infinity`/`NaN` in a
      numeric setting reached `int()` and answered **500**; every numeric
      setting now goes through one clamp that refuses non-finite junk with a
      400 naming the field. `POST /jobs` accepted an empty or blank URL (and
      stored it), and had no ceiling — a job now needs a real URL, trimmed,
      at most 4096 characters. The launcher (`python -m suravidl_engine`)
      silently ignored `SURAVIDL_TOKEN` and used `~/.suravidl/token` instead,
      so the token the README tells you to set did nothing — the env var now
      wins (empty value falls back to the file), which is what the extension,
      scripts and the desktop entry all assume. A headless engine advertised
      a desktop window it did not have: `/app/info` said `desktop: true` and
      `/app/minimize` answered **500**. The window's actions are now dropped
      the moment `webview.start()` fails (there is a browser fallback) and a
      window call that raises answers 501 "not running in the desktop app"
      instead of a server error — capabilities are never announced on the
      strength of an import. And the UI kept its own, stale copy of the
      engine's "the site is asking for a sign-in" heuristic — with a bare
      `age` pattern that matched "webp**age**", so **every 404 came with an
      "add cookies in Settings → Authentication" hint**. The engine owns that
      judgement now (`explain_download_error`), the UI just prints what it is
      told, and one test asserts the UI never carries its own list again. All
      six are pinned by `tests/test_audit_fixes.py` + `tests/test_launcher.py`
      (21 tests), the XSS path was checked against a page whose *title* is an
      `<img onerror=…>` payload (rendered as text, no script — the UI builds
      DOM with `textContent`), and `scripts/smoke.py` still passes end to end.
- [x] **v0.21.1, deeper pass**: a second, design-level review of engine, UI and
      Android found one data-loss bug and a set of races. **Deleting a
      playlist job** used to recurse into its folder (a playlist's `filepath`
      *was* the folder) and take every other job's files with it — jobs now
      persist their own **`files`** list and delete only those. In the UI: a
      failed probe clears its stale quality chips (clicking one used to
      download the *previous* URL); the playlist pick list has an explicit
      **None** (empty used to mean "the whole playlist"), keeps a typed range
      like `1-600`, and Start refuses an empty pick; "this download only"
      overrides are cleared after each start instead of sticking to every
      later job; polling is one-at-a-time, and an unreachable engine says so
      instead of showing an empty queue that reads as "nothing downloaded".
      On Android: the page that inlines the **API token is gated** behind a
      per-install key (loopback is shared — any app could read the token and
      drive the engine), the WebView **checks the responder is really our
      engine** before it loads, the service starts **one engine per process**
      and cleans up its notification, the cookie restore can no longer wedge
      the boot loop, FileProvider no longer exposes the app's private dir
      (cookie session copy, `jobs.db`), backups are off, and a share is
      bounded, consumed once, and logged without the link itself.
- [x] **v0.21.2 — the second opinion**: the app was handed to an
      **independent agent** (Google Antigravity, run headless on a throwaway
      git worktree) and told to find real defects. It reported 16; each one
      was then **reproduced here** against a live engine with an ephemeral
      HOME before anything was believed — an audit is evidence, not truth.
      All 16 held. Data loss and correctness first: **deleting a job could
      remove the download folder itself** (the empty-subfolder cleanup
      compared an unresolved parent with a *resolved* root, so a relative
      `download_dir` never matched), and **changing the download folder made
      every earlier download undeletable** — jobs now remember the folder
      they were created under (schema + `ALTER` migration) and
      `_require_inside()` accepts either root. `POST /files/clear` used to
      run **while a download was live** and unlink its `.part` (yt-dlp then
      died on the final rename): it answers 409 with a count instead.
      A **cancelled download left its `.part`** and a **cancelled playlist
      left every finished entry** — the progress hook now records the target
      the moment yt-dlp names it, and finished playlist entries are appended
      as they land, so the row has something real to delete. A cancel that
      races the finish line used to report **"completed"** and fire the
      completion action; the lock decides now, and cancel wins.
      Engine: the **Firefox build could not reach the engine at all** — CORS
      only allowed `chrome-extension://`, so every call from
      `moz-extension://` died in preflight (`DELETE /presets/{name}` failed
      its preflight too). A **corrupt or hand-edited `settings.json` bricked
      every start** (an uncreatable `download_dir`, `"nan"` for
      `max_concurrent`): loaded values are now validated per key, fall back
      to their defaults, and a `download_dir` must be **provably writable
      before it is saved**. Per-job overrides could **switch raw arguments on
      for themselves** and raw arguments could **write anywhere**
      (`-o/-P/--output/--paths` were not denied) — both closed.
      UI, Android and extension: the per-download Tags block could only say
      "on", so a global embed could not be turned **off for one download**
      (two three-state selects now: use my settings / on / off, and a
      preset's `false` shows as off); a **playlist row asked the gallery to
      delete the folder's name** (matched nothing) and offered
      **Open/Share on a folder** — both work off the recorded `files` list
      now, and the Kotlin hand-off refuses a directory; MediaStore's
      " (N)" matching is **digits only** (the loose match also caught the
      user's own "clip (Official Music Video).mp4"); the desktop entry calls
      **`multiprocessing.freeze_support()`**; `scripts/smoke.py` no longer
      hard-codes `.venv/bin/python`; and the extension captures headers for
      **media requests only** instead of keeping cookies for every page
      request. `tests/test_audit2_fixes.py` pins each one (20 tests).

- [x] **v0.22.0 — what it still needed**: the third Antigravity pass was a
      *product* review instead of a defect hunt ("what does this app still
      need?"). Twelve ranked findings; every claim was checked against the
      code — and reproduced on a live engine where it could be — before a line
      was written (`docs/audits/2026-09-26-antigravity-features.md`).
      Shipped: **subfolders** (`off / playlist / site`, and a
      `filename_template` may finally hold a *relative* folder — it had always
      refused separators, which is why every playlist landed flat);
      **MP4/MKV remuxing** (`video_container`) so a finished download opens in
      QuickTime, iOS Files and Smart TVs, not only in VLC; **clipping**
      (`0:10-0:20` per download, with chapter chips straight from the probe);
      **subtitle-language chips** and `.vtt → .srt` conversion for TVs;
      **batch queueing** (`POST /jobs/batch`, ≤20 links, bad lines named and
      skipped instead of swallowed); **pause/resume** (cancel's cooperative
      stop, but it keeps the `.part` and says `paused`); **archive
      management** (ignore it for one download; list and forget an entry that
      had made a video un-downloadable for ever); **more audio formats**
      (MP3 320/128, FLAC, Opus — 192k MP3 had been the only conversion path);
      an **in-page player** (`GET /jobs/{id}/stream`, Range/206, the same path
      guard the delete path uses); and **edit-and-retry** (a 403 fails the
      same way every time, so a retry may now carry new options — and the UI
      loads the failed row back into the form). Live streams: the probe always
      carried `is_live`; the UI now shows a **● LIVE** badge and
      `live_from_start` records from the beginning when the site still has it.
      Left out on the record: **queue reordering** (the report itself said to
      postpone it — it means replacing the one-thread-per-job model) and a
      custom live-stream *finaliser* (yt-dlp already flushes the container;
      that claim was overstated). `tests/test_features22.py` (36 tests) pins
      all of it.

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
| `GET /files/summary` | ✓ | how much is in the download folder |
| `POST /files/clear` | ✓ | delete every downloaded file — needs `{"confirm": "delete"}` |
| `POST /jobs/{id}/delete` | ✓ | one job: file + sidecars + row (refuses mid-download) |
| `GET /app/info` | ✓ | whether a desktop shell (window) is attached |
| `POST /app/minimize`, `/app/quit` | ✓ | window controls (desktop only) |

## Dev

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests/ -q
SURAVIDL_TOKEN=x .venv/bin/python -m suravidl_engine.api --port 8787
# both entry points honor SURAVIDL_TOKEN; without it a token is generated
# into ~/.suravidl/token (0600) and printed on start
.venv/bin/python scripts/smoke.py   # full live end-to-end check
```

## Limits

DRM-protected streams (Widevine etc.) are out of scope — same as every
downloader of this kind.
