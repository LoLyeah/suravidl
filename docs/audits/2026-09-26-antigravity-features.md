# Feature review — Antigravity, 2026-09-26

Third independent pass, this time a *product* review instead of a bug hunt:
"what does this app still need?" (23 KB of ranked findings, run against a
detached worktree at v0.21.2). The rule of the house held — **nothing was
implemented because the report said so**: every claim was checked against the
code and, where possible, reproduced on the live engine first. This is the
record of that check plus what shipped in v0.22.0.

## Verdict per finding

| # | Claim | Verified? | Outcome |
|---|-------|-----------|---------|
| 1 | Everything lands in one flat folder; playlists collide | ✅ `validate_template` really did reject `sub/dir/…`, so no template could make a subfolder | **Shipped**: relative subfolders allowed + `subfolders` setting (off / playlist / site) |
| 2 | No way to download only a section (`--download-sections`) | ✅ no `download_ranges` anywhere in the engine | **Shipped**: clip start/end per download, chapter chips from the probe |
| 3 | MKV/WebM will not open in QuickTime, iOS Files, Smart TVs | ✅ `merge_output_format` was left unset except in presets | **Shipped**: `video_container` (auto/mp4/mkv), remux only, per download + setting |
| 4 | Subtitle languages are typed blind; `.vtt` unreadable on TVs | ✅ `subtitles_langs` is a free-text field; probe carried `subtitles`/`automatic_captions` unused | **Shipped**: language chips from the probe + `subtitles_to_srt` (ffmpeg converter) |
| 5 | No batch paste; one link per click | ✅ nothing multi-URL existed | **Shipped**: `POST /jobs/batch` (≤20, per-link skips) + "queue them all" in the UI |
| 6 | Cancel is destructive; no pause | ⚠️ **half true** — cancel is already *cooperative* and keeps the `.part`, and retry resumes it (v0.21.2 made this explicit). What was missing was the *word*: every stop read as "cancelled" | **Shipped**: `pause`/`resume` (same cooperative stop, its own status, its own buttons) |
| 7 | The archive is a black box — an archived video can never be re-downloaded | ✅ `archive.txt` was unreachable from the UI (and app-private on Android) | **Shipped**: `archive_ignore` per download + `GET /archive` + `POST /archive/forget` |
| 8 | Live streams are not detected; stopping one corrupts the file | ⚠️ **overstated** — yt-dlp's own live handling finalises the container, and the probe already returned `is_live`. What was missing was any UI trace of it | **Partial**: LIVE badge from the probe + `live_from_start` setting. No custom "graceful finalizer" — see below |
| 9 | Audio is stuck at MP3 192k; no Opus/FLAC/320k | ✅ `AUDIO_PRESETS` had exactly three entries | **Shipped**: `audio-mp3-320`, `audio-mp3-128`, `audio-flac`, `audio-opus` |
| 10 | Finished files cannot be played in the browser | ✅ only "reveal in file manager" existed | **Shipped**: `GET /jobs/{id}/stream` (Range/206, same path guard as delete) + in-page player |
| 11 | Retry re-runs the exact failing request | ✅ `retry()` took no parameters | **Shipped**: retry accepts `{fmt, preset, overrides, raw_args}` + "Edit & retry" loads the failed row into the form |
| 12 | No queue priority / reordering | ✅ FIFO by construction (one thread per job on a capacity CV) | **Deferred** — the report itself lists it under "explicitly postpone", and it means replacing the threading model. Not in v0.22.0 |

## Where the report was wrong (recorded, not quietly dropped)

- **#6 "cancel abruptly aborts … resets progress … retry creates an entirely
  new job"** — the cooperative stop, the kept `.part` and the resume-on-retry
  already existed (v0.21.2 fixed the last hole: a cancelled job now records its
  `.part`). The real gap was the status vocabulary, which is what shipped.
- **#8 "cancel leaves the file without a valid moov atom"** — that is not what
  the engine does (there is no wrapper around yt-dlp's live stopping) and a
  custom finalizer is exactly the kind of thing the report itself says to
  postpone. Recorded as partial instead of pretending to fix it.
- **#1's mechanism** — the report blamed `validate_template` for rejecting
  separators *and* pointed at yt-dlp templates; only the first is true (the
  templates it suggested were already legal). Fixing the real cause was enough.

## The traps it warned against (agreed, and already the app's position)

No embedded browser for Android login, no background channel watcher/cron, no
cloud sync or accounts, no screen/canvas capture, no re-encoding suite. All
five match existing decisions: cookies never leave the device, DRM is out of
scope, the engine remuxes instead of transcoding.

## Verification

`tests/test_features22.py` — 36 tests, written RED first: subfolder routing and
its safe bounds, container remux (real ffprobe run), clip parsing/ranges and a
real clipped download, the four audio presets (real 320k bitrate check), batch
queueing and its refusals, archive skip/ignore/list/forget, streaming with
Range, pause/resume over a throttled range-capable fixture, retry-with-edits,
the live-from-start plumbing, and an id-lock that every new control is really
in the UI.
