# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two layers, one tool:

- **Enthusiasts first:** the maintainer and people like them — users who want real
  control over a download (formats, playlists, subtitles, batches, cookies,
  presets), on desktop (Windows/Linux/macOS) and on Android.
- **Everyone else, effortlessly:** non-technical users who simply want a video
  saved locally — many of them on Android (APK) or desktop installers. For them
  the paste → download path must stay trivial.

Situation: the user is on their own machine, can already watch the video in a
browser or app, but wants a real local file — one that opens in QuickTime, iOS
Files or a Smart TV, not only in VLC.

## Product Purpose

suravidl downloads web video onto the user's own machine. One engine (Python,
yt-dlp as a library, FastAPI) and one UI core; every platform — desktop apps,
Android app, browser extensions — is a thin shell around them. It downloads
anything yt-dlp understands (1000+ sites) plus raw `.mp4`/`.webm`/`.m3u8`/`.mpd`
links, and never touches DRM.

Success: paste a link → see the site's real formats → pick one → get a normal
local file that plays everywhere. The deep controls (audio conversion,
subtitles, clips, playlists, batch, cookies, presets) are there when wanted and
never in the way of the simple path.

## Positioning

- **One engine + one UI core; every platform is a thin shell.** No per-platform
  forks of the product — desktop, extension and phone all front the same engine
  and UI (README, docs/PLAN-full-ytdlp.md).
- **Fully local, probe-first.** The engine runs on the user's machine
  (`http://127.0.0.1:8787` by default); no web service in the middle, no
  accounts. The UI reveals the site's actual formats before anything downloads —
  choose by fact, not by guess.
- **Never touches DRM**, stated plainly; cookie data is handled defensively
  (encrypted at rest on Android, never written into history or settings) —
  docs/THREAT-MODEL.md.
- **The deliverable is a playable file:** MP4/MKV remuxing so the result opens
  in QuickTime, iOS Files and Smart TVs.

## Operating Context

- Everything runs on the user's machine; downloads, job history (SQLite at
  `~/.suravidl/jobs.db`), settings and cookies stay there.
- Browser extensions are companions to the local engine: they detect videos on
  a page and hand the stream (with the page's own cookies) to the engine — the
  documented route for pages yt-dlp cannot read (docs/SNIFFING.md).
- Signed-in sites: users supply cookies — `cookies.txt` import, reading them
  from a desktop browser, or signing in inside the phone's in-app browser
  (docs/AUTH.md).
- ffmpeg does conversion and merging (bundled for Android; see
  scripts/build_ffmpeg_android.sh).
- Distribution: public GitHub Releases — Windows exe, Linux AppImage, macOS
  dmg, Android APK, Chrome/Firefox extension packages; developed in the open
  under MIT.
- Development entry point: `.venv/bin/python -m suravidl_engine.api` serves the
  UI on `http://127.0.0.1:8787`.

## Capabilities and Constraints

Confirmed features (README): probe-first format picker; playlists/channels with
per-entry picking or ranges; audio-only (keep the native stream, or m4a /
MP3 192–320k / FLAC / Opus); subtitles (files, embedded, or `.srt`); clips
(`0:10-0:20`, chapter fill); batch up to 20 links with bad lines named; pause /
resume that keeps fetched bytes; tidy output (per-playlist or per-site
subfolders, MP4/MKV remuxing); editable retries (a failed job's settings reload
into the form); in-page playback of finished downloads; cookies for signed-in
sites; page sniffing via extension / in-app browser handoff; SponsorBlock;
metadata and thumbnail embedding; speed limits; per-download overrides and
saved presets; auto-resume after a restart; Light/Dark/AMOLED themes; storage
view with a guarded wipe.

Technical constraints: deliberately tiny dependency set (yt-dlp, fastapi,
uvicorn; optional curl_cffi for desktop browser impersonation). Chrome (MV3)
and Firefox extension builds from one codebase. The Android app embeds the
Python engine and hosts the same UI in a WebView. No DRM, ever — a stated
non-goal, not a backlog item. No server component, no accounts, no telemetry.

Terminology: *engine* (the Python downloader API), *shells* (desktop /
extension / Android frontends), *probe* (reveal available formats before
downloading), *handoff / sniffing* (the extension or in-app browser watches a
page and passes the stream plus cookies to the engine), *jobs* (queued and
running downloads).

## Brand Commitments

- Name: **suravidl**; project by LoLyeah ("LoLyeah and suravidl contributors",
  MIT, © 2026).
- Logo asset in-repo (`assets/logo.png`), plus the extension icon family
  (`extension/icons/*`).
- Voice: direct, technical-but-plain, honest about limits — what it does not do
  (DRM) is stated as plainly as what it does. The README and docs set the tone.

## Evidence on Hand

- Public repo `github.com/LoLyeah/suravidl` with a GitHub Releases pipeline;
  README carries release / build / downloads badges.
- Docs set: AUTH.md, SNIFFING.md, THREAT-MODEL.md, PRIVACY.md, AMO submission
  material, and docs/audits/ (external UI and Android audit reports).
- Test suite in tests/ covering UI theming, touch, page layout, Android host
  caps, sniff handoff, and versioned fix batches.
- Firefox add-on submitted to AMO (docs/AMO-SUBMISSION.md).
- Absent — do not fabricate: no company, no team, no user testimonials, no
  benchmarks; the public download counter is the only usage metric.

## Product Principles

1. **Two speeds, one tool** — the paste → download path stays effortless; depth
   (formats, batches, subtitles, cookies, presets) stays one step away, never
   in the way.
2. **One engine, thin shells** — every platform fronts the same engine and UI
   core; platform work must not fork the product.
3. **On your machine, no middleman** — local-first by architecture: no service,
   no accounts, no telemetry; probe first so the user chooses with real facts.
4. **Never DRM; guard what users hand over** — cookies and secrets are treated
   as if the device will eventually be inspected.
5. **The deliverable is a playable file** — output must open on the user's
   actual devices, not just in the tool that made it.
