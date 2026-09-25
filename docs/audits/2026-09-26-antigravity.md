# Independent audit — 2026-09-26 (Google Antigravity)

**What this is.** The v0.21.1 tree was handed to an *independent* agent
(Google Antigravity CLI, `agy 1.2.10`, run headless) and asked to find real
defects, with the source mounted read-only in a throwaway `git worktree`.
It wrote `AUDIT-AGY.md` (40 KB, 16 findings, `DEF-01`…`DEF-16`).

**What was done with it.** Nothing was taken on trust. Each finding was then
reproduced here — against the live engine (booted with an ephemeral `HOME`
and token), against the test fixtures, or by reading the exact code path —
and only confirmed findings were fixed. That verification is the point: an
audit is evidence, not truth. **All 16 held.** One (`DEF-02`) had an
overstated blast radius, which is recorded below rather than quietly fixed.

**Where the regressions live.** `tests/test_audit2_fixes.py` (20 tests) —
each test was written first, run against the unfixed tree (all failed), and
then made green by the fix.

| # | Finding | Verdict | Fix (v0.21.2) |
|---|---------|---------|---------------|
| 01 | `delete_job`'s empty-folder cleanup compares an unresolved parent with a *resolved* root, so with a relative `download_dir` it `rmdir`s the download folder itself | confirmed (reproduced) | resolve both sides before comparing |
| 02 | Gallery collision matching (`stem (` … `)`) also matches the user's own files, e.g. `clip (Official Music Video).mp4` | real, blast radius overstated | digits only (`\d+`); it is owner-scoped, so it could only have hit copies **this app** published |
| 03 | After a settings change, an older job's files are "outside the download folder" → 409, undeletable forever | confirmed | jobs persist their own `download_dir` (schema + `ALTER`); `_require_inside()` accepts either root |
| 04 | `POST /files/clear` runs while a download is active and unlinks its `.part`; yt-dlp then fails the final rename | confirmed | 409 with the active count; cancel first |
| 05 | A cancelled download leaves its `.part` (the row has `filepath = None`, so delete finds nothing) | confirmed | the progress hook records the target as soon as yt-dlp names it; `.part`/`.ytdl` candidates are deleted with it |
| 06 | The Firefox extension (`moz-extension://`) is rejected by the CORS allow-list — every call dies in preflight | confirmed | `moz-extension://<uuid>` accepted alongside `chrome-extension://<id>` |
| 07 | A hand-edited/corrupt `settings.json` (uncreatable `download_dir`, `"nan"`) bricks every start | confirmed | per-key validation on load with default fallback; `download_dir` must be provably writable before it is saved |
| 08 | A cancel that lands while yt-dlp is finishing still reports `completed` and fires the completion action | confirmed | the lock decides; a cancelled row stays cancelled |
| 09 | Per-job overrides can enable raw arguments, and raw arguments can move the output path (`-o/-P`) | confirmed | `raw_args_enabled` added to the per-job deny list — the *switch* is app-level; `raw_args` itself stays a feature (an override's arguments are inert while the switch is off, asserted at the opts level); `-o/-P/--output/--paths` denied in raw args |
| 10 | A cancelled playlist leaves every entry it had already written | confirmed | finished entries are appended to `files` as they land |
| 11 | On Android a playlist row asks the gallery to delete the *folder's* name (matches nothing) and offers Open/Share on a folder | confirmed | the UI works from the recorded `files` list; the Kotlin hand-off refuses a directory |
| 12 | `DELETE /presets/{name}` fails CORS preflight (DELETE missing from `allow_methods`) | confirmed | `DELETE` allowed |
| 13 | The per-download Tags block cannot express "off" — a global embed cannot be disabled for one job | confirmed | three-state selects (use my settings / on / off); a preset's `false` renders as off |
| 14 | `scripts/smoke.py` hard-codes `.venv/bin/python` (dies in a worktree/fresh clone) | confirmed | prefers the venv, falls back to `sys.executable` |
| 15 | `scripts/entry.py` never calls `multiprocessing.freeze_support()` (frozen Windows builds re-spawn) | confirmed | called before `main()` |
| 16 | The extension keeps cookie headers for *every* request in a tab, not just media | confirmed | media requests only |

**Also checked by the auditor and found clean** (recorded for honesty):
the process-wide engine boot, the `files`-scoped delete path for legacy
rows, the UI's Escape/tab-scoping logic, and the Android 16 KB alignment.
