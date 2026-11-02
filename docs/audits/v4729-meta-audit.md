# v0.47.29 audit — per-download title/artist and chapter splitting

Audit by Argon (agy, "use Argon high") on `4d6ff44`, before the release
shipped. Every finding below was re-checked against the tree: fixed or
refuted, never relayed on faith.

## Blockers it found — all real, all fixed

1. **The uncut source was orphaned after a split.** `job["files"]` became
   the sections while the original stayed on disk: Delete missed it, and
   the next download of the same URL said "already on disk". The source is
   now removed once every section exists (and a failed split removes the
   sections it had already cut).
2. **The queue row hid chapters 2..N.** `playlistRow` only fired when the
   filepath was not among the files; a split row filepath is its FIRST
   section, so one Play remained. `redact_job` now exposes `split` and the
   row lists its files (verified in the running UI: "Files (2)", both
   sections with Play, summed size).
3. **`_stat_size` reported only the first section.** Split rows sum now.
4. **`-c copy` without `-map 0` dropped secondary streams.** A tag rewrite
   on a two-audio-track file left one audio track. Pinned by a test that
   builds exactly that file and counts the streams after the rewrite.

## Should-fix — all taken

- `.info.json` / poster sidecars are renamed with the download (they were
  left behind and later misses by Delete).
- A case-only rename is no longer read as a collision (`os.path.samefile`).
- `meta_title` + split: the rename now happens BEFORE the cut, so the
  sections carry the title (was: sections kept the site stem).
- 0-byte ffmpeg output can no longer replace a good file, and the temp is
  cleaned on failure or lock.
- Chapter names are bounded so a long title cannot pass `check_name`'s
  150 characters, and trailing dots are stripped.
- `CHAPTERS` is no longer sliced to the twenty chips drawn, and both
  `clearOv()` and a new URL reset it — the previous video's cut points
  cannot ride the next link.
- The new fields join `initOverrides` (the armed-count) and `editAndRetry`
  (a failed job comes back with its title and its cut).

## Refuted (not acted on)

- *"Tag writing fails across containers"* — measured working on mp4, mkv,
  mp3 (ID3v2) and webm.
- *"Chapter cuts are not frame-accurate"* — `-c copy` cuts on keyframes by
  design; the alternative is a re-encode of every section.

## Left open deliberately

- A title of only punctuation still refuses at `check_name` with a clear
  message rather than inventing a name.
- Native Android MediaStore import of split sections was not exercised
  here; the emulator board covers the app, not the gallery copy of a split.
