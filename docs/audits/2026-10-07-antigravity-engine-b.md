# Audit Report: suravidl Engine Sweep (B)

- **Target commit**: `bb971de` (tag: `v0.45.16`, tip of `main`)
- **Scope**: `src/suravidl_engine/` (excluding `extract.py`'s `StreamCopyFixPP` internals and its dedicated unit tests)
- **Focus**: Job lifecycle, queue management, options/postprocessor assembly, updater & port ladder, API surface, error capture, security/data-loss guarantees
- **Audit Date**: 2026-10-08

---

## 1. Executive Summary

This independent audit evaluated the engine tier of `suravidl` against the core tenets defined in `DESIGN.md` and `PRODUCT.md`: *"Never lose user data"*, *"Honest logs"*, *"Outbound-only"*, and *"Secrets never in logs"*.

The audit identified **11 confirmed findings** across job execution, persistence, sidecar management, process lifecycle, error handling, and release updates. No padding was applied. The most urgent issues concern:
1. **Silent data loss** when deleting a download job whose stem matches user-created documents or image assets.
2. **Data corruption** during repeated job resumption where duplicate worker processes write concurrently to the same `.part` file.
3. **Directory desynchronization** where changing the settings download folder causes resumed/queued jobs to re-download from zero and abandon partial files.
4. **False success reporting** where empty or completely failed playlists transition to `completed`.

---

## 2. Findings Summary by Severity

| Severity | Count | Summary |
|---|---|---|
| **CRITICAL** | 1 | Unsafe generic sidecar deletion unlinks user files sharing the download stem (`.json`, `.jpg`, `.png`, `.webp`) |
| **HIGH** | 3 | Resume leaves job in `paused` enabling duplicate concurrent writes; `_execute` ignores per-job `download_dir`; Failed playlists report `completed` with `files=None` |
| **MEDIUM** | 6 | `_requeue` strips partials stranding disk bytes; `overrides` cannot be cleared on retry; Immediate status mutation in `cancel()` races with `delete_job`; `logcap.py` leaks credentials via `GET /logs`; `bindable()` lacks `SO_REUSEADDR` exhausting port ladder; In-flight updater cancellation raises `PermissionError` on Windows |
| **LOW** | 1 | Hardcoded `quiet: True` and `no_warnings: True` suppress ffmpeg diagnostic context |

---

## 3. Detailed Audit Findings

### Finding 1: Unsafe generic sidecar purge unlinks user files sharing media stem
- **Severity**: CRITICAL
- **Evidence**: `src/suravidl_engine/jobs.py:725-727`, `760-763`, `854`
```python
725:    SIDECAR_SUFFIXES = (".info.json", ".description", ".annotations.xml",
726:                        ".jpg", ".jpeg", ".png", ".webp", ".vtt", ".srt",
727:                        ".ass", ".lrc", ".json", ".live_chat.json")
...
760:    def _sidecars_for(self, path: Path) -> list[Path]:
761:        out: list[Path] = []
762:        for suffix in self.SIDECAR_SUFFIXES:
763:            sidecar = path.with_name(path.stem + suffix)
...
854:                    p.unlink()
```
- **What**: When a user deletes a completed job (via `delete_job` or UI trash button), `_sidecars_for()` generates candidate paths using `path.stem + suffix`. The suffix list contains broad extensions: `.json`, `.jpg`, `.jpeg`, `.png`, and `.webp`. Any file in the download directory matching `path.stem + suffix` is deleted unconditionally without checking whether it was created by the engine.
- **Why it matters (Real failing scenario)**:
  1. A user downloads `presentation.mp4`.
  2. The user has existing files in that folder: `presentation.json` (metadata/notes), `presentation.png` (slides/diagrams), or `presentation.jpg` (cover art).
  3. Or a user downloads `data.mp4` into a working folder where `data.json` exists.
  4. The user clicks "Delete download" (trash icon) in `suravidl`.
  5. `delete_job()` iterates through `_sidecars_for()` and calls `p.unlink()` on `presentation.json` and `presentation.png`.
  6. The user's pre-existing, unrelated personal files are permanently deleted. This violates `DESIGN.md`'s primary rule: *"Never lose user data. A tool that deletes the wrong file once has lost the user's trust forever."*
- **Suggested fix**: Only delete sidecars that were explicitly recorded in `job["files"]` during execution, or restrict sidecar deletion to unambiguous engine-specific patterns (e.g. `.info.json`, `.live_chat.json`, `.description`) while avoiding generic `.json`, `.png`, `.jpg` unless tracked at download time.

---

### Finding 2: `resume()` leaves source job in `paused` status, enabling concurrent download corruption
- **Severity**: HIGH
- **Evidence**: `src/suravidl_engine/jobs.py:644-647`, `693-700`
```python
644:    def resume(self, job_id: str) -> dict:
645:        """Continue a paused job: a new row that reuses the partial file."""
646:        src = self.get(job_id)
647:        if src["status"] != "paused":
...
693:        with self._lock:
694:            live = self._jobs.get(src["id"])
695:            if live is not None:
696:                live["filepath"] = None
697:                live["partials"] = None
698:                live["files"] = None
699:        if live is not None:
700:            self._save(live)
```
- **What**: When `resume()` is called on a paused job, it calls `_requeue(src)`. In `_requeue`, `live["filepath"]`, `live["partials"]`, and `live["files"]` are set to `None`, but `live["status"]` is never updated. It remains `"paused"`.
- **Why it matters (Real failing scenario)**:
  1. Job `J1` is paused. Its status is `"paused"`.
  2. A client calls `POST /jobs/{J1}/resume`. A new queued job `J2` is created pointing to the same URL and output path.
  3. Due to UI double-click, network retry, or a mobile client reconnecting, `POST /jobs/{J1}/resume` is called a second time.
  4. Because `J1` status is still `"paused"`, the second call succeeds and creates job `J3`.
  5. Both `J2` and `J3` enter the worker execution queue.
  6. If worker threads run them concurrently (or sequentially with overlapping locks), two separate yt-dlp instances write and append to the exact same `.part` file simultaneously, corrupting the downloaded stream.
- **Suggested fix**: In `resume()` / `_requeue()`, atomically transition `src["status"]` to a terminal or non-resumable state (such as `"resumed"` or `"superseded"`) inside `with self._lock:` before returning.

---

### Finding 3: `_execute()` ignores per-job `download_dir` and hardcodes `self.download_dir`
- **Severity**: HIGH
- **Evidence**: `src/suravidl_engine/jobs.py:1042`, `1050-1052`
```python
1042:            "outtmpl": str(self.download_dir / "%(title).100B.%(ext)s"),
...
1050:        if self._download_opts:
1051:            settings_opts = dict(self._download_opts(
1052:                self.download_dir, raw_args=job.get("raw_args"),
```
- **What**: `create()` deliberately records `"download_dir": str(self.download_dir)` on the job dict so that downloads are tied to the directory active at creation time. However, when the job is executed in `_execute()`, `outtmpl` and `_download_opts` strictly use `self.download_dir` instead of `Path(job.get("download_dir") or self.download_dir)`.
- **Why it matters (Real failing scenario)**:
  1. A user sets Download Folder to `Folder A` and starts downloading a 10 GB video.
  2. The user pauses the job at 5 GB (`Folder A/video.mp4.part` exists).
  3. The user changes Settings -> Download Folder to `Folder B` for subsequent downloads.
  4. The user resumes the paused job.
  5. `_execute()` runs with `self.download_dir = Path("Folder B")`.
  6. yt-dlp looks for `Folder B/video.mp4.part`, finds nothing, and starts downloading from byte 0 into `Folder B`.
  7. The 5 GB partial file in `Folder A` is permanently abandoned on disk, wasting bandwidth and disk space.
- **Suggested fix**: Use `target_dir = Path(job.get("download_dir") or self.download_dir)` inside `_execute()` for `outtmpl` and `_download_opts`.

---

### Finding 4: Empty or completely failed playlists report `status="completed"`
- **Severity**: HIGH
- **Evidence**: `src/suravidl_engine/jobs.py:1112-1130`, `1157`
```python
1112:            if (info or {}).get("_type") == "playlist":
1113:                entries = [e for e in (info.get("entries") or []) if e]
1114:                job["title"] = info.get("title") or "playlist"
1115:                job["filepath"] = str(self.download_dir)
...
1128:                job["files"] = made or None
...
1157:                job["status"] = "completed"
```
- **What**: For single-item downloads, `jobs.py:1138` checks `if not job["filepath"]: raise RuntimeError(...)` to guarantee that missing files report as errors. For playlists, however, `job["filepath"]` is unconditionally set to `str(self.download_dir)`. If a playlist is empty, or if all videos within the playlist fail to download (e.g., all entries are private, geo-blocked, or deleted), `made` remains empty, `job["files"]` is `None`, and the execution branch proceeds straight to `job["status"] = "completed"`.
- **Why it matters (Real failing scenario)**:
  1. A user pastes a playlist URL where all items are unplayable or deleted.
  2. yt-dlp finishes extraction without writing any media files.
  3. `suravidl` marks the job as `completed` with a green checkmark in the UI.
  4. The user clicks "Open folder" or expects the files to exist, but zero files were downloaded. The engine falsely reports success on a total failure.
- **Suggested fix**: In the playlist branch, if `not made` and `job.get("playlist_count", 0) > 0` (or `len(entries) == 0`), raise `RuntimeError("No playlist entries were successfully downloaded")` so the job transitions to `status="error"` with an honest failure message.

---

### Finding 5: `_requeue` strips partials from source job while `create()` initializes `partials=None`
- **Severity**: MEDIUM
- **Evidence**: `src/suravidl_engine/jobs.py:590`, `681-700`
```python
590:            "filepath": None,
...
696:                live["filepath"] = None
697:                live["partials"] = None
698:                live["files"] = None
```
- **What**: When `_requeue()` is invoked (on resume or retry), it wipes `partials`, `filepath`, and `files` from the old row (`live["partials"] = None`) so trashing the old row does not delete the files. However, the successor job is created via `self.create(...)`, which initializes `filepath=None` and does not set `partials`. The successor does not inherit the partial file path until yt-dlp's progress hook fires.
- **Why it matters (Real failing scenario)**:
  1. A 4 GB download is paused or interrupted. `job["partials"]` points to `file.part`.
  2. The user clicks "Resume". A new job `J2` is queued, and `J1["partials"]` is set to `None`.
  3. Before `J2` begins downloading (e.g. while `J2` is waiting in queue behind another job, or during metadata extraction), the user decides to cancel and delete `J2`.
  4. `delete_job(J2)` checks `_job_file_targets(J2)`. Because `J2["partials"]` is `None` and `J2["files"]` is `None`, `targets` is empty.
  5. The multi-gigabyte `.part` file remains on disk forever, unreferenced by any job record.
- **Suggested fix**: Pass `partials=src.get("partials")` from the old job to the successor job in `_requeue()`, so the successor maintains ownership of the in-flight files immediately upon queueing.

---

### Finding 6: `_requeue` merges `patch.overrides` over `src.overrides` without reset path
- **Severity**: MEDIUM
- **Evidence**: `src/suravidl_engine/jobs.py:672-674`, `src/suravidl_engine/api.py:1292`
```python
672:        patch = dict(patch or {})
673:        overrides = {**(src.get("overrides") or {}),
674:                     **(patch.get("overrides") or {})} or None
```
- **What**: In `_requeue()`, `overrides` is computed by merging `patch.get("overrides")` on top of `src.get("overrides")`. There is no mechanism to clear an override that was set on the original job.
- **Why it matters (Real failing scenario)**:
  1. A user runs a job with an override, for example `merge_output_format: "mkv"`, or a custom subtitle language.
  2. The download fails due to format muxing issues.
  3. The user clicks "Edit & Retry" and selects a standard MP4 preset or clears their custom overrides.
  4. Because `{**src["overrides"], **patch["overrides"]}` retains all keys from `src`, the failed override (`merge_output_format: "mkv"`) persists into the retried job.
  5. Passing `{"overrides": {}}` in the retry request cannot clear the settings because `{**src, **{}}` equals `src`.
- **Suggested fix**: If `patch` explicitly provides `"overrides"`, allow it to replace `src["overrides"]`, or allow sentinel `None`/`null` values in `patch["overrides"]` to delete specific keys.

---

### Finding 7: Immediate status mutation in `cancel()` races with `delete_job`
- **Severity**: MEDIUM
- **Evidence**: `src/suravidl_engine/jobs.py:623`, `844-846`
```python
623:            job["status"] = "cancelled"  # queued jobs never start; running see below
...
844:        status = job.get("status")
845:        if status in ("queued", "downloading", "merging"):
846:            raise ValueError("cancel this download before deleting it")
```
- **What**: Cancellation in `jobs.py` is cooperative: worker threads check `_stop_requested(job)` on the next progress hook. However, `cancel()` mutates `job["status"]` to `"cancelled"` synchronously before the worker thread stops. `delete_job()` only guards against `status in ("queued", "downloading", "merging")`.
- **Why it matters (Real failing scenario)**:
  1. A download is actively receiving data in the worker thread.
  2. The user cancels the job and immediately clicks delete (or an automated script/UI calls `POST /jobs/{id}/cancel` followed immediately by `DELETE /jobs/{id}`).
  3. `delete_job()` observes `status == "cancelled"` and immediately begins unlinking files in `_job_file_targets(job)`.
  4. On Windows: The `.part` file is locked by the active download thread. `p.unlink()` raises `PermissionError` (swallowed by `except OSError: pass`). The file remains locked on disk while the database record is deleted.
  5. On POSIX: The `.part` file is unlinked while the worker thread still holds an open file descriptor. The worker continues writing bytes into an unlinked inode until the hook fires, or ffmpeg crashes with unexpected file errors.
- **Suggested fix**: Introduce a transition state (e.g. `"cancelling"`), or use a threading event / worker join mechanism so `delete_job()` blocks until the worker thread has exited before unlinking files.

---

### Finding 8: `logcap.py` captures raw logs without secret scrubbing, exposing tokens via `GET /logs`
- **Severity**: MEDIUM
- **Evidence**: `src/suravidl_engine/logcap.py:21-32`, `src/suravidl_engine/api.py:1120-1123`
```python
21:def _push(msg: object) -> None:
...
27:    for raw in text.splitlines() or [""]:
28:        line = raw.rstrip()
...
32:            _LINES.append(line)
...
1120:    @app.get("/logs")
1121:    def get_logs(_mgr: JobManager = Depends(require_auth)):
1122:        from . import logcap
1123:        return {"lines": logcap.lines(), "verbose": bool(settings.get()["verbose"])}
```
- **What**: In `auth.py`, `scrub_secrets()` is carefully defined and applied to job errors, probes, and persisted cookies to strip sensitive query parameters (`token`, `auth`, `sig`, `key`, `hdnts`, `policy`). However, `logcap.py:_push()` receives raw yt-dlp logs directly and appends them to `_LINES` without calling `auth.scrub_secrets()`.
- **Why it matters (Real failing scenario)**:
  1. A user enables the "Verbose logs" switch in Settings to troubleshoot a failing download.
  2. yt-dlp logs verbose HTTP request URLs containing signed tokens, session keys, or API parameters.
  3. The user opens the Log card in the UI or exports the log via `GET /logs` to share with developers or issue trackers.
  4. Raw credentials and signed tokens are exposed in plaintext. This breaches `PRODUCT.md`'s rule: *"Secrets never in logs."*
- **Suggested fix**: Import `scrub_secrets` from `.auth` into `logcap.py` and call `line = scrub_secrets(line)` in `_push()` before appending to `_LINES`.

---

### Finding 9: `bindable()` lacks `SO_REUSEADDR`, causing rapid restarts to exhaust the port ladder
- **Severity**: MEDIUM
- **Evidence**: `src/suravidl_engine/__main__.py:86-93`
```python
86:    def bindable(p: int) -> bool:
87:        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
88:            try:
89:                s.bind(("127.0.0.1", p))
90:                return True
91:            except OSError:
92:                return False
```
- **What**: When checking whether a port on the fixed ladder (8787..8792) is available, `bindable()` creates a socket and attempts `s.bind()`. It does not set `socket.SO_REUSEADDR`.
- **Why it matters (Real failing scenario)**:
  1. The engine process is restarted rapidly (e.g. self-update restart, service restart, or crash restart).
  2. Previous TCP connections remain in `TIME_WAIT` for 60 seconds.
  3. Without `SO_REUSEADDR`, `s.bind(("127.0.0.1", 8787))` fails with `OSError: [Errno 98] Address already in use`.
  4. `find_free_port()` walks the ladder to 8788, 8789, etc. If multiple restarts occur within the 2-MSL window, the 6 rungs of the ladder (8787..8792) are quickly exhausted.
  5. The engine falls back to `s.bind(("127.0.0.1", 0))`, binding to an ephemeral OS port (e.g. 52419).
  6. The browser extension and mobile clients only scan 8787..8792; they cannot discover the engine on an ephemeral port. The UI reports "suravidl isn't running".
- **Suggested fix**: Add `s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)` prior to `s.bind()` inside `bindable()`.

---

### Finding 10: In-flight updater cancellation unlinks open file handle, raising `PermissionError` on Windows
- **Severity**: MEDIUM
- **Evidence**: `src/suravidl_engine/updater.py:317-343`
```python
317:    def cancelled() -> bool:
318:        """The user asked to stop: clean up and end idle, voluntarily."""
319:        if not _DL.get("cancel"):
320:            return False
321:        part.unlink(missing_ok=True)
322:        _set_state(status="idle", name=None, path=None, bytes=0, total=0,
323:                   sha256_ok=None, error=None, cancel=False)
324:        return True
...
329:            with open(part, "wb") as f:
330:                while True:
331:                    if cancelled():
332:                        return update_status()
```
- **What**: During update downloading, `cancelled()` is called inside the chunk loop while `with open(part, "wb") as f:` holds an open write handle on `part`. `cancelled()` immediately invokes `part.unlink(missing_ok=True)`.
- **Why it matters (Real failing scenario)**:
  1. On Windows NTFS, unlinking an open file handle raises `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
  2. `missing_ok=True` only suppresses `FileNotFoundError`, not `PermissionError`.
  3. When a Windows user cancels an update download, `part.unlink()` raises `PermissionError`.
  4. The exception escapes `cancelled()` into `except Exception as e:` in `download_asset()`.
  5. The updater state is marked as `status="failed"` with a raw Windows permission error instead of transitioning gracefully to `status="idle"`.
- **Suggested fix**: In the download loop, have `cancelled()` return a boolean indicating cancellation without unlinking; break from `with open(...)` so the file handle closes, and then unlink `part`.

---

### Finding 11: Hardcoded `quiet: True` and `no_warnings: True` suppress ffmpeg diagnostic context
- **Severity**: LOW
- **Evidence**: `src/suravidl_engine/jobs.py:1040-1041`
```python
1040:            "quiet": True,
1041:            "no_warnings": True,
```
- **What**: In `jobs.py:_execute()`, yt-dlp execution options hardcode `"quiet": True` and `"no_warnings": True`.
- **Why it matters (Real failing scenario)**:
  1. When ffmpeg postprocessors encounter muxing anomalies, audio/video synchronization drift, or unmapped streams, ffmpeg emits warnings to stderr.
  2. Because `no_warnings: True` is hardcoded, yt-dlp suppresses all warning logging.
  3. When a postprocessor fails or falls back to an unusable state, yt-dlp raises generic `PostProcessingError("Conversion failed!")` with no diagnostic trail.
  4. This directly amplifies postprocessing debugging churn by concealing whether ffmpeg failed due to missing codecs, container incompatibility, or stream corruption.
- **Suggested fix**: When `settings.get("verbose")` is enabled, set `"no_warnings": False` and route warnings through `CaptureLogger`.

---

## 4. Refuted / Cannot Stand Behind Hypotheses

During the audit, several hypotheses were evaluated and refuted based on code evidence:

1. **Hypothesis: `extract_info` is called without stream-fix attachment**
   - *Status*: **Refuted**.
   - *Evidence*: `jobs.py` routes all download extraction through `extract.py:extract_info(..., download=True)`. In `extract.py`, `_attach_stream_copy_fix()` is invoked on every YoutubeDL instance when `download=True`. Probe paths (`probe.py`) use `download=False`, which correctly omits postprocessors.
2. **Hypothesis: Windows updater spawn regressed to use `DETACHED_PROCESS`**
   - *Status*: **Refuted**.
   - *Evidence*: Inspected `src/suravidl_engine/__main__.py:1312-1322`. The spawn call uses `creationflags=_CREATE_NO_WINDOW` alone with `close_fds=True`. Commit `8377b13` / v0.45.10 correctly eliminated `DETACHED_PROCESS`.
3. **Hypothesis: Release manifest role/artifact mismatch between workflow and updater**
   - *Status*: **Refuted**.
   - *Evidence*: Inspected `.github/workflows/release.yml`, `scripts/generate_release_manifest.py`, `scripts/refresh_update_manifest.py`, and `updater.py`. Roles (`windows-setup`, `windows-standalone`, `macos-dmg`, `macos-zip`, `android-apk`) and platforms (`windows`, `macos`, `android`) match precisely.
4. **Hypothesis: Desktop loopback authentication bypass vulnerability**
   - *Status*: **Refuted / Documented Rationale Holds**.
   - *Evidence*: `DESIGN.md` explicitly documents the threat model: loopback (`127.0.0.1`) on single-user desktop systems is trusted; Android isolates loopback via `page_key`. The code enforces tokens when set and validates origins.

---

## 5. Ranked Top 5 Findings

1. **Finding 1 (CRITICAL) — Unsafe sidecar purge deletes unrelated user files**: Permanent, irreversible data loss of user-owned `.json`, `.png`, and `.jpg` files sharing a download stem.
2. **Finding 2 (HIGH) — Resume leaves job in `paused`, causing concurrent download corruption**: Double-resuming creates competing worker processes that corrupt `.part` files.
3. **Finding 3 (HIGH) — `_execute` ignores per-job `download_dir`**: Resuming or executing queued jobs after changing the download folder abandons multi-gigabyte partial downloads and restarts from zero in the wrong folder.
4. **Finding 4 (HIGH) — Failed/empty playlists report `completed`**: Complete failure to download any playlist items is falsely reported to the user as a successful completion.
5. **Finding 7 (MEDIUM) — Cooperative cancellation races with `delete_job`**: Immediate status change to `"cancelled"` allows file unlinking while worker threads are still actively writing.
