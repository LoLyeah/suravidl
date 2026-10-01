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

- **v0.23.1 — the glass that did nothing, fixed properly.** A bug
    report with a screenshot: on the phone, switching Frosted/Liquid changed
    nothing. True — the Android host block turned off the blur, the gloss AND
    the highlight in one blanket rule, so both styles resolved to the same
    solid panel; the only difference left was one 1px inset alpha. Android
    cannot blur, so the styles are now carried by what is left: frosted stays
    flat and matte, liquid keeps its gloss — an accent-tinted sheen, a brighter
    top highlight and a tinted border (`--glass-border`), all of it pure paint
    with no backdrop-filter to pay for. The same token sharpens the desktop
    difference (16px vs 30px blur on top of it).
    The screenshot held two more real defects, both reproduced before being
    touched: the mobile toast lane was missing its `env(safe-area-inset-bottom)`
    term (a gesture bar reserves 30-50px below the tab bar, so the stack sat
    that much lower and clipped behind it), and on the Settings tab the toasts
    landed on the pinned Save bar — the button's gradient showed through the
    10px gap between two toasts, which reads as a broken screen on exactly the
    screen where everyone taps a theme or glass swatch. `body[data-tab]` (set
    by `showTab`) now gives the stack its own band above that bar.
    No test had ever covered the appearance settings: `tests/test_web_theming.py`
    asserts the difference rather than the wording — every glass style must
    change a visible property on every host, the glass surfaces must consume
    the tokens, all three themes must define the same core palette, and the
    mobile toast lane must clear both bars. Suite: **353 passed**.

- **v0.23.2 — the storage row stops lying, and Android gets its blur back.**
    Two follow-ups from the same report. (1) "Downloaded files: 2 files ·
    73.2 MB" sat above a confirm reading "Delete 0 files (0 B)": both read
    `/files/summary`, but the row was fetched once at boot and never again, so
    a delete done from another tab (or a download finishing) left it stale.
    It re-reads whenever Settings comes into view and after a per-job delete,
    and with nothing on disk the button says "nothing to delete" instead of
    opening a destructive dialog at all. (2) A correction. The Android host
    block claimed backdrop-filter was unreliable there and wrote that down as
    `--glass-blur: none` plus opaque panels. The WebView is Chromium and the
    app already refuses anything below Chrome 80, so the filter is there: the
    original note was a *cost* decision (a big card blurred over the animated
    aurora re-rasterized on every scroll frame) promoted to a capability limit,
    and it made the glass setting a no-op on the platform most people use.
    Android now blurs for real with a lighter radius than desktop (11px
    frosted / 19px liquid), keeps the frozen aurora as the actual perf lever,
    and still falls back to solid panels through the `@supports` block.
    Suite: **355 passed**.

- **v0.23.3 — the update notice grows up.** It used to be a one-line button
    appended to the header: on a phone it was a squeezed strip between the
    title and the edge (reported with a screenshot), it could not say which
    version was newer, and it had no way to be dismissed. It is now two
    surfaces fed by one check: **one persistent toast** (it does not time out)
    carrying the actual choices — Get <version> · Later · Skip this version —
    and a **Settings → General → Updates** row that can be looked at any time
    ("up to date ✓", or "0.23.4 is available / skipped", with Check now).
    Skip and snooze are per-device (`localStorage`; Android's UI origin is the
    fixed 127.0.0.1:8787, so they survive restarts), "Later" means 24 hours,
    and Check now deliberately overrides both. Nothing installs itself: "Get
    it" opens the release page, because no build of this app can replace
    itself in place. `toast()` gained an options argument (sticky + action
    buttons) whose buttons stop their click from bubbling into a dismiss.
    Verified live against a stubbed newer release: notice persists past the
    4.2s timeout, Skip silences it across reloads, Check now brings it back,
    Get reaches the exact release URL, Later stores ~24h and stays quiet.
    Suite: **362 passed**.

- **v0.23.4 — Settings is a page, and the header stops repeating the tabs.**
    Reported with phone screenshots, four things at once. The settings card was
    already `border-radius: 20px` and glass, but two opaque plates sat on it: a
    sticky `modal-head` carrying a ✕ and the sticky Save bar, both
    `--panel-solid` (97% opaque) and both spanning the card's full width — which
    squared off its top and bottom corners and read as "a popup that isn't a
    popup". The ✕ and the dialog header are gone (the tab bar is the way out;
    Escape still closes), the title scrolls with the content like every other
    card's, and the Save bar keeps the card's glass (`--glass-bg-strong`) with a
    matching bottom radius and no backdrop-filter (a sticky blur smears its
    backdrop in Android's WebView). The header had a "⚙ Settings" button
    directly above a Settings tab — one entry point now — and "Update yt-dlp"
    moved into the yt-dlp tab, which shows the installed version beside it and
    refreshes the label after an update. Suite: **366 passed**.

- **v0.23.5 — the phone stops behaving like a web page.**
    "When clicking any button on android, there's always ugly blue square
    opacity, and I can copy every text." Both were WebView defaults we had
    never overridden. The flash is the WebView's own highlight plate
    (`-webkit-tap-highlight-color`): it ignores border-radius and our colours
    and lands on whatever is tapped — now transparent, with the app's own
    `:active` press states (extended to tabs, sub-tabs and option rows) doing
    the feedback instead. Selection: `user-select: none` on the chrome and
    `text` on inputs/textareas/selects, with a `.selectable` hook plus `.msg`
    (an error line is worth copying). `touch-action: manipulation` on controls
    so the first tap is never spent as a double-tap-zoom probe. And the
    "always" part: `:hover` styles latch on a touch screen, leaving a faint
    blue tint stuck on the last-tapped button — all ten hover rules now live
    inside `@media (hover: hover)`, so they exist only where a real pointer
    does. Suite: **370 passed**.

- **v0.24.0 — M1 of the capture plan: the engine gets a brain.**
    `POST /classify` names a URL before any shell shows it: kind (video / hls /
    dash / drm / audio / image / page / unknown), mime, size, and the final URL
    after redirects. HEAD first, then a bounded 4 KB ranged GET when HEAD is
    refused — the size comes from `Content-Range`, never from the peek. The DRM
    line is drawn where it belongs: an ordinary `METHOD=AES-128` HLS is *not*
    DRM (yt-dlp fetches the key with our cookies), while `SAMPLE-AES`, `skd://`
    and DASH `<ContentProtection>` are — those answer `drm`.
    `GET /sniff/patterns` becomes the one media-pattern list every shell
    prefilters with (the extension's hard-coded copy stays a subset, enforced
    by a test, until M4 moves it). `POST /probe` now answers a site yt-dlp
    cannot extract with a *structured* error — `{message, hint,
    unsupported: true}` — instead of a bare string, and the UI keeps that
    detail on the Error while showing the human message.
    Live-verified: mp4 → `video` (size 2 848 208), the mux HLS demo → `hls`, a
    SAMPLE-AES manifest → `drm`, an AES-128 one → `hls`, w3schools and the
    tested JS-only player → `page`, and a real probe of that player returns the
    browser hint in the UI. The live pass also caught a real defect: the
    classifier's default User-Agent was urllib's "Python-urllib/…", which is
    bot-blocked on sight — pages answered 403 until it asked like a browser.
    Suite: **395 passed**.

- **v0.24.1 — M2 of the capture plan: the phone gets a browser.**
    `BrowserActivity` + `SnifferWebViewClient` capture what a page asks for in
    four layers — network requests in every frame, element loads, JS hooks
    (fetch/XHR, a media element's own src, `createObjectURL`, `addSourceBuffer`)
    and a `performance`-timeline sweep. The hooks also ride into *same-origin*
    child frames, and every find carries the frame it came from, because a
    signed media URL's referer is usually the player iframe and not the address
    bar. Candidates land in one thread-safe log — layer 1 runs on a handler
    thread — with a strongest-signal-wins rule, so a blob-fed player outranks
    the request that happened to fetch it first. The Download tab grows a
    host-gated "Find a video on a page" button: Android has no extensions, so
    here the browser *is* the extension. **No new dependency, no new
    permission** — the system WebView is the browser — and the measured cost is
    **+20 KB** on the debug APK. Handing a candidate to the engine (cookies,
    referer, User-Agent) is M3: this milestone finds and copies, and says so.
    The instrumented test earned its keep before the release: it caught a
    WebView method read off the main thread, and a frame guard that latched on
    the `about:blank` document a frame starts life with — leaving a child
    frame's *real* document unhooked. Fixing the second one came with an
    insight worth keeping: a `blob:` source on a media element *is* a
    JavaScript-fed stream, so a player stays visible even when the hooks that
    would have watched it being built arrived late. Verified: android
    instrumentation ✅ on API 30 **and** the 16 KB-page API 36 emulator (a
    loopback fixture server, a real WebView, real HTTP — nothing but the
    emulator needed), CI ✅, suite **395 passed**.

- **v0.24.2 — M3 of the capture plan: the handoff.**
    A find is no longer a dead end. Every row carries the engine's own verdict —
    kind, size, DRM, from `POST /classify`, sent with the headers a guarded URL
    needs even to be *looked at* — and a Download button that posts to `/jobs`
    exactly the way the desktop extension always has: this WebView's cookie jar,
    its own User-Agent, and the **frame** the URL came from as the referer (a
    signed media URL's referer is the player iframe, not the address bar). All
    three keys sit inside `jobs.py`'s allow-list, so nothing is dropped silently
    and a failure never masquerades as "this site needs a login". Markers are not
    downloads: a `blob:`/`mse:` row says what it is, a DRM row says it cannot be
    fetched and offers nothing, and "Clear browsing data" arrives with a confirm
    that names what it does *not* touch — downloads and the imported cookie file.
    In the app, an "unsupported URL" probe answer finally offers "Open in the
    browser ↗" (host-gated, hidden again as soon as a probe works): the consumer
    the M1 structured error was built for.
    Verified end to end **on a device**: the instrumented test's fixture is
    *guarded* — `/guarded.mp4` answers 403 unless the request carries the
    browser's cookie *and* a referer from the page that embedded it — so a green
    run is proof that the captured headers genuinely reached yt-dlp. Suite:
    **402 passed**.

- **v0.24.3 — M4 of the capture plan: desktop parity + docs.**
    The last milestone of the arc, and mostly about *one place* to decide things.
    The extension no longer hard-codes the media-pattern list: it fetches
    `GET /sniff/patterns` (once a day, cached; a subset-checked fallback stands
    when the engine is not answering), and a response that *says* `video/*` is
    now a find even when its URL looks like nothing — which is the whole reason
    to sniff rather than guess. Both shells ask the engine the new
    `POST /sniff/rank` question — *which of these is worth showing?* — so a
    playlist hides its own fragments on the desktop and on the phone for the same
    reason, and both *count* what they hid ("3 fragments belong to a playlist
    above") instead of making rows disappear. Same rule in one test file, two
    shells.
    The docs half is the honest half: the README gains a capture matrix (what
    each platform can get, row by row, including the cells that say "—"), and
    `docs/SNIFFING.md` states what is promised, what is *deliberately* not
    (DRM, ad gates, anti-bot, cross-origin `blob:` on Android, segment-only MSE,
    live HLS, sniffed subtitles), how the Firefox-for-Android stopgap works, and
    the device-only manual checklist. Settings → Network also grew the API-token
    row (masked, with Copy): the extension needs that token, and a phone cannot
    read `~/.suravidl/token` — which is exactly the gap the row closes.
    Suite: **417 passed**; the extension is at its own version 0.5.0.

- **v0.24.4 — the extension harness, and the race it caught on its first run.**
    M4 shipped with the extension's new logic asserted *statically* (string
    checks in pytest), which is thin for the one shell no emulator can host. So
    `extension/test_harness.mjs` loads the real `background.js` into Node with
    just enough `chrome` to be honest — storage, three webRequest listeners, a
    badge — fires it with realistic requests, and asserts what gets remembered,
    what gets captured, and what the engine is asked. `tests/test_extension_runtime.py`
    runs it, and it is part of the suite.
    Its first run found a real bug: `remember()` and `captureHeaders()` were
    read-modify-write against `chrome.storage.local`, and a player that asks for
    its manifest and its first fragments *in the same tick* lost finds — the last
    writer won. Writes are now chained (`update()`), the badge follows every
    find, and the harness keeps three same-tick finds as a regression test.
    Verified: extension runtime checks ✅, suite **418 passed**, CI ✅.
    Extension: 0.5.1.

- **v0.24.5 — an independent audit, confirmed finding by finding.** The whole
    capture arc (engine `/classify` + `/sniff/rank`, the extension, the Android
    in-app browser, their tests) was handed to Google Antigravity, read-only,
    which returned 15 findings in 20 KB. Nothing was taken on trust: each was
    reproduced against the real code path before anything changed, two were
    **downgraded with reasons** (the "hostile page evals JS" finding reaches no
    privilege the page didn't already have; the "/classify SSRF" has no
    exfiltration path — the verdict renders in the local app), and loopback +
    RFC1918 reachability was kept on purpose (the engine *is* on loopback, and a
    NAS is a legitimate source).
    What was real, and is fixed: the **infinite `/classify` retry loop** (a null
    verdict was never remembered, so `render()` re-queued the URL forever — the
    worst find of the batch); **the MV3 pattern cache** (only the timestamp was
    persisted, so after every worker restart the engine's list was silently the
    baked-in fallback — owned, and mutation-verified); **extension-less media
    found by its response** now carries the headers that were held for it;
    `tabs.onRemoved` joined the write chain; `SniffLog` became thread-safe with
    an on-device test that hammers it from eight threads; `rank()` stopped
    treating a query string as a playlist name and now attributes a fragment to
    the manifest it actually lives beside; "Clear browsing data" clears the find
    list too, and says so in the confirm; FairPlay is detected whatever the
    `METHOD`; the popup WebView is destroyed; the injected hooks are non-writable
    so no page can swap them; `/classify` refuses link-local and cloud-metadata
    targets; the token comparison is constant-time; the README badge is current
    and its API table lists the new endpoints.
    The tests half matters most: a decoration found here by mutation (deleting
    the `offerBrowser()` call still passed) is now an assertion that the wiring
    is *reached*, and an **on-device** test proves a live row carries its
    Download button — not merely that the code says so. The tap itself is still
    not end-to-end, and says so.
    Suite: **426 passed** (was 418); extension runtime checks ✅; records in
    `docs/audits/2026-09-26-antigravity-sniffing.md`. Extension: 0.5.2.

- **v0.24.6 — the site that beat the prefilter, and the link that went nowhere.**
    A live report (a link that would not download) turned out to be two
    bugs, and neither was the one the plan expected.
    **1. The prefilter was deciding for the player.** The site's stream is
    `https://mp4-06.overfetch.video/1Vvp1Q5ixT-GxZcW4IToe` — no media extension,
    another host, inside a same-origin player frame. No pattern list can
    recognise that shape, so every layer dropped it: the player's own `<video>`
    pointed straight at the video and the app could not see it. The rule was
    right for *network noise* and wrong here, so `rep()` grew a `direct` flag —
    a media element's own source (the DOM sweep and the `src` setter) is
    evidence, not a guess, reported as it is and classified by the engine before
    a row is drawn. `/classify` on that URL answers `video · 16 MB`, and yt-dlp
    takes it with the frame's referer, which the handoff already sends.
    **2. `singleTask`, and a second launch that was a no-op.** A second "Open in
    the browser ↗" never reached the activity at all: on API 30 an identical
    singleTask launch is discarded — `Intent.filterEquals` ignores extras, so
    the two launches *were* "the same", while the same code delivered
    `onNewIntent` on API 36 — and the user kept scanning the *previous* page
    while believing they were on the new one, which is exactly what "it still
    won't download" looks like from the outside. The instrumented test's
    failure message is what cracked it: the activity was `RESUMED` on the *old*
    URL. Fixed at both ends — `onNewIntent` reads the extra, starts a fresh
    find list and loads the link, and the launch site adds
    `CLEAR_TOP | SINGLE_TOP`, the system's documented way to hand a new Intent
    to the running instance. (The screen also has to be awake for any of this:
    a stopped activity is handed a new intent only when it resumes, which is
    why the same test passed on one emulator and failed on another.)
    Both are pinned by instrumented tests that failed in CI before the fix: an
    extension-less player source must be found as a `player` find with its frame
    recorded, and a second link must reach a browser that is already open.

- **v0.24.7 — the tab fade.** Switching tabs was an instant `display: none`
    swap with no signal that the screen had changed, so the app read like a
    page reload rather than a tab. It now fades *through* — the outgoing panel
    leaves, the incoming one arrives, opacity only, since a transform on every
    switch reads as a glitch rather than a signature — and both halves ride the
    existing motion tokens, so the global reduced-motion rule already turns it
    into the instant switch with no second code path to keep in step. The swap
    hangs off `animationend` with the same timer backstop the row exit needed,
    and the per-tab refreshes that call back into `showTab()` cannot restart
    the fade.

- **v0.24.8 — the delete that keeps the Gallery/Music copy.** "Delete
    downloaded files" was all-or-nothing: it emptied the app's own folder *and*
    removed the Gallery/Music copies, so reclaiming space destroyed the copy the
    user could actually open. Settings → Device now also offers "Delete app
    copies — keep Gallery/Music": one flow for both deletes — fresh count, the
    same confirm discipline, and still no dialog over an empty folder — with the
    host's MediaStore cleanup simply not made, because the engine's
    `/files/clear` never touched the library to begin with. The button starts
    hidden where no gallery copy exists (browser builds), and both the confirm
    and the toast say the copies stay.

- **v0.24.9 — the cache with an owner, and logs that stop piling up.** The
    deletion machinery was thorough; the *caches* were nobody's job. yt-dlp's
    own cache (player JS, signature data) was never counted and never cleared
    — and on Android it landed in app *data*, where even the system's
    Clear-cache button cannot reach it. The engine now points yt-dlp at a
    directory it owns: the shell exports `SURAVIDL_CACHE_DIR` (Android answers
    with the app's cache bucket, so the system button governs it and storage
    pressure may evict it; desktop falls back to `~/.cache/suravidl`), the
    Device row reports it beside the downloads ("app cache · 340 B"), and both
    delete buttons free it — the same confirm and toast say so, an empty
    folder with a full cache still gets its own "Clear the app cache?"
    dialog instead of "nothing to delete", and the sweep stands down when the
    download folder lives *inside* the cache root (a config mistake, not
    cache). Android's logs were the other slow leak: a timestamped file per
    crash or engine failure, kept in the user-visible Android/media folder
    too, plus a `share-detail.log` appended per shared link — now capped at
    the newest 10 per folder (pruned on every write, and at first launch so an
    update shrinks an existing pile) with the appended one written through a
    bounded appender.

- **v0.25.0 — everything the screenshots complained about, answered.** Five
    complaints from one session, each one real:

    1. *"ERROR: Unable to down…"* — every failed row sliced yt-dlp's message
    to 160 characters in a single ellipsised line, so the explanation the user
    needed was the part that was hidden. The row now renders the whole
    message, clamped to two lines and unfoldable by a tap, with a **Copy**
    button beside **Retry** (clipboard works through a fallback for WebViews
    that refuse `navigator.clipboard`, and the footer's copy-path uses the
    same helper).

    2. *"There's no open and share button for the playlist"* — a playlist
    row's `filepath` is the download folder, which is why the row-level
    hand-offs were withheld (a player cannot open a directory). But the row
    owns real files, so it now offers them: **Files (N)** unfolds a list where
    every entry gets its own Open / Share (Android host) and **Play** — the
    engine serves one recorded entry through `stream?name=…`, matched against
    the list the job wrote, so the parameter can never reach any other file.
    A merged single-file download is *not* a playlist: its `files` also names
    the fragments it muxed, but the finished file is among them — caught live
    in testing, when a video+audio row briefly offered "Files (3)" instead of
    Play.

    3. *"'video only — sound added latter' is ambiguous"* — the label now
    says what the download will do ("video only — sound included"), the sound
    choice became an explicit checklist item (**Video only — no sound**), and
    a site with no separate audio says "no sound available" instead of
    promising a track that does not exist. Sound stays the default: the tick
    rides every start from the card (chips, best quality, playlist) as a
    per-job `no_audio` override, the engine strips the audio pairing
    (`137+bestaudio/best` → `137`; a bare "best" pairs nothing at all), and
    the label flip is live, in place. Verified end to end against a local HLS
    fixture: ticked → `h264` only, unticked → `h264+aac`.

    4. *"Add the open folder button too, below copy path"* — the footer has
    it. Desktop shells reveal the real folder (`POST /app/reveal-dir`);
    Android cannot (no file manager may open Android/data), so the same
    button opens a **folder sheet** inside the app — `GET /files/list` shows
    the folder's own files, newest first, work files and sidecars excluded —
    each with Play, and Open / Share through the host bridge where it exists.

    5. *"Multiple inconsistent UI"* — the fix pass itself: one copy helper,
    one clamp style, one dialog pattern (the sheet announces itself like the
    other two modals), touch-sized controls.

- **v0.26.0 — the second pass over the same screens, and TikTok's own
    retry.** Seven reports from the follow-up session:

    1. *"Use highlights for the chosen subtitle language; I can't unclick
    the one I accidentally click"* — the chips are toggles now: a picked
    chip stays lit (`aria-pressed` drives the fill, so the paint and the
    semantics cannot drift), clicking it again takes it out of the wish
    list, and the row opens with the languages a person is actually after —
    the device's own, then English — with the rest one tap behind a "+N
    more" chip. The old list was alphabetical ISO codes: Abkhazian in
    front, English past the cut.

    2. *"Not all languages are available, depends on the video. The engine
    refuses to download if the language isn't available"* — the wish list
    is per-download but the list is per-video, so a pick the new video does
    not offer is pruned the moment its probe lands (with a toast saying
    what went). The engine never refused: re-verified against a fixture
    that a missing subtitle language skips the subtitles and the download
    still completes — both behaviours pinned by tests now.

    3. The "video only — sound included" suffix read as noise on every
    row. A video-only row says **video
    only**; the "— no sound" suffix appears only while the sound checkbox
    is ticked. The unchecked default still pairs the site's audio, and the
    hint under the checkbox still says so.

    4. *"What's the difference between mp4 1920p with size calculated and
    unknown size?"* — answered in chat: "unknown" is the site not
    advertising a size (fragmented streams), and the same height repeats
    because the containers/codecs differ. The cell now explains that on tap,
    not only on hover.

    5. *"The quality quick download should be below the title right? not
    above"* — moved: the chips now sit inside the video card, under its
    title row. (They were already honest: "Best" is the default, and the
    "✓" marks your pick for that site last time.)

    6. *"TikTok is still broken"* — the exact error ("Unexpected response
    from webpage request") is ticketed upstream as intermittent
    rate-limiting/anti-bot flakiness — "the same videos download fine
    individually, and that's what the repeated passes are for"
    (yt-dlp/yt-dlp#17604). So the engine now retries: `extract_info` gives
    TikTok's refusal two more attempts (0.8 s, 2 s) before surfacing it,
    both probe and download go through that one helper, and the final
    failure carries the next step (hit Retry, or grab it from the in-app
    browser instead).

    7. The suite's own finding: two worker races surfaced under
    random-order runs — a hand-set `completed` status racing a DNS failure
    (the audit helpers stub the worker now), and a cancel landing when a
    playlist's next entry had already started: that entry's `.part` was
    stranded under a name `files` never learns (only finished entries land
    there) and the delete walked past it. Jobs now record every target
    yt-dlp names (`partials`, with an ALTER-TABLE migration for existing
    DBs), the delete sweeps their partials through the same
    inside-the-folder leash, and the test waits for the second entry and
    the worker's death instead of hoping.

- **v0.27.0 — authenticated video, round two: impersonation + the
    stale-cookie voice.** The answer to "is there any way I can download
    authenticated-gated video?" took inventory first: cookies were already
    everywhere (cookies.txt, cookies-from-browser, the encrypted Android
    vault, and the in-app browser handing its own cookie jar with every
    sniff). The two real gaps:

    1. *Facebook-class fingerprinting.* With cookies alone, yt-dlp still
    gets "Cannot parse data" from sites that gatekeep on HTTP header
    fingerprints; upstream's answer is `--impersonate` (curl_cffi), which
    the app had nowhere. There is an **impersonate** setting now (off |
    chrome | firefox | safari | edge — default off), refused at save time
    with the missing package's name when the backend isn't there, carried
    by the ONE options path into probes and downloads alike (a probe hits
    the wall first), and the desktop builds ship curl_cffi: the release
    workflow installs it, the spec collects it (`collect_all`), and the
    frozen-binary smoke test runs with `SURAVIDL_EXPECT_IMPERSONATE=1` — a
    build that lost the backend fails in CI, not on someone's Mac. Android
    stays out honestly: curl_cffi has no Android wheels, the settings row
    hides there, and the phone's route is the cookies import (or the
    in-app browser) it already had. Verified against a real onefile build:
    `SELFTEST_IMPERSONATE ok — curl_cffi 0.16.3, chrome target loads`,
    plus an impersonated probe against the fixture server end to end.

    2. *Stale-cookie silence.* An expired cookies.txt failed with the same
    words as no cookies at all. The sign-in-wall hint now says the cookies
    may have expired ("Instagram sessions last only hours"), and the
    Android vault's status line reports WHEN the last import happened —
    the difference between "it's broken" and "it's three days old".

- **v0.28.0 — the phone's routes, said out loud; `docs/AUTH.md`.** The
    second half of the auth-gated plan. The engine could already carry a
    session; what the phone lacked was saying where its sessions come
    from. The in-app browser now wears a dismissible one-line hint ("You
    can sign in here — this browser's session goes with the download"),
    its empty state — the exact place a login-walled page leaves the user,
    staring at "nothing found" — repeats the route, and the start page
    says it before the first scan. The Android Settings hint swaps its
    text for the phone's two real routes: sign in inside "Find a video on
    a page", or import a cookies.txt exported from a desktop browser; the
    hint span gains an id (`#authHint`) so the swap is pinned. One new
    on-device assertion (`SnifferTest.theBrowserOffersTheSignInRouteOnScreen`)
    proves the hint is actually on screen — a source-substring check is
    decoration. And the document the plan promised: `docs/AUTH.md` — the
    routes per platform, per-site notes (Facebook → cookies AND
    impersonation; Instagram → hours-long sessions, rate limits, account
    risk; DRM → never), where cookies live on each platform, and a
    five-minute verify-it-yourself checklist for desktop and phone. The
    README's signed-in bullet links it.

- **v0.29.0 — the cache's own button; the built-in presets grow up.** Two
    asks off one screenshot (2026-09-28). First: "why not make 'delete
    cache' as a different button?" — right; v0.24.9 had folded the cache
    sweep into both file deletes (the cache then had no owner), and the
    hint had to explain the side effect. Now `/cache/clear` is its own
    endpoint with its own confirm word, its own button ("Clear app cache"),
    and the same stand-down guard (a cache root containing the downloads is
    a config mistake, not a wipe target); `/files/clear` does files and
    nothing else — the reversal is deliberate, and the old tests were
    rewritten to the new contract, not deleted. Unlike the file delete, the
    cache clear never refuses for a running job: nothing it deletes can be
    a `.part` or a finished file. Second ask: more built-in presets —
    the built-ins were seven audio intents. Added: two MP4-compatibility
    format intents (`video-mp4-1080`, `video-mp4-720` — H.264+AAC preferred
    when the site has them, the app's usual capped ladder when it doesn't,
    and FFmpegVideoRemuxer repacks the result so the file opens on a
    TV/iPhone/WhatsApp), and three pure-patch bundles (`subs-en-sidecar`,
    `subs-en-embed`, `metadata-cover`). That exposed a real gap: `/jobs`
    expanded only USER presets, so a built-in that was not a bare intent
    would have died as an unknown preset — builtins and saved presets now
    expand through the same `split_patch`. The intent map got its honest
    name (`FORMAT_INTENTS` — it holds video now), the options chip shortens
    `video-` names like `audio-` ones, and every new format expression is
    asserted against yt-dlp's own parser plus one real end-to-end remux
    download.

- **v0.30.0 — refusing the app hand-off.** The 2026-09-28 report, second
    half: a TikTok page inside "Find a video on a page" navigated itself to
    `snssdk1180://aweme/detail/<id>` — the page's own "open our app" move.
    Nothing refused it, so the navigation died half-way: scheme URL stuck in
    the address bar, the find list wiped, the page blank (the screenshot that
    started this). The engine was innocent — the probe runs yt-dlp directly
    and never touches this browser; its failure that day was TikTok's known
    intermittent rate-limiting (reproduced and green from the server within
    the hour). Now `SnifferWebViewClient` overrides
    `shouldOverrideUrlLoading`: anything that is not `http(s)` is refused
    before the navigation starts, and the browser says so on its own line —
    "app link refused (snssdk1180://) — only web pages load here". Every
    door shares the one definition of a web URL (`isWebUrl`): the WebView
    client, the popup (`target=_blank`) path and the Go button — where a
    pasted app link is now named rather than mangled into a fake https URL.
    The refusal note is its own view with its own tag, so `render()`'s
    status line can never eat it, and a real navigation hides it. Proven on
    the emulators: the new instrumented test fires `snssdk1180://` from a
    live page and asserts the browser stays put and speaks.

- **v0.31.0 — the transplant; a size for HLS.** Two ideas from the cobalt
    read (the ideas — its `api/` is AGPL-3.0 and `web/` is CC-BY-NC, so no
    code crossed over). **The transplant:** cobalt re-runs its extractor
    mid-download when a signed CDN link expires under a running transfer;
    here it falls out of the one retrying extractor — `retry_refresh=True`
    chains a progress note in front of the caller's hooks, and when a
    download dies on an HTTP 403/410 *after bytes had arrived*, the
    extraction is re-run once for fresh links, with yt-dlp's own
    `continuedl` resuming the `.part` underneath. The gates are the point:
    no bytes → no retry (a refusal before any progress is the site's
    answer), one refresh per job, and TikTok's flake keeps its own path
    untouched. **The size:** an HLS manifest never says how big the stream
    is, so `/classify` reads the playlist (the highest-BANDWIDTH variant of
    a master), takes ONE segment's size × the playlist's duration span and
    marks the verdict `estimated` — the phone now shows "HLS · ~42 MB"
    instead of a bare "HLS", and a manifest's own byte length is never
    reported as the stream's size (which used to leak through as the
    playlist file's own few KB). Unmeasurable stays bare; the estimator
    reads playlists and probes a single segment, never a stream. DASH gets
    the honest no-size. 16 new tests, one real-HLS round trip.

- **v0.32.0 — the "What's new" card.** Requested verbatim ("Can you add
    'what's new' pop up for the first launch after the update in the app??"),
    landing where one implementation covers every shell — the Android app,
    the desktop window and the browser all render this UI. The engine owns
    the notes (`whatsnew.ENTRIES`, `GET /whats-new`) and the suite fails on
    a version bump that ships without an entry: the card is only as honest
    as that list. The UI shows the entries NEWER than the version this
    device last ran (localStorage — the same per-device durability as
    skip/snooze), capped at three, and the selection rule is executed in
    Node inside the tests against the real functions. The card waits for
    "Got it" (until then the next launch asks again) and a device that never
    saw a card gets the current release's notes — the first card; after that
    it is strictly what is new to it (the fresh-install rule had to flex:
    an EXISTING install has no marker either, and would otherwise never see
    the card for the very update that ships the feature). Settings → What's
    new re-opens the current release's notes any time. Verified end-to-end
    in a real browser: a fresh boot with no marker shows the current
    release, a simulated 0.30.0 → 0.32.0 shows exactly the two unseen
    releases, dismissing records the version, a reload stays quiet, and the
    Settings button re-opens the card.

- **v0.32.1 — the second audit's fix batch.** The v0.32.0 tree went through
    another read-only agy audit ("delegate to agy, audit the app, then you
    confirm and fix it"); eleven findings came back and six survived
    independent reproduction — each has a RED test in `test_v32_1_fixes.py`
    written before the fix, and the five that did not survive (a `_cmp_version`
    helper, an `exportForEngine` cookie export, an api.py stem-prefix sidecar
    match, a missing opus mime, unguarded extension fetches — none of them
    exist in this tree; the report's line numbers drifted onto some other
    codebase) are recorded as refuted, not fixed. The six that were real:
    (1) `/files/stream` built `Content-Disposition` from the raw name, so any
    non-latin-1 file name (CJK, Cyrillic, emoji) crashed the response with
    `UnicodeEncodeError` — latin-1 headers can't carry it; now RFC 5987
    (ASCII fallback + `filename*=UTF-8''…`). (2) HLS estimation fetched
    whatever the playlist pointed at — `file:///…` (a local-file read) and
    link-local addresses; every playlist URL now gets the same vetting as
    the main URL (scheme + `blocked_reason`), the span math follows the
    segments that survived, and a master whose best variant is unfetchable
    is refused. (3) deleting a job `rmdir()`ed ANY empty parent that was not
    the CURRENT root — after a Settings folder change that is the previous
    download folder; the cleanup now prunes only a parent strictly INSIDE
    one of the roots (current, or the row's recorded one) and never a root
    itself. (4) `/jobs/{id}/retry` skipped `/jobs`' preset expansion, so
    bundle/saved presets died as "unknown preset" and a preset↔format edit
    tripped create's "not both" refusal; retry expands exactly like
    queueing, and a `_requeue` edit that names one lane clears the other.
    (5) a 206 range probe carries `Content-Length: 1` — the byte asked for —
    and the real size in `Content-Range`; the estimate read the 1 and came
    out as ~2 bytes (Content-Range now wins). (6) subtitles are reclaimed
    with their video: the srt convertor leaves `Name.en.srt` and only the
    final info knows the renamed path (the progress hook saw the `.vtt` it
    replaced), so the run now records `requested_subtitles` filepaths, and
    the delete-side sidecar pass matches language-tagged subtitles
    (`Name.en.vtt`, `Name.en-US.srt`) with a strict language tag —
    `Name.2.vtt` is not one. 14 new tests; suite 543 → 557, both orders.
- **v0.33.0 — the polish pass.** The first run of the `impeccable` design
    skill over the real UI (desktop 1440×900 + phone 390×844, three themes,
    both glass styles, every modal, every job state, live downloads on a
    throttled fixture). Eight suspicions came out of the use-first pass;
    seven survived verification. (1) `probeMsg` kept class `msg muted` — the
    app's one grey error; now `.msg.bad.mono` (Nova Rose + machine voice per
    DESIGN.md), with the class reset at the start of each probe. (2)
    `Math.round(8 / 60) + " min"` = `"0 min"` for any clip under 30s — now
    `"<1 min"`. (3) `.audioRow` carried 20px of side padding on top of the
    card's 18, so the chip rows sat deeper than the probe title and the
    format table beside them — flush now. (4) scrollbars were OS stock on
    dark glass (loudest in the Presets list) — themed via `scrollbar-color:
    var(--dim)` + a webkit fallback for Chromium < 121. (5) text selection
    and the caret shipped browser defaults — new per-theme `--sel` token +
    `caret-color`. (6) data numerals were proportional while sizes and
    percents update between polls — `font-variant-numeric: tabular-nums` on
    .meta/.jmeta/.fmt-s/.fsize. (7) link underlines ran through the word
    space — the footer read "copy_path / open_folder"; `text-underline-offset`
    now. The eighth (active Settings sub-tab cut off at 390px) was refuted
    live before any edit: `showSettingsTab` has scrolled the active sub-tab
    into view since v0.17.0; the repro was a viewport-shrink artifact — the
    behavior is pinned now instead. The rendered-pass detector run caught one
    more real one the file scan could not see: placeholder text sat under the
    4.5:1 floor (the paste field's own 3.7:1, every bare input on the
    browser's grey, 4.3:1) — placeholders now carry a per-theme `--ph` token.
    The rest of its report (gradient palette, glow shadows, single font
    family, the aurora halo, the width-transition progress bar) is the
    committed DESIGN.md answering a generic checklist — recorded, not
    changed. 9 new tests; suite 557 → 566, both orders; PRODUCT.md +
    DESIGN.md join the repo, `.impeccable/` is ignored.
- **v0.34.0 — presets that make sense.** Two field reports off the phone.
    (1) An m4a job died on `Unable to download video subtitles for 'en':
    HTTP Error 429` — yt-dlp fetches captions before the media streams, so
    a throttled captions endpoint cost the whole download. Subtitles are a
    sidecar: a subtitle-shaped failure now retries once with every
    subtitle option stripped (`_drop_subtitles`) and the job completes
    with a note naming the refusal ("subtitles could not be fetched
    (HTTP Error 429: …) — downloaded without them"); anything that is not
    a subtitle error still fails, and the retry is offered once.
    (2) The preset row could apply a bundle but never save, show or
    change one. It now does all three: "Save these options as a preset…"
    stores the block's own fields (audio intent included), "Update
    “name”" writes them back into the applied user preset (built-ins
    stay read-only), and the applied preset spells out every key it
    carries — including keys the block has no field for. The select
    learned to mirror the applied preset (it went blank after a save,
    because the name was set before the option could exist). Impeccable's
    Operate guidance: inline progressive disclosure, no modal, the
    existing control vocabulary. 9 new tests; suite 566 → 575, both
    orders. versionCode 54.
- **v0.35.0 — the download end of the preset workflow.** The preset flow
    needed its download end — applying a preset should shape the actual
    download, not just sit in the panel. Reproduced live
    at phone width — four defects, all real: the armed set hid in the
    collapsed block below the formats table, nowhere near a download
    button; the start toast said a bare "Added to downloads" whether or
    not a preset shaped the job; a quality pick silently replaced an
    audio preset's format (armed "m4a", tapped 720p, got a silent video);
    and the one-shot clearing had no announcement anywhere. The video
    card now carries an armed strip under its head row ("next download:
    “audio-m4a” — extract the audio to m4a" + ✕), painted from
    renderOvCount — the one count that already updates on every change
    path — so it can never drift from the block. The start toast names
    what rode ("— with preset “audio-m4a”", "— with 3 options set
    below"), and the format-over-intent case speaks ("— “audio-m4a”
    skipped: your format pick replaces it"). Tapping the strip opens the
    block and scrolls it into view; its ✕ is the block's Clear. Two live
    catches beyond the report: the strip's light-theme ink measured
    3.65:1 (under the repo's 4.5 floor for small text) — light
    `--accent-ink` is now #0a55a8 (5.43:1), pinned in a test; and
    `behavior: "smooth"` scrollIntoView proved inert in the stripped
    headless browser — the scroll is instant. 8 new tests; suite
    575 → 583, both orders. versionCode 55. (Never tagged on its own —
    it ships folded into v0.36.0.)
- **v0.36.0 — a preset that stays.** "Kept as is, if the user wants more
    permanent solution they can go to the settings. Maybe add presets in
    the settings to?" The one-shot block stays one-shot; permanence is a
    setting: Settings → Presets names one Default preset that rides every
    NEW download. The engine layers it like every other setting — a plain
    download rides it whole (intent + bundle); an explicit preset's intent
    wins while the default's bundle still fills in; a quality pick beats
    the format intent with the bundle intact; per-download fields win over
    its values; a preset deleted later quietly stops riding (it must never
    brick /jobs) and the select shows "no longer exists" instead of
    falling back to none. "default_preset" joins PER_JOB_DENIED (a job may
    not decide what every future download carries) and POST /settings
    refuses an unknown name at the boundary. 10 new tests; suite
    583 → 593, both orders. versionCode 56. Ships the v0.35.0 workflow
    fixes in the same release (v0.35.0 was never tagged on its own).
- **v0.37.0 — The Post House (the major overhaul).** Brief: the UI feels
    generic — make it modern, iOS-like liquid and frosted glass, easy for
    newcomers, advanced options for enthusiasts, multi-platform, across
    all screen sizes. Ran the
    impeccable machinery end to end: the review found 25/40 with the
    verdict "generic shell, specific instrument"; a seeded direction round
    produced five options; the user picked The Post House (an ingest room:
    deck, scopes, transport, patch bay, filed bins) — code-led build, no
    comp round. The replacement world ships whole: a scope strip that reads
    source · formats · largest for every probe; picks ARM a take and only
    the amber START commits it (startJob returns a boolean; a commit
    spends the take and unlights every pick — caught live: the paint loop
    lived in armTake alone, so a spent row stayed lit); a finish that
    speaks (one transition-fired toast with Play / Show folder, a FILED
    stamp on the row, the FILED TAKES rail); a human-first error voice
    with the raw engine message behind Show details; 30 drawn SVG icons
    (the emoji die); self-hosted variable fonts (Archivo + Martian Mono,
    OFL, latin woff2); stylesheet and markup rebuilt from the ground up
    (1,041 + 872 lines) with every legacy contract kept (.chk,
    .chip[aria-pressed], .ghost-sm.del, k-* kind colours). The glass
    ladder verified live — frosted blur(14px) saturate(115%); liquid
    blur(26px) saturate(165%) brightness(1.04) + specular gloss + amber
    edges; Android keeps REAL blur at 11/19px and only flattens the
    full-screen overlay; @supports falls back to solid panels — pixel
    proof captured (footer text visibly smeared behind the fixed
    transport). Live walk: deck → probe → arm → START → Added → Filed →
    bins 13→14 across phone, tablet, ultrawide, light/dark/AMOLED, zero
    console errors. Fixed en route: the mobile take readout truncated to
    "best availa…" (12.5px reading + slimmer START), and the toast lane
    math re-based on --tabbar-h. 19 new tests; suite 593 → 612, both
    orders. versionCode 57. DESIGN.md rewritten to the committed system.
- **v0.37.1 — the device pass (five defects off the user's phone).** "the
    scrollbar is too big in the what's new pop up, the blur isn't working
    (look at the screenshots), changing the tab feels slow … also black bar
    behind the confirmation button … changing submenu in settings doesn't have
    animation." Each photo traced to a cause: (1) the custom webkit
    scrollbar rules had overridden Android's native transient overlay with
    always-on 9px bars that read like a desktop bar inside a phone dialog —
    6px on desktop, hidden entirely on touch; (2) [MIS-DIAGNOSIS, reverted
    in v0.37.2] I read the device screenshots as showing the transport and
    dialogs unblurred, and made the floating plates near-opaque on the
    android host (--glass-float); re-measuring the same screenshots (edge
    energy: blurred ghost text 19 vs crisp text 81 behind the transport)
    proves the phone compositing the real blur — the revert restores the
    shared glass;
    (3) the tab swap was serial — a .14s exit fade, THEN a .4s panel wash:
    the next screen only STARTED once the old one had finished leaving; the
    swap is synchronous now with one 140ms arrival lift and no event
    dependency (measured live: 7.5ms click-to-visible, one tabIn @140ms);
    (4) the settings sub-tabs swap with the same arrival animation; (5) the
    android flatten rule is scoped to the settings Save strip — it had
    painted every .modal-foot a near-black slab (the black bar behind Got
    it / Cancel / Delete). Found on the way: the raw error text wrapped one
    word per line in the narrow column it shared with the buttons (full
    width now), and six sub-tabs never fit a 393px row ("Auth" half-cut) —
    they wrap to two. Suite 612 → 620; two motion-contract tests rewritten
    to the new truth; the phone capture rig still drops the fixed transport
    layer (DOM + computed styles are the truth). versionCode 58.

- **v0.37.2 — the glass stays (revert).** The user: "Why did you delete the
    blur for the Android. The previous version has a working liquid glass
    blur." Correct. My v0.37.1 read of their screenshots was wrong — soft
    ghost text at a small blur radius reads as "crisp" at phone scale, and
    I trusted that reading over both the pixels and their own history. The
    numeric pass (blurred ghost text 19 vs crisp 81 behind the transport;
    modal ghosts 44 vs dialog text 57–70) confirms the WebView composites
    backdrop-filter. The near-opaque float plates, their three theme tokens
    and their pins are gone; the shared glass (11/19px on android) covers
    dialogs, the transport and toasts again. Everything else from the
    device pass stands. versionCode 59.

- **v0.37.3 — the steady pass (three phone reports).** "the start best is
    stuck after tab switching … the chosen Bottom bar tab needs a squircle
    outline … What's new pop up doesn't have blur." Root cause of the stuck
    bar: the v0.37.1 arrival animated `transform: translateY(4px)` on the
    panel, and a transform makes the panel a CONTAINING BLOCK for its
    `position: fixed` transport — after each switch the bar re-anchored to
    the panel (reproduced live: content-relative y 405, moved with scroll)
    instead of the viewport (699, pinned, unmoved). The arrival is
    opacity-only now. The android overlay kept the v0.22-era flat veil, so
    the popup's backdrop read as "no blur" — it frosts again (blur(10px)
    saturate(120%), veil .72 → .55; desktop has blurred it since v0.22).
    The chosen bottom-bar tab: 2px top hairline → squircle outline (1px
    accent-line, 15px radius, glass fill). Take readout keeps "best
    available" whole on a phone (12px + 10px gap). Suite 620 → 624;
    versionCode 60.

- **v0.37.4 — the backdrop pass.** The DESIGN.md request ("don't forget to
    add the blur liquid glass design") turned up a doc-vs-code gap: DESIGN.md
    claimed the overlay frost, but only the phone had it (v0.37.3) — the
    desktop veil was still a flat dim, the exact state that made the popup
    read as blur-less. The frost now lives on the base `.overlay` rule
    (blur(10px) saturate(120%), veil rgba(4,6,9,.55)), one definition for
    every host, the android-era override gone; a lying CSS comment ("desktop
    has blurred it since v0.22") corrected. DESIGN.md's glass section is now
    the material spec sheet: the five-part stack (fill / blur / gloss /
    hairline / highlight), both finishes with exact tokens, host deltas with
    the edge-energy proof, where the material lands, the intentionally
    solid surfaces (toasts, Settings Save strip), and a new Measured-Blur
    rule. Suite 624 → 626; versionCode 61.

- **v0.37.5 — the bar comes home.** "there's no liquid glass effect aka the
    blur in the 'best available' card" + "where's the animation for 'this
    download only' opening and closing?" The zoomed photo showed the storage
    block's text crisp THROUGH the transport — no backdrop pass composited.
    Truth established across three versions: the in-flow glass blurred on
    the device (v0.36 + v0.37.0), the fixed bar does not (v0.37.1+); the
    2026-09-30 "19 vs 81 edge-energy proof" was measured through v0.37.1's
    near-opaque fill, so it proved dimming, not blur — and this WebView
    skips the backdrop pass for fixed layers over scrolling content (the
    same reason the fixed bar collided with the footer's last line). The
    phone transport rides sticky-in-flow again (also structurally unable to
    overlap the page's end; footer leg 190px → 150px). The bay — a bare
    <details> since M17 — now opens through a door: summary clicks are
    intercepted so the browser never snaps the content; a .bay-body wrapper
    transitions max-height + opacity and [open] flips when it settles
    (500ms safety seal; programmatic opens skip the door on purpose).
    Suite 626 → 631; versionCode 62.

- **v0.37.6 — the board reads at phone width.** Second device report off the
    16:22-16:24 photos. (1) "the blur still not applied ... behind 'best
    available' it's still crisp" — sticky in-flow did NOT restore the pass:
    proven dead in both geometries (fixed v0.37.1-4, sticky v0.37.5); the
    shell is hardware-accelerated (no setLayerType, manifest default), this
    WebView just doesn't composite backdrop-filter for floating plates. The
    blur declarations stay; the android transport pours dense (85%
    panel-solid via color-mix) and the overlay veil returns to the
    v0.36-proven rgba(3,5,12,.72). (2) "after probing the list goes
    overflow" — the four-column format table cannot fit 393px (Take buttons
    off the right edge); phone rows re-stack (quality+Take / format / size,
    header hidden). (3) "toast appears to the center instead of after the
    bottom bar" — the settings tab's +150px lane floated toasts over the
    panel; one phone lane now (tab bar + 84px, clears the Save strip).
    Suite 631 → 635; versionCode 63.

- **v0.37.7 — the readable queue.** Device report (17:32 photo + a crop).
    (1) A queue count pushed the queue button off its column — the
    phone tab is a centered column; the count badge was a flow child, so
    its height shifted the tab's icon+label up against the siblings. The
    badge is absolute on the icon's corner now (inert, zero layout
    impact; verified live: icon Y identical across all four tabs with the
    badge on/off). (2) "expand the card when you click on the queue card,
    so I can read at least the full title" — a tap on the title unfolds
    it; the open title takes the row's FULL width (flex basis 100% + a
    wrapping .jobtop:has rule — beside the pills its box can collapse to
    ~30px and the naive fix wrapped one letter per line, caught in the
    live harness). Suite 635 → 637; versionCode 64.

- **v0.38.0 — pine & cream (the brand).** The identity is rebuilt from the
    current logo's idea (download arrow + play), not its look: the play is a
    knockout inside a cream arrow on a pine tile. Master SVGs + lockups in
    assets/brand/ (single-path, no text/mask/gradient; wordmark outlined from
    Archivo 600), all rasters — favicon, extension set, Android legacy +
    adaptive mipmaps for all densities, desktop .ico — generated by
    scripts/build_brand.py. The header mark is now drawn SVG fed by
    --mark-tile/--mark-arrow: pine by day, the cream chip at night/AMOLED
    (the pine tile measured 1.8:1 on graphite — it sank). Suite 637 → 644;
    versionCode 65.

- **v0.38.1 — straight to Download.** Reopening the app should land on
    Download, not whichever tab was last touched. The boot restored the
    last tab from localStorage (suravidl.tab) — the phone loads a fresh
    http://127.0.0.1:PORT/ each launch, so the remembered key always won. The
    restore (const + write + read) is gone: boot = hash || download. The hash
    stays a real address (a #settings link still opens Settings; a mid-session
    reload keeps its tab). Verified live on all four boot paths (stale key →
    download, #settings → settings, reload #queue → queue, fresh → download).
    Suite 644 → 647; versionCode 66.

- **v0.38.2 — the receipt and the lane.** Two device reports (06:23 photo,
    2026-10-01). (1) The toast lane floated above a gap — it should adapt,
    clearing only real furniture: the phone lane was
    pinned at bar + 84px everywhere — a value tuned for the Download
    transport, which is STICKY and only sits at the bottom once the page is
    long enough (a probed list) — so on Queue it hovered over nothing. The
    lane now MEASURES (syncToastLane): its fallback is bar + 12px; when the
    transport or the settings Save strip is really docked in the bottom
    140px band it lifts to 8px above that furniture. Verified live at
    393x852: Queue 9px above the bar; probed Download lifts to 707 vs
    transport top 715 (inline bottom: 145px); Settings 8px above the strip.
    (2) An expanded Queue card should show the size and the location, not
    just the name: the unfolded card gains a receipt (size + full saved
    path, mono, wrapping); the engine stats the real bytes — size_bytes in
    the row serializer AND in the live get()/list() copies (the in-memory
    dict never passes _row_to_job — caught live when the API answered
    null). Suite 647 → 653; versionCode 67.

- **v0.38.3 — the audit and the second voice.** agy audited the UI against
    the impeccable + antislop rulebooks; every finding verified here before
    code (agy's contrast numbers checked out ±0.03; one stale cross-ref
    ignored). Fifteen fixes: light-theme site liveries get dark brand inks
    (YouTube #c5221f, X #1d68c9, Vimeo #0073a8, IG #a82782, TikTok #077a6e —
    all past 4.5:1); the what's-new card rides the real dialog lifecycle
    (openModal/closeModal, Escape, backdrop); the queue title expands from
    the keyboard (Enter/Space, aria-expanded, role=button — the tap wiring
    kept intact for the v0.37.7 pin); "Best" no longer wears the armed lamp
    before it is armed; the minimize button is a drawn SVG minus; the
    active-tab icon takes --accent-ink (6.81:1 on the light bar); six
    unnamed form controls get labels; chips hit 8px radius + 44px touch
    target + press state under pointer:coarse; settings sub-tabs become a
    real tablist; --ok darkens in light (#1b6942, 5.26:1); preset rows stop
    pretending to be clickable; the error-details toggle carries
    aria-expanded/controls; match counts pluralize in mono; the queue shows
    "Checking the queue…" before the first poll. AND the Pine & Cream
    scheme: data-accent="pine" in Settings → Appearance — light keeps pine
    #14493C on cream ink (8.1:1), dark/AMOLED flip to cream on pine ink
    (15.6:1); --accent-fg/--accent-glow tokenized first so the hardcoded
    #1a1305 ink dies; swatch previews follow the scheme. Suite 653 → 674;
    versionCode 68.

- **v0.38.4 — the native glass.** Can the Mac app sit on Apple's real
    liquid-glass material API? Yes — behind the page:
    Apple exposes Liquid Glass only to native toolkits (SwiftUI glassEffect,
    UIKit UIGlassEffect, AppKit NSGlassEffectView, macOS 26+), never to web
    content, so per-element glass stays CSS — but the SHELL can sit the
    whole window on the real material. _try_window now creates the darwin
    window transparent (TypeError retry for older pywebview);
    _native_glass_ready (the webview.start callback — window.native exists
    only after the GUI loop is up) inserts NSGlassEffectView behind the
    WKWebView (addSubview:positioned:relativeTo: NSWindowBelow), falls back
    to NSVisualEffectView vibrancy (.behindWindow, UnderWindowBackground)
    on pre-26, turns drawsBackground off (KVC), and syncs the material
    appearance to the page theme at launch (restart to re-sync). Only on
    success does it set data-host="darwin-glass" — the CSS rule
    html[data-host="darwin-glass"] body { background: transparent } lets
    the page yield (verified live: body rgb(15,18,22) → rgba(0,0,0,0),
    plates keep their tints). pyobjc is optional: no AppKit/no native →
    plain window, no flag. AND the dock icon: build_brand.py gains
    build_icns() (hand-packed container — Pillow writes ICNS only on
    macOS itself; icp4..ic10 PNG chunks from the 1024 bleed master),
    assets/icon.icns committed so the .app BUNDLE works from the repo
    (the spec's CFBundleShortVersionString also finally bumped). Suite
    674 → 685; versionCode 69.

- **v0.38.5 — the fold.** Phone screenshot report (11:50, 2026-10-01).
    (1) The expanded card snapped open and shut — no fold: the
    receipt swapped via display: none → grid, which cannot animate — it
    now FOLDS: .jdetails is a persistent grid collapsing through
    grid-template-rows 0fr → 1fr (+opacity 0→1, margin-top 0→9px, .28s
    cubic-bezier(.2,.7,.3,1)), with the receipt rows wrapped in .jdgrid
    (overflow hidden, min-height 0 — the shrinkable row the 0fr trick
    requires); the mono type + dashed top rule moved onto .jdgrid and
    animate in (padding-top, border-top-color). Verified: open rule
    applies with transitions off (rows 37.5px, opacity 1); the old-headless
    rig cannot tick transitions (no compositor — same blindness class as
    backdrop-filter), so the tween itself is phone-verified. Chromium
    animates grid-template-rows since 107; older WebViews degrade to
    today's snap. Reduced-motion clamps it (global .001s rule). (2)
    .job:has(.jobtitle.open) .path { display: none } — the compact
    ellipsised strip yields once the receipt carries the full path
    (verified live: block when closed, none when open). Suite 685 → 691;
    versionCode 70.

- **v0.38.6 — the straight answer.** Report (phone, 2026-10-01): the
    humanized line and the "Show details" text disagreed, and the human
    one pointed at the wrong fix. Root cause found by reproducing in real
    JS (the tests extract humanErr and run it in node): the sign-in
    regex's bare `age` alternative matched "page", so every "Unsupported
    URL … no extractor for this page" read as a sign-in wall — and the
    branch order let it win over the unsupported branch. Fix: word
    boundaries on every alternative (`\bsign[ -]?in\b|\blog[ -]?in\b…|
    \bage\b`), the unsupported branch ordered before the sign-in family,
    and — the deeper repair — the engine's structured verdict now leads:
    /probe already sends detail.unsupported + hint (auth.py), api()
    already carries it as err.detail, so the probe pass-through calls
    humanErr(e.message, e.detail) and a structured verdict can never be
    re-guessed into another story. Same pass: the releases' prompt quotes
    are gone from PLAN (commits stay as published; no force-push) and the
    no-verbatim-quotes rule is recorded in the skill. Suite 691 → 695;
    versionCode 71.

- **v0.38.7 — the tuck.** Two desktop reports (2026-10-01): the window's
    "−" should tuck the app away to the tray instead of running the
    standard Dock minimize, and the desktop app shows no motion at all.
    The − path is now tray-aware: on macOS the whole app hides behind an
    NSStatusItem (SF Symbol arrow, Show suravidl / Quit suravidl; the item
    is visible exactly while the app is tucked, driven by the app's own
    hide/unhide notifications), and on Windows and Linux the window hides
    behind a pystray icon. Every missing piece — no pyobjc, no pystray, no
    icon file, a tray that refuses to start — degrades to the old plain
    minimize; --no-tray still forces it. macOS hides at the NSApp level,
    so the Dock icon restores the app the way Mac users expect; pystray
    destroy/restore are thread-safe marshals in pywebview 6.2.1 (winforms
    Invoke, GTK glib.idle_add), so the actions are safe from the API
    thread. Motion: the page's only global kill switches are
    prefers-reduced-motion (system-level; we follow it — that is the
    point) and WebKit pausing transitions while the page reports itself
    hidden. The shell now probes both ~2.5s after boot (logged as
    SURAVIDL_MOTION), re-fronts the window once when it claims to be
    hidden, and Settings → Appearance shows a quiet note naming whichever
    switch is in force and where to change it. Suite 695 → 710;
    versionCode 72.

- **Extension 0.5.3 — the Firefox that never worked.** The 0.5.2 build AMO
    approved did nothing on Firefox, and the cause was measurable: the
    background script registered its header listener with the Chrome-only
    `extraHeaders` spec value, and Firefox refuses that value — "Invalid
    enumeration value" — by *throwing at the call site, mid-load*. Every
    listener declared after it (the popup's message port included) never
    existed; the popup sat on "loading…" forever. Chrome never noticed — it
    accepts the flag (and needs it to see Cookie/Referer). A second, quieter
    bug sat behind it: Firefox's `chrome.*` namespace is callback-only —
    tabs.query, sendMessage and storage.local.get return *undefined* without a
    callback, not a promise — so the popup's awaited queries and the
    background's awaited storage reads never saw an answer. The promise
    namespace is `browser`, and Chrome's `chrome.*` returns promises; both
    now ask `globalThis.browser || chrome`. Reproduced and fixed against real
    Firefox 157 (probe extension logging every answer to a local HTTP
    endpoint — the old-headless rig cannot host Firefox): before,
    background.js died at line 146 and the popup never left "loading…";
    after, popup → handoff → engine → completed download, UA and referer
    included. The Node harness grew a Firefox flavor shaped by those
    measurements — it fails on the shipped 0.5.2 source and passes on the
    fix, and now exercises the popup too. The popup gained its Options link
    (address + token) and the failure texts say where the token goes.

- **v0.38.8 — the trust bundle.** The desktop app's "Check now" failed on
    macOS with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer
    certificate`, and it was never a network problem: a packaged Mac app's
    Python has *no discoverable CA store* — OpenSSL's compiled-in paths do
    not exist there, and Python never consults the Keychain — so every
    stdlib `urlopen` that verifies a real certificate dies. yt-dlp never
    noticed (it loads certifi's own bundle), which is why downloads worked
    while the update check failed. Reproduced on Linux by hiding the store
    (`SSL_CERT_FILE=/nonexistent SSL_CERT_DIR=/nonexistent` → the identical
    error). Fixed at the source: a new `suravidl_engine/net.py` builds one
    TLS context — `ssl.create_default_context()` plus certifi's bundle
    *added* on top (platform and corporate stores survive; nothing is
    substituted) — and the two stdlib fetch sites (the update check, the
    classify/direct-media probes) now pass it to `urlopen`. The PyInstaller
    spec collects certifi's data explicitly so every frozen build carries
    the bundle, and the update row explains a certificate failure in plain
    words and opens the releases page instead of showing a raw error line.
    Suite 712 → 718.
