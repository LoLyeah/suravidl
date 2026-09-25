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

## 3. UI: tabs / menu instead of one long page ✅ shipped v0.16.0

**Four top-level tabs** in the existing shell, same design language:

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
3. **M11 — tabbed shell** ✅ shipped v0.16.0 (as the four-tab shell, together
   with the tier-2 curated groups; the settings sub-tabs were its first slice)
4. **M12 — Tier-1 options** — in an order you pick (playlists · subtitles ·
   audio-only · metadata embedding · templates · rate limits · proxy · archive ·
   SponsorBlock), each with tests + docs
5. **M13 — Advanced tab** — `/options` catalogue, curated groups, raw arguments
6. **M14 — Android ffmpeg decision** — bundle a community ffmpeg build
   (~+20–25 MB APK) → enables merging + conversion on Android, or keep the
   documented gap (merge is desktop-only today) — *done in M11a: own 8.1.3
   build, 8.0 MB arm64; ffprobe followed in M18 at +2 MB via a read-only
   configure*
7. **M15 — polish** — per-job option overrides, presets, better empty states
   — *done in M17; M18 closed the tier-1 table (retries, playlist limit,
   quality picks, Test cookies)*

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
- **v0.14.0 — M13 (phone UX + Android storage truth + cookie vault):**
  Settings became a real phone sheet (one scrollable tab row, body scrolls,
  Save pinned), Frosted/Liquid are visually distinct (flat matte vs glossy
  sheen) with hints, the footer no longer advertises an unopenable
  `Android/data` path, finished jobs get **Open/Share** (FileProvider grant —
  a file manager may not browse Android/data, but a grant lets the player
  read it), audio now also imports to `Music/suravidl`, and cookies live in
  a **Keystore vault** (AES-256-GCM, non-exportable key; owner-only session
  copy deleted on quit/delete/start; legacy plaintext migrated + deleted) with
  a delete button and `docs/THREAT-MODEL.md`.
  **Asset caching rule (applies to every embedded shell):** static files must
  be version-stamped (`?v=<engine>`) *and* served `no-store` — a
  `Last-Modified` validator alone lets an Android WebView serve an old
  `style.css` under a fresh `index.html`, which is exactly how a release
  ended up wearing the CSS of two versions earlier. Tested in
  `tests/test_assets.py`.
- **M10b done** (was: Keystore-encrypted imported cookies + one-tap delete +
  threat model) — shipped in v0.14.0 above.
- **v0.15.0 — M14 (format honesty + storage cleanup):** the probe table says
  what each stream contains (video+audio / video only / audio only / single
  file), codecs get human names, duplicate announcements of the same stream
  collapse (keeping the copy with a known size), unadvertised sizes read
  "unknown" instead of "?", and picking a video-only stream auto-pairs it
  with the site's audio (`<id>+bestaudio/best`) so quality picks can't yield
  silent files. New `GET /files/summary` + `POST /files/clear` back a
  Settings → Device "Delete downloaded files" row (app folder + the
  Gallery/Music copies we contributed, completed jobs pruned) — needed
  because Android/data is not user-browsable.
  - **v0.16.0 — M15 (four-tab shell + curated groups):** the shell from §3 is
    real: `#download · #queue · #settings · #ytdlp`, hash-routed, remembered in
    localStorage, left rail on desktop and a bottom segmented bar on phones
    (Queue carries the active-downloads badge). Settings and the option
    catalogue left their modals and became tabs — every element id that the
    engine tests and the E2E flows rely on is unchanged; only the two modal
    shells (`settingsModal`, `optionsModal`) are gone. The curated groups from
    tier 2 (§1) are named settings now — `verbose`, `ip_version`
    (auto/ipv4/ipv6 → `source_address`, yt-dlp's own mapping), `no_check_certificates`,
    `sleep_requests` (0–30 s → `sleep_interval_requests`), `geo_bypass` +
    `geo_bypass_country`, `extractor_args` (`extractor:key=value,…`, parsed
    locally, never through a shell) — validated in `settings.py`, mapped in
    `download_opts.curated_settings_opts()`, and proven against yt-dlp's own CLI
    translation in `tests/test_curated.py`. The network ones also reach the
    probe (`probe(extra_opts=…)`, engine-owned keys dropped) so a
    region-locked video can at least be listed; live proof in the engine log:
    `Using fake IP … (ID) as X-Forwarded-For`. Raw arguments stay default-OFF
    and the editor only appears once enabled in Settings → Advanced.
  - **Format honesty note (v0.15.0):** never infer a stream's tracks from
    missing fields — a direct link reports `vcodec: null, acodec: null`, which
    is "unknown", not "audio only"; pair with `bestaudio` only when the site
    publishes a separate audio-only format.
  - **v0.17.0 — M16 (per-download delete + the phone blob):** the trash button
    the user asked for: `POST /jobs/{id}/delete` removes one download's files
    (main file + same-stem sidecars), its row, and on Android the MediaStore
    copy this app contributed (`MediaLibrary.deleteOwnCopiesNamed`, matched by
    display name) — refusing while the job still runs and refusing any path
    outside the download folder. The UI asks first (`askConfirm`, file name in
    the message, "Stop and delete" for a running job via `settleThenDelete`)
    and reports `deleted`/`freed_bytes`. The blue capsule that covered the
    Authentication fields was a **CSS class collision**: `class="col fill"` (a
    settings layout helper) also matched the bare `.fill` progress-bar rule, so
    a 339×114 gradient was painted over the panel — progress-bar styles are now
    scoped `.bar .fill` and `tests/test_ui.py` pins that scoping. Android
    additionally drops the glass illusion (`--glass-bg` → solid where
    `backdrop-filter` can't be trusted).
  - **v0.18.0 — M17 (per-download overrides + presets + empty states):** a job
    may now carry `overrides` — a validated patch over the saved settings
    (`settings.validate_overrides`, whitelist of per-job keys, the app-level
    ones refused) — persisted with the job so retries repeat it, merged in the
    engine's `_download_opts` callable. `presets.json` (0600) holds user
    presets: a name plus a validated patch that may also carry the audio
    intent, applied through the very same override path
    (`POST /jobs {"preset": "my-bundle"}` expands it). UI: a collapsed "This
    download only" block on the Download tab, a Presets sub-tab under
    Settings (save the options that differ from the defaults), `⚙ N options`
    chips on the rows, and honest empty states for Download and Queue.
    Verified live: an applied preset named the file (`ui-ov.mp4`), embedded
    metadata (ffprobe tags) and wrote the subtitle sidecar, while `/settings`
    stayed untouched.
  - **v0.19.0 — M18 (ffprobe + the last tier-1 gaps):** ffprobe is bundled for
    Android from its own read-only build (demuxers + parsers only; 2.4 MB
    against ffmpeg's 10.7 MB on x86_64) and `.github/actions/fetch-ffmpeg`
    places `libffprobe.so` beside `libffmpeg.so`, which is exactly where
    yt-dlp looks (`_determine_executables` substitutes the program name in
    the given path). Engine: `retries` (0-30) and `max_downloads` (0-1000)
    settings + per-job keys; `QUALITY_PRESETS` (engine-owned format
    expressions, each asserted against `yt_dlp.parse_options`) served via
    `/presets`; `POST /auth/check` (settings + a URL → static cookie report
    plus a real extraction as proof, values never leave the engine).
    UI: quality picks under the probe box, Retries/Playlist-limit fields,
    Test-cookies button with an inline verdict.
  - **v0.20.0 — M19 (Android share-target):** "Share → suravidl" from any app
    that shares a link (YouTube, Chrome, a browser). The activity is
    `singleTask`: a share raises the existing window — no second engine, no
    second WebView — and a share that arrives before the UI is up waits for
    `onPageFinished` instead of being dropped. The link is extracted from
    whatever the share sheet sends (`Title — https://…`, a bare `youtu.be/x`,
    punctuation trimmed; an address or a `clip.mp4` is not a link) and handed
    to the UI by `window.suravidlShared(url)`, which switches to Download,
    prefills the box, probes and says so — the format stays the user's choice,
    exactly like a paste. Delivery writes one line to `share.log` so a share
    that "did nothing" is diagnosable from the phone.
  - **v0.21.0 — M20 (playlist browsing + per-site memory):** a playlist probe
    already listed its entries; they are now a **pick list**. Every entry row
    carries a checkbox (`index` is the playlist number the engine probes with,
    up to 500 entries), All/None buttons and a live "*n* of *m* picked" label,
    and the Download button names what it will do ("Download 3 picked"). The
    range field stays the single thing sent to the engine (blank = all) and
    the two halves are kept in step both ways: boxes → field, and a typed
    range ticks the matching boxes back. Second half: the engine remembers the
    **quality you pick per site** (`settings.site_quality`, host → quality
    key, bounded to 50 sites, cleaned on the way in, refused as a per-job
    override) and `/probe` returns it as `site_quality` — an *offer*: the chip
    is marked ("720p ✓, your pick for this site last time") and still needs
    the click, and an arbitrary typed format teaches the engine nothing.
  - **v0.21.1 — the audit release (no new features):** a hostile-input pass
    over the *running* engine and the UI, not a read-through. Six bugs, each
    fixed and pinned by a test: `POST /files/clear` wiped every download on a
    bare POST (the confirm existed only in the UI) — a server-side
    `{"confirm": "delete"}` is now required (400 otherwise); `Infinity`/`NaN`
    in a numeric setting reached `int()` and answered **500** — one clamp
    (`settings.int_in`) refuses them with a 400 that names the field;
    `POST /jobs` accepted a blank URL and had no ceiling — trimmed,
    non-empty, ≤4096 chars; the launcher (`python -m suravidl_engine`)
    ignored `SURAVIDL_TOKEN` and quietly used `~/.suravidl/token`, making the
    README's dev command a lie — the env var now wins; a headless engine
    advertised a desktop window (`/app/info` said `desktop: true`,
    `/app/minimize` → 500) — the actions dict is emptied the moment
    `webview.start()` fails and a failing window call answers 501; and the UI
    carried its own copy of the engine's sign-in-wall heuristic, with a bare
    `age` pattern that matched "webp**age**" — so every 404 came with a bogus
    "add cookies in Settings → Authentication" hint. `auth.WALL_PHRASES` +
    `auth.explain_download_error` are now the single source (used by probe
    errors *and* job errors), the UI prints what it is told, and a test
    asserts the UI never grows its own list again. 242 tests;
    `scripts/smoke.py` green; the XSS path verified against a page whose title
    is an `<img onerror=…>` payload (rendered as text — the UI builds DOM with
    `textContent`).
  - **v0.21.1, second half — the deeper pass** (design review of the *whole*
    codebase, engine + UI + Android, after the hostile-input one): two
    sub-audits reported 32 findings; the real ones are fixed here.
    Engine: a **playlist job's `filepath` was its download folder**, so
    deleting that one row recursed into the folder and took every other job's
    files with it — jobs now persist their own **`files`** list (schema +
    ALTER migration) and `delete_job` deletes only those, through
    `_require_inside()`; legacy rows delete nothing and say so.
    UI (~15 findings): a probe no longer paints stale quality chips
    (`PROBE_SEQ`) and a failed probe now clears them (clicking one used to
    download the *previous* URL); the playlist pick list got an explicit
    **None** state (empty used to mean "the whole playlist"), keeps a typed
    range like `1-600` (it was silently narrowed to 1-500) and disables Start
    when nothing is picked; per-job overrides are **cleared after each start**
    (they stuck to every later job) and an emptied preset field now *deletes*
    the value instead of leaving it in force; polling is one-at-a-time with a
    sequence stamp, and three failures say **"cannot reach the engine"**
    instead of rendering an empty queue (which reads as "nothing downloaded");
    a `/presets` failure is a load error with retry, not "No presets yet";
    Escape only closes Settings when Settings is open; unsaved Settings survive
    a tab switch (`SETTINGS_DIRTY`); the bulk-wipe confirm no longer claims
    "0 files (0 B)" when the size is unreadable; `__CFG__` escapes `<`/`&`
    (a `download_dir` containing `</script>` could break out).
    Android (the shell, from the same reports): the engine page that inlines
    the **API token is now gated** behind a per-install key (`GET /?k=…`) —
    loopback is shared, so any other app could read the token and drive the
    engine; the WebView **verifies the responder** is our engine before it
    loads (a squatter on 8787 would otherwise get the JS bridge); the service
    starts **one engine per process** (a re-delivered `onStartCommand` booted
    a second one), takes its notification down when it stops, and survives an
    FGS start failure without leaving an un-swipeable "downloading…"; the
    cookie-restore call moved **out of the boot loop** (a damaged vault threw
    there and reloaded the UI ~120 times, then claimed the engine never
    started), an unreadable vault blob is dropped with a message instead of
    failing every start; FileProvider's **`<files-path>` is gone** (it exposed
    the plaintext cookie copy and `jobs.db` to any page with the bridge), and
    backups/device-transfer are off; the share text is **bounded to 4 KB** (a
    1 MB share ANR'd the launch path), a share is consumed **once** (the
    framework replays the intent on every recreation), the shared link is
    logged **host-only** in the world-readable log, the WebView refuses to
    navigate off the engine, imported gallery ids are **persisted** (every
    restart used to re-import every past download), playlist jobs import every
    file they made, `videoMime()` stops stamping `video/mp4` on webm/mkv, a
    failed MediaStore publish no longer leaves a hidden half-row, and MediaStore's
    " (1)" renames are matched when deleting. 256 Python tests + 2 new
    instrumentation tests.
  - **v0.21.2 — the second opinion**: an *independent* audit (Google
    Antigravity via `agy`, headless, on a throwaway git worktree, read-only
    prompt) reported **16 findings** in `AUDIT-AGY.md`; every claim was then
    reproduced here against a live engine with an ephemeral HOME before it
    was believed. All 16 held — one with an overstated blast radius. Data
    loss: deleting a job could `rmdir` the **download folder itself** (the
    cleanup compared an unresolved parent with a resolved root, so a
    relative `download_dir` never matched); **changing the download folder
    made every earlier download undeletable** (409) — jobs now record their
    own `download_dir` (schema + ALTER) and `_require_inside()` accepts
    either root; `POST /files/clear` ran **while a download was live** and
    unlinked its `.part`, killing the download on the final rename (409 +
    count now); a **cancelled download left its `.part`**, a **cancelled
    playlist left every finished entry** (the progress hook now records the
    target as soon as yt-dlp names it, and finished entries are appended to
    `files`); a **cancel racing the finish line reported "completed"** and
    fired the completion action (the lock decides; cancel wins). Engine: the
    **Firefox build could not reach the engine** — CORS accepted only
    `chrome-extension://` (and not `DELETE`, so presets failed preflight
    too); a **corrupt `settings.json` bricked every start** (uncreatable
    `download_dir`, `"nan"` for `max_concurrent`) — loaded values are
    validated per key now and `download_dir` must be provably writable
    before it is saved; per-job overrides could **enable raw arguments**
    (the *switch* is denied per job now — the first cut of this release
    denied `raw_args` too and would have quietened the per-download
    arguments field, so the tag was re-cut with that corrected) and raw
    arguments could **redirect output** (`-o/-P/--output/--paths`).
    UI/Android/extension: Tags could only say "on", so a global embed could
    not be turned **off for one download** (three-state selects, preset
    `false` shows as off); a playlist row asked the gallery to delete the
    **folder's name** and offered Open/Share on a **folder** (both now use
    the recorded `files`, Kotlin refuses a directory); MediaStore matching
    is **digits only** (the loose match also caught the user's own
    "clip (Official Music Video).mp4" — owner-scoped, so it could only have
    hit our own copies: fixed defensively); desktop entry calls
    **`freeze_support()`**; `smoke.py` stops hard-coding `.venv/bin/python`;
    the extension captures **media requests only**. 276 tests.
  - **v0.22.0 — the feature review**: this pass was a *product* review, not a
    defect hunt. Antigravity was asked what the app still needs; its twelve
    ranked findings were each checked against the code (and reproduced where
    possible) before anything was built. Shipped: **subfolders**
    (`off/playlist/site`, and `filename_template` may now hold a *relative*
    folder — separators had always been refused, which is exactly why every
    playlist landed flat), **MP4/MKV remuxing** (`video_container`),
    **clipping** (`download_sections` + chapter chips), **subtitle chips and
    `.vtt → .srt`**, **`POST /jobs/batch`** (≤20, per-link skips),
    **pause/resume** (`paused` keeps the `.part`; resume continues from the
    byte offset), **archive inspect/forget + `archive_ignore`**, **MP3
    320/128 + FLAC + Opus presets**, **`GET /jobs/{id}/stream`** with Range
    (and an in-page player), and **edit-and-retry** (`POST /jobs/{id}/retry`
    takes `{fmt, preset, overrides, raw_args}`; the UI reloads the failed row
    into the form). Live: `● LIVE` badge from the probe + `live_from_start`.
    Deferred on purpose (both on the record): queue reordering — the report
    itself said postpone it, and it means replacing the one-thread-per-job
    model — and a custom live finaliser (yt-dlp already flushes the
    container). `tests/test_features22.py` (36 tests, written RED first).
  - Next up: M21 — (open) subtitles language picker per site (half-shipped in
    v0.22.0 as probe chips + srt), scheduled downloads (cron-style watch list).
  - **v0.22.1 — the UI/Android review** (fourth Antigravity pass, this time
    scoped to the UI and the Android section plus the install floor): 12
    findings, 11 confirmed and fixed, one applied as hardening (the
    ACTION_SEND clipData claim is not reproducible — the platform migrates
    EXTRA_STREAM — but stating the grant explicitly costs nothing).
    Headlines: the confirmed-fatal unguarded `NotificationChannel` (Android
    7.0/7.1, the declared floor, died before Python started); the
    gallery-import retry loop (`existing` counts files, so on API<29 the
    settle condition was unreachable — a 2-second re-check forever plus log
    spam); and the one reproduction worth framing — the Android build's
    starlette 0.27 ignores `Range`, so the in-app player could not seek on a
    phone while the desktop venv (starlette 1.7) passed the test. Range now
    lives in `api.py` (206/416/suffix/open-ended) with a test that fails if
    the file is handed back to `FileResponse`. Also: pending-share survives
    config changes, the inert "whole video" button, the duplicate Retry, the
    stuck outage banner, bare-host batch links + a visible 20 cap, toasts
    above the mobile tab bar, `readAll` reading both log dirs, aria-labels /
    `role="dialog"` / 44px touch targets, and the same empty-pick-means-all
    trap on the manual playlist path that v0.21.2 closed for the None button.
    Floor: `minSdk 24` kept — it IS Chaquopy's floor — with the crash guarded,
    a WebView-age check (Chrome 80) that explains itself instead of painting a
    blank page, and README notes for what needs Android 10+ (gallery copy,
    file-manager log). Verdict table:
    `docs/audits/2026-09-26-antigravity-ui-android.md`.

- **v0.23.0 — the UI/UX + motion review** (fifth Antigravity pass: how the app
    *feels* — animation, transition, feedback). 21 findings: 17 fixed, 2
    already fixed in this same sitting before the report landed, 2 rejected on
    evidence (one by direct measurement). The pass came with a method rather
    than an opinion: a throttled fixture server so a download stays in every
    state long enough to watch, and live probes — `getAnimations()` filtered to
    `playState === 'running'`, computed styles, and `getBoundingClientRect()`
    sampled every 100 ms across poll boundaries.
    Headlines. **The progress bar was animating for 220ms of every 1200ms poll
    and then sitting dead** — a stalled-looking download; there is now a
    `--t-poll` token that glides across the whole window, and a test pins it to
    `setInterval(refreshJobs, …)` so the two numbers can never drift apart
    (measured after: 15 sampled frames where the bar moved while the poll value
    was static). **A start no longer invites a second tap**: the trigger button
    goes disabled + `.busy` for the round-trip, and every trigger passes itself
    in — a double-tap used to queue the same video twice. **Deleting says
    deleting**: the row dims and its pill reads "stopping…/deleting…" through
    `settleThenDelete`'s up-to-3s loop, and the mark is undone if it fails.
    **Queued and merging are no longer silent** — every active status renders a
    bar, with a muted indeterminate track for the states that know no
    percentage, and `metaParts` stopped printing "0% · 0 B / 0 B" beside it.
    Motion hygiene: `.swap` is opacity-only now (it dropped the row 6px on
    every status change), the dialog exit lands on opacity 0 inside
    `closeModal()`'s 170ms timer instead of being cut at .5, the player closes
    through the same path as every other dialog, Android freezes the aurora
    (`animation: none` + a 34px blur — three radial gradients under 70px of
    blur, re-rastered every frame, is battery spent on decoration), and the
    theme switch cross-fades through a scoped `html.theming` class for the
    ~400ms it lasts instead of easing four selectors while the controls inside
    them snap. UX: a dirty dot on the Settings tab, the override chip names its
    own keys, the option catalogue got a keyboard (roving tabindex — one tab
    stop, arrows/Home/End, Enter/Space; the review's snippet would have added
    322 of them), the playlist range reacts as you type, the sticky save bar no
    longer hides the field you are typing into on a phone, and the Settings ✕
    is desktop-hidden so a tab stops looking like a dialog. Rejected: "card
    rise replays on every tab switch" (measured false — Chrome does not restart
    a finished animation on `display` flips) and "animate the toast stack" (it
    would mean animating layout on each dismissal, which this stylesheet
    deliberately avoids everywhere else). 17 new regressions in
    `tests/test_web_motion.py`; suite **346 passed**.
    Verdict table: `docs/audits/2026-09-26-antigravity-motion.md`.
