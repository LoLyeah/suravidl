# suravidl Product Feature Report

## 1. Product Position Verdict

**Where suravidl already leads:**
- **Cross-platform single-engine parity:** Unlike Android-only Seal/YTDLnis, desktop-only Parabolic, or cloud-relayed cobalt, suravidl runs one FastAPI engine (`src/suravidl_engine/api.py:567-590`) and one glass UI (`src/suravidl_engine/web/index.html:110-240`) across desktop, Android, and browser extensions (`PRODUCT.md:26-35`).
- **Authenticated & obfuscated stream sniffing:** Companion extensions and Android in-app browser sniffing capture streams, cookies, headers, and XOR keys to materialize scrambled HLS playlists locally (`src/suravidl_engine/api.py:91-101`, `src/suravidl_engine/jobs.py:1740-1750`, `src/suravidl_engine/web/index.html:127-138`)—recovering media where Parabolic, Seal, YTDLnis, and cobalt fail.
- **Playable-everywhere output & honest probe-first UX:** Probes real formats into the scope strip before downloading (`src/suravidl_engine/probe.py:40-89`, `src/suravidl_engine/web/index.html:146-163`), enforces QuickTime/TV-safe H.264/MP4 remuxing (`src/suravidl_engine/jobs.py:275-295`) or smart MKV subtitle fallback with honest notices (`src/suravidl_engine/download_opts.py:734-745`), and provides polite, deduplicated channel/playlist following (`src/suravidl_engine/follows.py:1-55`).

**Where suravidl is clearly behind:**
1. **High-friction Android share & background feedback:** Sharing a link to Android (`android/app/src/main/java/com/suravidl/app/MainActivity.kt:754-764`) only prefills `#url` (`src/suravidl_engine/web/index.html:120-122`) rather than offering YTDLnis/Seal's instant download sheet, and `EngineService` displays only a static `"downloading $n…"` string (`android/app/src/main/java/com/suravidl/app/EngineService.kt:322-336`) without progress bars, speed, ETA, or cancel actions.
2. **Post-processing & metadata polish:** Lacks YTDLnis's chapter splitting into separate files (currently only clips a single time range at `src/suravidl_engine/download_opts.py:712-722`) and pre-download title/artist tag editing (currently only boolean `embed_metadata` at `src/suravidl_engine/download_opts.py:788-790`).

---

## 2. Ranked Feature Recommendations (Best First)

### 1. One-Tap Quick Download on Share & Paste
- **What it is:** A "Download now" button beside `Probe` and an Android share-intent option that immediately queues a link using the user's `default_preset` without stopping at the format picker.
- **Why it earns its place:** Matches cobalt's zero-friction speed and YTDLnis/Seal's quick-download flow; today `MainActivity.sharedUrlFrom` (`android/app/src/main/java/com/suravidl/app/MainActivity.kt:754-764`) forces a full UI trip to `#url` (`src/suravidl_engine/web/index.html:120-122`) even when `default_preset` is set (`src/suravidl_engine/settings.py:27-29`), directly serving Principle #1 ("Two speeds, one tool", `PRODUCT.md:119-121`).
- **Size & files touched:** **S (<= 1 day)** — `src/suravidl_engine/settings.py:12-30`, `src/suravidl_engine/web/index.html:118-123`, `src/suravidl_engine/web/app.js:1560-1580`, `android/app/src/main/java/com/suravidl/app/MainActivity.kt:754-764`.
- **Risk:** Accidentally queueing a 500-item playlist on share; mitigated because `jobs.py` already forces `noplaylist=True, playlist_items="1"` unless `playlist_items` is explicitly passed (`src/suravidl_engine/jobs.py:1698-1704`).

### 2. Rich Android Foreground Notifications (Progress Bar, Speed/ETA & Cancel)
- **What it is:** Upgrade the Android foreground notification to show active download percentage, transfer speed, ETA, and an inline Cancel button.
- **Why it earns its place:** YTDLnis and Seal keep users informed from the notification shade; `EngineService.kt` currently polls `/jobs` only to count active rows (`android/app/src/main/java/com/suravidl/app/EngineService.kt:312-320`) and discards `downloaded_bytes`, `total_bytes`, `speed`, and `eta` already returned by `jobs` (`src/suravidl_engine/jobs.py:54-57`).
- **Size & files touched:** **S (<= 1 day)** — `android/app/src/main/java/com/suravidl/app/EngineService.kt:310-366`.
- **Risk:** `EngineService.kt:339-345` documents a past `ForegroundServiceDidNotStartInTimeException` crash; `startInForeground()` (`EngineService.kt:367`) must stay minimal, applying progress bars and `PendingIntent` actions only in subsequent `updateCount()` calls with a try/catch fallback.

### 3. Per-Download Title & Artist/Uploader Metadata Override
- **What it is:** Let users edit the probed title and artist/uploader on the probe card before queueing so both the saved filename and embedded container tags use the cleaned values.
- **Why it earns its place:** Shipped by YTDLnis and Parabolic; currently `embed_metadata` (`src/suravidl_engine/settings.py:34`, `src/suravidl_engine/download_opts.py:788-790`) embeds raw site titles verbatim and `--postprocessor-args` is security-blocked (`src/suravidl_engine/download_opts.py:414-415`), leaving music/lecture archivers unable to strip title junk inside suravidl.
- **Size & files touched:** **M (<= 1 week)** — `src/suravidl_engine/api.py:47-62`, `src/suravidl_engine/jobs.py:40-68` & `1690-1735`, `src/suravidl_engine/download_opts.py:788-791`, `src/suravidl_engine/web/index.html:173-178`, `src/suravidl_engine/web/app.js`.
- **Risk:** Custom titles must not clobber the `[%(id)s]` dedupe tag in `DEFAULT_TEMPLATE` (`src/suravidl_engine/download_opts.py:451-476`) or `_path_belongs_to` remux checks (`src/suravidl_engine/jobs.py:1732-1734`), and inputs must collapse behind an edit icon on `#probeTitle` (`src/suravidl_engine/web/index.html:175`) to preserve the glass aesthetic.

### 4. Split by Chapters (and SponsorBlock Segments) into Separate Files
- **What it is:** A toggle in the probed chapters row that splits a multi-chapter video or album into individual numbered files per chapter in a single download pass.
- **Why it earns its place:** Shipped by YTDLnis; suravidl currently only clips a single `start-end` range (`src/suravidl_engine/download_opts.py:712-722`, `src/suravidl_engine/web/index.html:230-234`) or marks/removes SponsorBlock chapters (`src/suravidl_engine/download_opts.py:776-786`), forcing users saving full albums to manually queue N separate clips.
- **Size & files touched:** **M (<= 1 week)** — `src/suravidl_engine/settings.py:41` & `111`, `src/suravidl_engine/download_opts.py:707-723` (`FFmpegSplitChapters`), `src/suravidl_engine/jobs.py:501-508` (`files` / `partials` columns), `src/suravidl_engine/web/index.html:230-234`, `src/suravidl_engine/web/app.js`.
- **Risk:** Because user `-o/--paths` are blocked (`src/suravidl_engine/download_opts.py:391-394`), the engine-owned chapter `outtmpl` must sanitize chapter titles into `download_dir` and record all child paths in `jobs.files` (`src/suravidl_engine/jobs.py:501`) so storage wipe and UI playback track every split file.

### 5. Local `.txt` / `.m3u` Link-List Import in Batch Tab
- **What it is:** A "Load `.txt` file" button in the Batch subpanel that reads newline-separated URLs from a local file into the batch checker.
- **Why it earns its place:** Shipped by YTDLnis; because `--batch-file` is denied in `DENIED_RAW_FLAGS` (`src/suravidl_engine/download_opts.py:388`, `430-431`) so the engine owns the job model, a client-side file reader in `#subBatch` (`src/suravidl_engine/web/index.html:369-382`) feeding `/jobs/batch` (`src/suravidl_engine/api.py:1145-1175`) safely closes this gap.
- **Size & files touched:** **S (<= 1 day)** — `src/suravidl_engine/web/index.html:369-382`, `src/suravidl_engine/web/app.js:6428-6440`, `src/suravidl_engine/api.py:1145-1175`, `android/app/src/main/java/com/suravidl/app/MainActivity.kt` (`onShowFileChooser`).
- **Risk:** Android WebView `<input type="file">` requires explicit `WebChromeClient` handling, and imports must enforce chunking well below `MAX_QUEUE = 500` (`src/suravidl_engine/jobs.py:34`).

### 6. Interactive Per-Item Selection & Preset Overrides in Probed Playlists
- **What it is:** Clickable playlist entry rows on the probe card to toggle items and assign per-item presets, complementing the `1-10,15` text input.
- **Why it earns its place:** Shipped by YTDLnis; `probe.py` already extracts `entries` with `index`, `id`, `title`, `url`, and `duration` (`src/suravidl_engine/probe.py:66-85`), and fanning customized entries into `/jobs/batch` (`src/suravidl_engine/api.py:1145-1175`) unlocks per-video pause/resume and mixed audio/video picks from one playlist probe.
- **Size & files touched:** **M (<= 1 week)** — `src/suravidl_engine/web/index.html:235-240`, `src/suravidl_engine/web/app.js`, `src/suravidl_engine/probe.py:66-85`, `src/suravidl_engine/api.py:1145-1175`.
- **Risk:** Rendering 100 glass rows (`MAX_ENTRIES` at `src/suravidl_engine/probe.py:8, 54`) with heavy controls can lag Android WebView; keep rows lightweight and only split into individual jobs when per-item overrides differ.

### 7. Deferred Queue Start ("Start After Time" While App Is Open)
- **What it is:** An optional "Start after HH:MM" delay when queueing jobs so large batches wait in `queued` state until off-peak hours.
- **Why it earns its place:** Shipped by YTDLnis; `JobManager` already decouples `_pending` deque from `_workers` (`src/suravidl_engine/jobs.py:439-442`) and persists SQLite rows across restarts (`src/suravidl_engine/jobs.py:40-68`, `458`).
- **Size & files touched:** **M (<= 1 week)** — `src/suravidl_engine/jobs.py:40-70` & `1386-1430`, `src/suravidl_engine/api.py:47-62`, `src/suravidl_engine/web/index.html:408-425`, `src/suravidl_engine/web/app.js`.
- **Risk:** Android kills idle background processes; must follow `follows.py`'s honest rule ("runs while the app does" or on next open, `src/suravidl_engine/follows.py:17-19`) rather than requesting invasive exact-alarm permissions.

### 8. Uncompressed `audio-wav` Extraction Preset
- **What it is:** Add `WAV (uncompressed)` to `#audioMore` (`src/suravidl_engine/web/index.html:205-211`) for video editors importing audio into NLEs.
- **Why it earns its place:** Shipped by Parabolic; `FORMAT_INTENTS` (`src/suravidl_engine/jobs.py:230-274`) covers native/m4a/mp3/flac/opus, and adding `preferredcodec: "wav"` is a 6-line win using existing bundled ffmpeg (`PRODUCT.md:62-63`).
- **Size & files touched:** **S (<= 1 hour)** — `src/suravidl_engine/jobs.py:230-274`, `src/suravidl_engine/web/index.html:205-211`, `src/suravidl_engine/web/app.js`.
- **Risk:** WAV containers do not reliably embed cover art (`embed_thumbnail` at `src/suravidl_engine/download_opts.py:791-795`); emit a `notices` caveat (`src/suravidl_engine/download_opts.py:733`) when combined with `embed_thumbnail`.

---

## 3. What NOT to Add (Competitor Traps)

- **External downloaders (`aria2c` in Seal) or unrestricted `--exec` / command templates (Seal/YTDLnis):** Rightly forbidden by `DENIED_RAW_FLAGS` (`src/suravidl_engine/download_opts.py:382-386`, `419-429`). Spawning external binaries breaks loopback sandbox guarantees (`src/suravidl_engine/api.py:575-590`), ruins pause/resume byte accounting (`src/suravidl_engine/jobs.py:54-61`), and is redundant given built-in `fragments` (`1..16` at `src/suravidl_engine/settings.py:47`, `src/suravidl_engine/download_opts.py:804-806`).
- **Cloud storage uploads (YTDLnis Nextcloud sync):** Violates Principle #3 ("On your machine, no middleman", `PRODUCT.md:124-126`) and creates a remote credential store alongside sensitive cookies (`PRODUCT.md:46-48`).
- **In-app search queries (YTDLnis search-in-batch):** Turns a local file downloader (`PRODUCT.md:26-30`) into a scraper frontend prone to rate-limits and UI bloat.
- **Always-on Android background polling daemons / two-way deletion sync (YTDLnis observe & sync):** Explicitly rejected in `follows.py` (`src/suravidl_engine/follows.py:17-19`) to avoid battery drain and OS background-service kills; auto-deleting local files violates user ownership.
- **Hosted relay instances (cobalt model):** Defeats local-first privacy (`PRODUCT.md:42-45`) and breaks residential IP/cookie-authenticated downloads (`src/suravidl_engine/settings.py:21-25`).

---

## 4. Ship One Thing This Week

**Ship #1: One-Tap Quick Download on Share & Paste.**
**Definition of Done:** Adding a "Download now" button next to `#probeBtn` (`src/suravidl_engine/web/index.html:122`) and a `quick_share` setting (`src/suravidl_engine/settings.py:12-30`) allows a pasted link or Android `ACTION_SEND` share (`android/app/src/main/java/com/suravidl/app/MainActivity.kt:754-764`) to immediately enqueue a single-video job via `POST /jobs` (`src/suravidl_engine/api.py:1065-1115`) using `default_preset` (`src/suravidl_engine/settings.py:27`) and switch straight to `#panel-queue` (`src/suravidl_engine/web/index.html:408`), verified by an end-to-end test confirming one-tap queueing without a prior `/probe` call.

---

## 5. Summary

- **Position:** suravidl already leads Parabolic, Seal, YTDLnis, and cobalt in cross-platform architecture (`src/suravidl_engine/api.py:567-590`), browser/in-app stream sniffing + XOR HLS decryption (`src/suravidl_engine/jobs.py:1740-1750`), and TV/QuickTime-compatible output (`src/suravidl_engine/jobs.py:275-295`).
- **Key gaps:** It trails YTDLnis/Seal on Android share-to-download speed (`MainActivity.kt:754-764`), live notification progress (`EngineService.kt:322-336`), chapter splitting (`download_opts.py:712-722`), and metadata tag editing (`download_opts.py:788-790`).
- **Top priorities:** Ship **One-Tap Quick Download (#1)** and **Rich Android Notifications (#2)** first (both S-sized), followed by **Title/Artist Overrides (#3)** and **Chapter Splitting (#4)** (both M-sized).
- **Guardrails:** Refuse external downloaders (`aria2c`), `--exec` templates (`download_opts.py:382-386`), cloud uploads, in-app search, and fake Android background daemons (`follows.py:17-19`) to keep the local-first, single-engine core fast and auditable.
