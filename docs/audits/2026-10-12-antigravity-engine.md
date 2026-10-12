# Engine Security & Correctness Audit Report: suravidl

**Target**: `suravidl_engine` (`src/suravidl_engine/`)  
**Commit**: `499ec14` (tag: `v0.46.9`, "the cut")  
**Scope**: `jobs.py`, `api.py`, `download_opts.py`, `follows.py`, `updater.py`, `ytdlp_update.py`, `cut.py`, `auth.py`, `diagnostics.py`, `settings.py`, `extract.py`, `logcap.py`, `classify.py`, `handoff.py`, `macos_swap.sh`.  
**Rubric**: House laws from `DESIGN.md` & `PRODUCT.md` ((1) honesty: errors name cause, caveats ride as notes; (2) watch list laws: start-from-now, nothing-grabbed-twice, polite/bounded checks; (3) live recordings: disk stat is truth, watchdog exempts lives; (4) DB columns align every boot without SCHEMA_VERSION gate; (5) redaction happens engine-side; (6) loopback trust model).

---

## Executive Summary

This deep audit evaluated the core engine tier of `suravidl` at version `v0.46.9`. 12 verified findings were confirmed directly from source code:
- **P0 (Critical)**: 1 finding (concurrent resume/requeue race corrupting partial downloads).
- **P1 (High)**: 4 findings (DB `note` column omission losing caveats across reboots; `cut_job` permission refusal on changed download dir; credential leak in proxy diagnostics; raw args whitelist bypass for external downloader arguments).
- **P2 (Medium)**: 4 findings (Authorization/cookie leak in verbose logcap; updater prerelease & 4-part version parse defects; unvalidated `out_dir` boundary in `cut_job`; `_stat_size` ignoring `.part` files on live recordings).
- **P3 (Low)**: 3 findings (unauthenticated host path leakage on `/health`; `macos_swap.sh` TOCTOU placeholder deletion & stale executable name; `files_clear` deleting partials under active workers).

---

## Detailed Audit Findings

### Finding 1: `note` column missing from SQLite schema and per-boot alignment, permanently losing caveats and local cut attribution across reboots
- **Severity**: P1
- **Evidence**:
  - `src/suravidl_engine/jobs.py:37-62` (`_SCHEMA` definition lacks `note TEXT`)
  - `src/suravidl_engine/jobs.py:393-441` (`_init_db` aligns all legacy columns on boot, but omits `note`)
  - `src/suravidl_engine/jobs.py:552-570` (`_save` SQL `INSERT ... ON CONFLICT DO UPDATE` omits `note`)
  - `src/suravidl_engine/jobs.py:500-544` (`_row_to_job` row decoder omits `note`)
  - `src/suravidl_engine/jobs.py:721-722` (`add_take` attaches `job["note"] = note` in memory)
  - `src/suravidl_engine/jobs.py:1393, 1416, 1430, 1448, 1470` (`_execute` sets `job["note"]` on caveats and skips)
- **What**: In `v0.45.29` ("the note") and `v0.46.9` ("the cut"), the engine introduced the `note` attribute on jobs so that caveats ride visibly on job cards ("subtitles could not be fetched", "already in the archive — skipped", "already on disk — nothing was fetched", and "cut locally at the nearest keyframes"). However, `note` was only implemented in in-memory dicts. It was never added to `_SCHEMA`, never added to `_init_db`'s per-boot `ALTER TABLE` alignment list, never included in `_save()`, and never restored in `_row_to_job()`.
- **Why it matters**: 
  1. On every engine reboot, all caveats, skip reasons, and cut take notes are permanently wiped from the database. A job that completed with skipped subtitles or an existing-disk skip reloads with `note: null`, hiding from the user why subtitles or new streams are absent. This directly violates House Law 1 (*"honesty — a successful job may never hide what it couldn't do; errors name their cause; caveats ride as notes"*).
  2. House Law 4 mandates: *"DB columns align every boot — never gated behind SCHEMA_VERSION"*. If a future commit adds `note` to `_save()` without this boot alignment, every existing user database will crash on boot with `sqlite3.OperationalError: table jobs has no column named note` (the exact defect that occurred with `replaced_by` in `v0.45.26`).
- **Fix-direction**:
  1. Add `note TEXT` to `_SCHEMA` in `jobs.py:62`.
  2. In `_init_db()` (`jobs.py:441`), add:
     ```python
     if "note" not in cols:
         self._con.execute("ALTER TABLE jobs ADD COLUMN note TEXT")
     ```
  3. Include `note=excluded.note` and `job.get("note")` in `_save()`.
  4. Decode `job["note"] = row["note"]` in `_row_to_job()`.

---

### Finding 2: Unsynchronized `_requeue` and unawaited worker in `resume()` enable concurrent writes to identical `.part` files
- **Severity**: P0
- **Evidence**:
  - `src/suravidl_engine/jobs.py:774-780` (`pause`)
  - `src/suravidl_engine/jobs.py:782-787` (`resume`)
  - `src/suravidl_engine/jobs.py:810-853` (`_requeue`)
  - `src/suravidl_engine/jobs.py:1003-1025` (`delete_job` waiting for worker in `_running`)
- **What**: When a job is paused via `pause(job_id)`, `job["status"] = "paused"` is written immediately, but the running worker stops cooperatively at its next hook or poll; the worker thread remains in `self._running` until yt-dlp unwinds. When `resume()` is called:
  1. Unlike `delete_job()`, `resume()` does not check if `src["id"] in self._running` or wait for the existing worker to terminate.
  2. In `_requeue()`, the check `if src.get("replaced_by"):` runs on an unlocked dict snapshot, calls `create()`, and only subsequently locks `self._lock` to assign `live["replaced_by"] = job["id"]`.
- **Why it matters**: If `resume()` is called immediately after `pause()`, or if `resume()` is double-clicked / retried concurrently via the API before the first invocation finishes `create()`:
  - Both calls see `replaced_by == None`, queueing two separate successor jobs pointing to the exact same URL and partial file path.
  - Or, the newly queued successor is picked up by a free worker in `_worker_loop` while the first worker is still in `_execute()`.
  Two concurrent threads then write and append to the identical `.part` file simultaneously, causing irrecoverable byte corruption and defeating the promise of pause/resume.
- **Fix-direction**:
  1. In `resume()`, if `job_id in self._running`, wait with a bounded timeout for the worker to exit before requeueing (matching the pattern in `delete_job`).
  2. Inside `_requeue()`, acquire `self._lock` *before* checking `replaced_by`, and atomically transition `src["status"]` or assign a reservation before releasing the lock or calling `create()`.

---

### Finding 3: `cut_job` passes `None` to `_require_inside()`, breaking local cuts on downloads made before a folder change
- **Severity**: P1
- **Evidence**:
  - `src/suravidl_engine/api.py:1524` (`mgr._require_inside(src, None)`)
  - `src/suravidl_engine/api.py:1461` (`mgr._require_inside(path, job)` in `stream_job`)
  - `src/suravidl_engine/jobs.py:887-911` (`_require_inside`)
- **What**: `_require_inside(path, job)` allows files within either the current download folder (`self.download_dir`) or the folder the job was created under (`job["download_dir"]`). In `GET /jobs/{job_id}/stream` and `POST /jobs/{job_id}/delete`, the job dictionary is passed to `_require_inside(path, job)`. However, in `POST /jobs/{job_id}/cut`, `cut_job` calls `mgr._require_inside(src, None)`, passing `None` instead of `job`.
- **Why it matters**: If a user changes their download directory in Settings, earlier downloads reside in their historical `job["download_dir"]`. While playback (`/stream`) and deletion (`/delete`) continue to work because they pass `job`, clicking "Cut this take" on any such download throws an HTTP 403 Forbidden (*"that file is outside the download folder"*). The player's trim feature is completely broken for historical files across folder updates.
- **Fix-direction**: Change `src/suravidl_engine/api.py:1524` from `mgr._require_inside(src, None)` to `mgr._require_inside(src, job)`.

---

### Finding 4: `redact_settings` and `scrub_inline` fail to redact proxy credentials, leaking passwords into public diagnostics bundles
- **Severity**: P1
- **Evidence**:
  - `src/suravidl_engine/diagnostics.py:24-26` (`_SECRET_KEY = re.compile(r"(?i)(token|secret|password|passwd|api[_-]?key|cookie|authorization|credential|auth)")`)
  - `src/suravidl_engine/diagnostics.py:36-40` (`redact_settings` walking settings dict)
  - `src/suravidl_engine/diagnostics.py:90-93` (`_INLINE_SECRET` regex)
  - `src/suravidl_engine/auth.py:136-139` (`_SECRET_QUERY_RE`)
- **What**: `redact_settings` in `diagnostics.py` matches dictionary keys against `_SECRET_KEY`. The setting `"proxy"` (e.g. `http://user:password@proxy.example.com:8080`) does not match this regex. It falls through to the string handler, which calls `auth.scrub_secrets()`. However, `scrub_secrets` only redacts URL query string arguments (`[?&](token|auth|key)=`). Proxy userinfo (`user:pass@`) is left unaltered. Furthermore, `_INLINE_SECRET` in `diagnostics.py` matches `\b(token|secret|password)\s*[=:]`, which fails on `user:password@host`.
- **Why it matters**: `GET /diagnostics` generates the bug report bundle explicitly meant to be pasted into public bug trackers (`diagnostics.py:135-136`: *"paste this whole block into the bug report — every secret was redacted by the engine itself, not by trust"*). Any user with authenticated HTTP or SOCKS proxies will leak cleartext proxy passwords into public issue threads, violating House Law 5 (*"redaction happens engine-side"*).
- **Fix-direction**:
  1. Add `proxy` to `_SECRET_KEY` in `diagnostics.py` (or redact the userinfo portion via `re.sub(r'://([^:]+):([^@]+)@', r'://\1:[redacted]@', proxy_url)`).
  2. Extend `_SECRET_QUERY_RE` or `_INLINE_SECRET` to sanitize URL authority userinfo in all scrubbed strings.

---

### Finding 5: Raw argument filter omits `--downloader-args` and `--external-downloader-args`, allowing arbitrary child process argument injection
- **Severity**: P1
- **Evidence**:
  - `src/suravidl_engine/download_opts.py:334-368` (`DENIED_RAW_FLAGS`)
  - `src/suravidl_engine/download_opts.py:370-395` (`DENIED_RAW_KEYS`)
  - `src/suravidl_engine/download_opts.py:576-580, 594-596` (`parse_raw_args`)
- **What**: `DENIED_RAW_FLAGS` denies `--postprocessor-args` (`--ppa`), `--downloader`, and `--external-downloader`. However, it fails to deny `--downloader-args` and `--external-downloader-args`. Furthermore, `DENIED_RAW_KEYS` fails to deny `external_downloader_args`.
- **Why it matters**: When raw arguments are enabled in Settings, a job specifying `raw_args='--downloader-args "ffmpeg:-y -filter:v ..."'` passes validation without error. yt-dlp parses this into `{'external_downloader_args': {'ffmpeg': [...]}}`, passing arbitrary command-line arguments directly to child FFmpeg invocations.
- **Fix-direction**:
  1. Add `--downloader-args` and `--external-downloader-args` to `DENIED_RAW_FLAGS` in `download_opts.py:368`.
  2. Add `"external_downloader_args": "--downloader-args"` to `DENIED_RAW_KEYS` in `download_opts.py:395`.

---

### Finding 6: `logcap.py` only scrubs query tokens, exposing HTTP Authorization headers and Cookies in `GET /logs`
- **Severity**: P2
- **Evidence**:
  - `src/suravidl_engine/logcap.py:31-35` (`_push` calling `scrub_secrets`)
  - `src/suravidl_engine/auth.py:136-139` (`_SECRET_QUERY_RE`)
  - `src/suravidl_engine/api.py:1180-1188` (`get_logs`)
- **What**: When the `verbose` setting is enabled, yt-dlp logs verbose HTTP request headers to its logger, including `[debug] Request Headers: {'Authorization': 'Bearer ...', 'Cookie': '...'}`. In `logcap.py`, `_push()` passes each line only through `auth.scrub_secrets()`. Because `scrub_secrets()` exclusively checks URL query parameters (`[?&](token|auth|key)=`), HTTP header values like `Authorization` and `Cookie` are stored verbatim in `_LINES`.
- **Why it matters**: Querying `GET /logs` or viewing the Log card in the web UI exposes active session tokens and cookies. When users export logs to report download issues, session secrets are leaked, breaching House Law 5 (*"redaction happens engine-side; secrets never in logs"*).
- **Fix-direction**: In `logcap.py:_push()`, run log lines through a header redaction regex (matching `Authorization:\s*Bearer\s+\S+` and `Cookie:\s*[^;\r\n]+`) before appending to `_LINES`.

---

### Finding 7: `_parse()` in updater treats all prerelease suffixes identically and truncates 4-part versions, disabling candidate updates
- **Severity**: P2
- **Evidence**:
  - `src/suravidl_engine/updater.py:38-54` (`_parse`)
  - `src/suravidl_engine/updater.py:82` (`check_update`)
- **What**: `_parse(v)` extracts digits from dot-separated chunks up to 3 parts and appends `prerelease = 0 if "-" in v else 1`, returning `tuple(parts[:3]) + (prerelease,)`.
- **Why it matters**:
  1. Any two prereleases with the same major.minor.patch (e.g. `0.46.0-rc1` vs `0.46.0-rc2`) parse to the exact same tuple: `(0, 46, 0, 0)`. Thus, `_parse("0.46.0-rc2") > _parse("0.46.0-rc1")` evaluates to `False`. Users testing release candidate builds are never notified of subsequent release candidates.
  2. Four-part versions (e.g. `0.45.1.1` vs `0.45.1.2`, or yt-dlp calendar versions like `2026.08.19.1`) are truncated to 3 parts, ignoring the fourth sub-patch version entirely.
  3. Pre-releases separated by dots without hyphens (e.g. `0.46.0.dev1`) parse with `prerelease = 1`, incorrectly sorting as equal to the final release.
- **Fix-direction**: Use a standard version parser (such as `packaging.version.Version`) or parse alphanumeric prerelease identifiers into comparable integer/string tuples, and preserve 4-part numeric tuples.

---

### Finding 8: `cut_job` executes ffmpeg cut into unvalidated `out_dir` without boundary verification
- **Severity**: P2
- **Evidence**:
  - `src/suravidl_engine/api.py:1540-1542` (`out_dir = Path(job.get("download_dir") or mgr.download_dir)`)
  - `src/suravidl_engine/cut.py:75-85` (`out = out_dir / clip_name(...)`)
- **What**: In `POST /jobs/{job_id}/cut`, `src` is verified with `_require_inside`, but `out_dir` is taken directly from `job.get("download_dir") or mgr.download_dir` and passed into `cut_file(src, start, end, out_dir)` without calling `mgr._require_inside(out_dir, job)`.
- **Why it matters**: If a job row carries an unverified or corrupted `download_dir` (e.g. from an imported SQLite database or modified row), `cut_file` invokes ffmpeg to output directly into `out_dir`, writing files outside the designated download folder.
- **Fix-direction**: In `api.py:1540`, assert `mgr._require_inside(out_dir, job)` before calling `cut_file()`.

---

### Finding 9: `_stat_size()` ignores `.part` files, reporting `None` for in-progress live stream recordings
- **Severity**: P2
- **Evidence**:
  - `src/suravidl_engine/jobs.py:98-114` (`_stat_size`)
  - `src/suravidl_engine/jobs.py:731, 752` (`get`, `list`)
- **What**: House Law 3 specifies: *"a live recording plays by ffmpeg's rules (disk stat is the truth, watchdog exempts lives)"*. When recording a live stream, yt-dlp delegates downloading to ffmpeg, which emits no progress hook events (`downloaded_bytes` remains 0) while streaming into a `.part` file. In `jobs.py`, `_stat_size()` checks only `path and os.path.isfile(path)` and completed files in `job["files"]`. It never inspects `job.get("partials")` or `.part` / `.ytdl` files.
- **Why it matters**: While a live recording is active, `os.path.isfile(path)` is `False` because the file on disk is named `<path>.part`. Consequently, `_stat_size()` returns `None`, and `GET /jobs` reports `size_bytes: null` throughout the entire recording, violating House Law 3 (*"disk stat is the truth"*).
- **Fix-direction**: In `_stat_size()`, if `path` does not exist, inspect `job.get("partials")` and test `p.with_name(p.name + ".part")` or `p.with_name(p.name + ".ytdl")` to return the real bytes written on disk during active transfers.

---

### Finding 10: `GET /health` is unauthenticated and leaks host download directory path
- **Severity**: P3
- **Evidence**:
  - `src/suravidl_engine/api.py:517-520` (`health`)
- **What**: Out of the 58 engine API routes, only `GET /health` and `GET /` lack `require_auth` or `require_auth_media`. `GET /health` returns:
  `{"ok": True, "version": __version__, "download_dir": str(download_dir)}`.
- **Why it matters**: Any local unauthenticated process or socket client querying the default loopback port learns the user's host OS username and local folder layout (e.g. `/home/alice/Downloads` or `C:\Users\Alice\Downloads`) without presenting an API token.
- **Fix-direction**: Return only `{"ok": True, "version": __version__}` on `GET /health`, omitting `download_dir` from unauthenticated responses.

---

### Finding 11: `macos_swap.sh` directory placeholder removal race and outdated executable resolution in relaunch fallback
- **Severity**: P3
- **Evidence**:
  - `src/suravidl_engine/macos_swap.sh:29-30, 58-63` (`EXEC` resolution and `relaunch`)
  - `src/suravidl_engine/macos_swap.sh:119-121` (`mktemp -d` and `rm -rf "$OLD"`)
- **What**:
  1. In `macos_swap.sh:119-121`, `OLD="$(mktemp -d "$DIR/.suravidl-old.XXXXXX")"` creates a secure directory, which is immediately removed via `rm -rf "$OLD"` prior to `mv "$APP" "$OLD"`. This creates a TOCTOU race where a local process could recreate or symlink `$OLD`.
  2. In `macos_swap.sh:29-30`, `EXEC` is computed from the *old* `$APP` before the new bundle is unpacked. If the update modifies `CFBundleExecutable`, the fallback launcher `INNER="$1/Contents/MacOS/$EXEC"` points to a missing binary if `open -n` fails.
- **Why it matters**: A renamed executable in an update bundle fails the direct-launch fallback, and deleting the mktemp directory prior to moving creates an avoidable filesystem race.
- **Fix-direction**:
  1. Avoid `rm -rf "$OLD"` by creating a unique non-existent destination name or moving into the directory.
  2. In `relaunch()`, re-read `CFBundleExecutable` from `$1/Contents/Info.plist` before executing `$INNER`.

---

### Finding 12: `files_clear` does not verify `_running` workers or paused jobs, unlinking partials under active threads
- **Severity**: P3
- **Evidence**:
  - `src/suravidl_engine/api.py:1235-1248` (`files_clear`)
  - `src/suravidl_engine/jobs.py:347, 1005-1025` (`_running` check in `delete_job`)
- **What**: `POST /files/clear` checks `active = [j for j in mgr.list() if j["status"] in ("queued", "downloading", "merging")]`. If a job was recently paused, its status is `"paused"`, but its worker thread may still be running in `self._running`. Furthermore, `_wipe_dir` unlinks all partials in the download directory, while `mgr.clear_completed()` leaves paused job rows in the database.
- **Why it matters**: Calling `/files/clear` unlinks `.part` files out from under live worker threads that have not finished unwinding, and leaves orphan `"paused"` rows in the queue that point to deleted partial files.
- **Fix-direction**: In `files_clear`, ensure `self._running` is empty (with a bounded wait matching `delete_job`), and purge or reset partial references for paused rows when the folder is wiped.

---

## Ranked Top 5

1. **Finding 2 (P0) — Concurrent resume/requeue race corrupts `.part` files**: Unsynchronized `_requeue` and missing worker liveness checks allow dual workers to write concurrently to the same `.part` file, corrupting downloaded bytes.
2. **Finding 1 (P1) — Missing `note` column in SQLite schema and per-boot alignment**: All caveats, skip reasons, and local cut attributions are permanently lost on engine restart; future schema updates risk bricking databases on boot.
3. **Finding 3 (P1) — `cut_job` passes `None` to `_require_inside()`, breaking local cuts after folder changes**: Historical downloads located in their original download folder are refused with HTTP 403 Forbidden when trimmed via the player's Cut button.
4. **Finding 4 (P1) — Proxy credential leak in `redact_settings` and `scrub_inline` via `GET /diagnostics`**: Cleartext proxy usernames and passwords in `http://user:pass@host` are exposed in public diagnostics bug report exports.
5. **Finding 5 (P1) — Raw arguments denylist omits `--downloader-args` and `--external-downloader-args`**: Bypasses raw argument security filters and enables passing uninspected argv arguments directly into child FFmpeg processes.
