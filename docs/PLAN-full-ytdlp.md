# Plan — full yt-dlp coverage, cookie safety, and a tabbed UI

Status: proposal · written for v0.10.1 (cookie-hardening release) · project: suravidl
(one engine + one UI core; every platform is a shell)

---

## 0. Ground truth

Measured against the yt-dlp pinned in this repo — extracted **programmatically
from `yt_dlp.options.create_parser()`**, not from docs:

> **361 long options across 16 groups**
> General 35 · Video Selection 28 · Download 28 · Filesystem 40 ·
> Thumbnail 4 · Internet Shortcut 4 · Verbosity/Simulation 33 ·
> Workarounds 12 · Video Format 21 · Subtitle 8 · Authentication 14 ·
> Post-Processing 40 · SponsorBlock 5 · Extractor 6 · Network 8 · Geo 6

So "support every yt-dlp feature" has to be engineered, not hand-waved into a
giant settings page. Three tiers do it.

## 1. Three tiers of coverage

### Tier 1 — first-class UI (~25 options; ≈95% of real use)

| Area | Options exposed | Notes |
|---|---|---|
| Quality | format picker (done), resolution presets, "best video+audio" | per-platform merge caveat below |
| Audio-only | extract MP3/M4A, keep native audio stream | needs ffmpeg to convert; native streams work everywhere |
| Playlists | whole playlist, item ranges, max downloads | engine already supports noplaylist=off path |
| Subtitles | all/auto/languages, embed, separate files | |
| Metadata & art | embed thumbnail, embed metadata, write info.json | |
| Filenames | output template, per-download subfolder | validated template helper |
| Network | rate limit, concurrent fragments, retries, proxy (http/socks) | proxy covers geo |
| Archive | download-archive file, "skip already downloaded" | |
| SponsorBlock | remove / mark categories | |
| Auth | cookies (done), + "test cookies" button | |

Every item: TDD, one settings default + per-job override where it makes sense.

### Tier 2 — **Advanced tab**: the remaining options, without a cluttered main UI

- **Option catalogue endpoint** `GET /options`: the full 361-option list
  generated from yt-dlp's own parser (name, metavar, help, group). Completeness
  *by construction* — nothing to hand-maintain, nothing to forget.
- Curated toggle groups for: verbosity, workarounds, extractor args, geo.
- **Raw arguments field** (global default + per download): the literal
  "every feature" switch. Parsed with yt-dlp's own parser (no shell), echoed
  back in the job details so you always see what ran.

### Tier 3 — deliberately excluded

Simulation/interactive modes (`--stdout`, `--dump-json` without download,
`--config-locations`), our own self-update flows, and anything that fights the
engine's job model. The `--exec` post-processor stays in Advanced **with a
warning** — it's your machine, but it's the one option that runs programs.

## 2. Cookie & local-data safety

### What the audit found in v0.10.0

1. Extension-captured `Cookie` headers were persisted **verbatim** into `jobs.db`.
2. Per-run cookie copies were mode 0644; `~/.suravidl` was 0775 with the engine
   token at 0664.
3. `GET /jobs` returned stored headers (including cookies) to any client holding
   the token.

### Fixed in v0.10.1 — `tests/test_security.py`

- **Cookies are never written to disk.** The live value lives in memory for the
  running job (and in-session retries); anything persisted or served is
  `<redacted>`.
- **Old rows are scrubbed** on engine start (`secure_delete` + `VACUUM` so the
  original bytes are gone from the file, not just the row).
- **Private modes everywhere:** `jobs.db` 0600 · `settings.json` 0600 ·
  `~/.suravidl` 0700 · token 0600 · per-run cookie copies 0600 inside a 0700
  temp dir, deleted after the run.
- A retry of a cookie-authenticated job keeps working while the app is running
  (covered by a test that proves the cookie still reaches the server).

### Planned — M10b

- **Android:** encrypt the imported `cookies.txt` with an AES-GCM key held in
  the Android Keystore; decrypt to a 0600 app-private file only for the duration
  of a run, then delete. (The file never exists readable at rest.)
- **Desktop:** optional keyring-wrapped storage; document that an exported
  cookies.txt is as sensitive as a password.
- **Settings → "Delete stored cookies"** button (one tap wipe).
- Error-string scrubber test: no cookie-shaped tokens in job errors or logs.
- Threat-model doc: what is protected against what (local other-user access,
  cloud backups, other apps on Android, token theft on loopback) — and what is
  explicitly out of scope.

## 3. UI: tabs / menu instead of one long page

Today: single page + one settings modal (it keeps growing). Plan — **four
top-level tabs** in the existing shell, same design language:

- **Download** — paste · probe · formats · presets · per-job options
- **Queue** — the current downloads card
- **Settings** — sub-tabs: **General** · **Authentication** · **Network** · **Advanced**
- **yt-dlp** — searchable option catalogue + raw arguments (hidden until
  enabled in Settings → Advanced; progressive disclosure)

Implementation: hash routing (`#download`, `#queue`, `#settings`, `#ytdlp`),
CSS-driven panels with ~30 lines of JS; **no build step**; **all element IDs
preserved** so the test suite keeps passing. Phones get a bottom segmented bar,
desktop a left rail.

## 4. Milestones

1. **M10a — cookie hardening** ✅ shipped v0.10.1
2. **M10b — encryption & controls** — Android Keystore, delete-cookies, threat model
3. **M11 — tabbed shell** — no feature changes; every test stays green
4. **M12 — Tier-1 options** — in an order you pick (playlists · subtitles ·
   audio-only · metadata embedding · templates · rate limits · proxy · archive ·
   SponsorBlock), each with tests + docs
5. **M13 — Advanced tab** — `/options` catalogue, curated groups, raw arguments
6. **M14 — Android ffmpeg decision** — bundle a community ffmpeg build
   (~+20–25 MB APK) → enables merging + conversion on Android, or keep the
   documented gap (merge is desktop-only today)
7. **M15 — polish** — per-job option overrides, presets, better empty states

Acceptance per milestone: TDD, full suite green, CI on 3 OS + 2 emulators
(incl. the 16 KB Android 16 run), README + release notes updated.

## 5. Drift protection (how this survives yt-dlp updates)

- CI test asserts every yt-dlp option string Tier 1/Tier 2 depends on **still
  exists in the installed parser** — updates that rename or drop options fail
  loudly instead of silently breaking features.
- The catalogue is generated from the parser at runtime, never hand-written.

## 6. Open questions

1. **Tier-1 order** — which first: playlists, subtitles, audio-only extraction,
   SponsorBlock, or proxy?
2. **Raw yt-dlp arguments field** — enable it (default off, Advanced tab)?
3. **Android ffmpeg** — bundle it (+~20–25 MB) or keep "merging is desktop-only"
   as a documented gap?

## 7. Status log

- **v0.10.1 — M10a done:** cookie safety hardening shipped (redaction at rest
  + API, private modes, startup scrub, per-run 0600 copies).
- **v0.11.0 — M11 done:** audio-only presets (keep original / M4A / MP3 192k)
  on the probe card, engine `preset` API, and the Android ffmpeg decision
  (M14) resolved the hard way: a static **ffmpeg 8.1.3** CLI is built from
  unmodified sources by `ffmpeg-android.yml` (arm64-v8a + x86_64, 16 KB
  aligned, LGPL), published on the `ffmpeg-bin` release, bundled into the APK
  as `libffmpeg.so`, exported to the engine via `SURAVIDL_FFMPEG`, and proven
  on-device by instrumentation tests (`FfmpegBinaryTest`, `AudioPresetTest`).
- Decisions applied (user): tier-1 order starts with **audio-only** ✓; the
  raw yt-dlp arguments field will be **default-off in Settings**; Android
  ffmpeg is **bundled** ✓ (latest upstream, 8.1.3).
- **v0.12.0 — M12 (rest of tier-1) done + first slice of M11:**
  `download_opts.py` mirrors yt-dlp's CLI→postprocessor translation in one
  tested place (subtitles embed, metadata, thumbnail, SponsorBlock
  mark/remove, rate limit, fragments, proxy, archive, filename template).
  Playlists: probe reports `playlist/false`+entries (`extract_flat`,
  capped at 100); jobs take `playlist_items` (persisted, surviving retry);
  safety rule — **no playlist_items ⇒ exactly one file**, because yt-dlp's
  `noplaylist` alone does not stop a playlist-only URL. Settings modal got
  sub-tabs (General · Media · Network · Authentication · Device). Progress
  carries `playlist_index/count`; completed playlist jobs report the folder
  plus `playlist_count`; archive skips surface as
  `"already in the archive — skipped"`. Live-verified: template + metadata
  embed on a real remote download (ffprobe shows the written tags), real HLS
  probe (5 formats), real MP4 download. 121 tests + smoke. YouTube itself now
  bot-walls this VPS IP, so YouTube checks run behind cookies (v0.10.0
  feature) — the fixture playlist E2E covers playlist logic offline.
- **v0.13.0 — M13 (Advanced tier) done + the update-link fix:**
  `GET /options` generates the catalogue from yt-dlp's parser (322 options,
  17 groups — complete by construction). Raw arguments: parsed with
  yt-dlp's own parser via shlex, merged as a **minimal diff against an empty
  argv** (merging the parser's full default dump would clobber engine
  choices), with a deny list checked twice — a flag pre-scan (needed:
  `--exec` becomes a postprocessor and never shows up as an option key,
  `--batch-file` reads files at parse time) and a key check for indirect
  effects (`--dump-json` implies `simulate`). Refusals name the flag and
  why. Raw args are snapshotted per job, echoed in the job row, reused on
  retry. UI: Settings → Advanced (switch + field + one-click insert from the
  searchable option browser). Fixed: the update banner could not open a
  browser from pywebview/Android (`target=_blank` is a no-op there) — it is
  a button now that goes host-bridge → desktop `/app/open-url`
  (`webbrowser.open`, `xdg-open`/`open` fallback) → `window.open`.
- Next up: curated option groups (verbosity/workarounds/geo), M10b Keystore
  encryption of imported cookies, and the full four-tab shell
  (Download · Queue · Settings · yt-dlp) — the settings sub-tabs (now
  including Advanced) are its first slices.
