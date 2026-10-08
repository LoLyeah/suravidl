# Audit Report A: The Stream-Fix Machinery (`StreamCopyFixPP`)

**Repository**: `suravidl` (`suravidl_engine`)  
**Commit / Tag**: `bb971de` (`v0.45.16`)  
**Scope**: `src/suravidl_engine/extract.py` (`StreamCopyFixPP`, `_parse_stream_dump`, `_streams_by_ffmpeg`, `_attempt_ladder`, `_remux`, `fix_file`, `run`, `_attach_stream_copy_fix`), `scripts/build_ffmpeg_android.sh`, and regression test suites (`tests/test_v4512_merge.py`, `test_v4513_anchor.py`, `test_v4514_oracle.py`, `test_v4515_keeper.py`, `test_v4516_proof.py`).  
**Audit Stance**: Independent, read-only, adversarial verification.

---

## Executive Summary

The `StreamCopyFixPP` machinery was introduced across releases `v0.45.12` through `v0.45.16` to salvage downloads where headerless or corrupted secondary streams (e.g., garbage MP3 tracks in HLS MPEG-TS feeds) cause yt-dlp's metadata and fixup passes to fail with `Conversion failed!`.

While the evolution from ffprobe JSON to FFmpeg input dumps and negative mapping (`-map 0 -map -0:N`) addressed desktop vs. Android probe discrepancies, the current implementation contains critical structural defects:
1. **Container Incompatibility in Negative Mapping**: Remuxing with bare `-map 0 -c copy` into MP4 fails completely whenever input files contain standard web subtitles (`subrip`/SRT, `webvtt`, `ass`), as FFmpeg's MP4 muxer strictly rejects copying these subtitle formats. Every attempt ladder rung fails, rendering the fixer completely inoperable for captioned media.
2. **Monolithic Audio Dropping**: When multiple audio tracks are flagged (a regular occurrence under the app's `analyzeduration 0` settings), the attempt ladder drops all flagged audio tracks together rather than testing them individually, stripping surviving healthy audio tracks.
3. **Flawed Deduplication Suppressing Notifications**: The attempt ladder deduplicates rungs solely on `drop`, discarding user notification sets (`real`) when non-AV streams are dropped.
4. **Fragile Completeness Check**: Counting raw occurrences of `Stream #0:\d+` causes false rejections on multi-program transport streams (MPTS) and streams with metadata or warnings mentioning stream indices.
5. **Double Remuxing & Unbounded Subprocesses**: Fresh downloads trigger redundant probes and multi-gigabyte remuxes in both progress hooks and post-processing, running unbounded `subprocess.run` calls without timeouts and buffering verbose logs in RAM.

---

## Findings

### FINDING 1: Incompatible Subtitle Passthrough Under `-map 0 -c copy` Breaks All Remux Attempts on Captioned MP4s
- **Severity**: CRITICAL
- **Evidence**:
  - `src/suravidl_engine/extract.py:267-270`:
    ```python
    cmd = [ffmpeg, "-y", "-loglevel", "repeat+info", "-i", path, "-map", "0"]
    for idx in drop:
        cmd += ["-map", f"-0:{idx}"]
    cmd += ["-c", "copy"]
    ```
  - `src/suravidl_engine/extract.py:350-351`:
    ```python
    nonav = {i for i, (kind, _) in streams.items()
             if kind not in ("Video", "Audio", "Subtitle")}
    ```
- **What**: In `_attempt_ladder`, `nonav` explicitly excludes `"Subtitle"`, treating subtitle tracks as essential media to retain. When `_remux` executes, it applies `-map 0` with negative mappings only for streams in `drop`, followed by `-c copy`. For MP4 containers (`.mp4`, `.m4v`, `.mov`, `.m4a`), FFmpeg's MP4 muxer does not support copying raw text or subtitle formats like SubRip (`subrip`/SRT), WebVTT (`webvtt`), or Advanced SubStation Alpha (`ass`). FFmpeg immediately fails at the header write stage with: `Could not find tag for codec subrip in stream #..., codec not currently supported in container` -> `Could not write header (incorrect codec parameters ?): Invalid argument` (exit code 234).
- **Why it matters**: Web video streams (HLS playlists, DASH manifests, MKV sources) frequently embed WebVTT or SRT subtitle streams. If any such media triggers `fix_file`, EVERY rung of the ladder retains the subtitle track and fails at `_remux`. The fix aborts with `"stream-copy fix could not apply — the file is left as-is"`, leaving the corrupted stream in place so the subsequent yt-dlp metadata pass dies.
- **Real failing scenario**: An HLS stream downloaded as `.mp4` containing Video (`h264`), Audio 1 (`mp3, 0 channels`), Audio 2 (`aac`), and Subtitle (`webvtt` or `subrip`). Rung 1, Rung 2, and Rung 3 all fail because FFmpeg refuses to copy the subtitle into MP4 without transcoding to `mov_text`.
- **Suggested fix**: Either exclude subtitle streams from default passthrough when target container is MP4, apply `-c:s mov_text` for MP4 targets, or add subtitle drop options into the attempt ladder when remuxing fails.

---

### FINDING 2: Monolithic Audio Dropping Discards Healthy Secondary Audio Tracks
- **Severity**: CRITICAL
- **Evidence**:
  - `src/suravidl_engine/extract.py:352`:
    ```python
    flagged_audio = {i for i in bad if streams.get(i, ("", ""))[0] == "Audio"}
    ```
  - `src/suravidl_engine/extract.py:355-356`:
    ```python
    if flagged_audio:
        ladder.append((nonav | flagged_audio, set(flagged_audio)))
    ```
- **What**: `_attempt_ladder` aggregates all audio streams flagged in `bad` into a single set `flagged_audio` and creates a single rung that drops all of them simultaneously (`nonav | flagged_audio`). It never iterates through subsets or drops audio streams one by one.
- **Why it matters**: Under the app's minimal probe configuration (`analyzeduration 0`), FFmpeg's input dump frequently emits false-alarm warnings (`Could not find codec parameters for stream N`) on healthy audio tracks as well as corrupted ones. If a stream contains one broken audio track (e.g. Stream 1 MP3) and one healthy audio track (e.g. Stream 2 AAC), and both are flagged in `bad`:
  1. Rung 1 (keep all) fails because Stream 1 is broken.
  2. Rung 2 unconditionally drops BOTH Stream 1 and Stream 2.
  3. The remux succeeds, but the resulting output is completely silent (video-only). The healthy audio is discarded without individual evaluation.
- **Real failing scenario**: An HLS stream with Stream 0 (`h264`), Stream 1 (`mp3, 0 channels`), and Stream 2 (`aac, 92 kb/s`). Both Stream 1 and Stream 2 trigger `Could not find codec parameters` under low probesize. Rung 2 drops `{1, 2}`. Output is video-only; the user loses all audio.
- **Suggested fix**: Expand the attempt ladder to test dropping individual flagged audio streams before dropping the entire union of flagged audio streams.

---

### FINDING 3: Deduplication in `_attempt_ladder` Ignores `real`, Silently Suppressing Removal Logs
- **Severity**: HIGH
- **Evidence**:
  - `src/suravidl_engine/extract.py:363-368`:
    ```python
    seen, out = set(), []
    for drop, real in ladder:
        key = frozenset(drop)
        if key in seen:
            continue
        seen.add(key)
        out.append((sorted(drop), real))
    ```
  - `src/suravidl_engine/extract.py:313-320`:
    ```python
    if self._remux(path, drop):
        if real:
            names = ", ".join(
                f"{i}:{streams[i][0]}/{streams[i][1]}" for i in sorted(real))
            self.to_screen(
                f"Dropped {len(real)} unusable stream(s) "
                f"before the metadata pass ({names})")
        return True
    ```
- **What**: The attempt ladder deduplication loop keys strictly on `key = frozenset(drop)`. In Rung 1, `ladder` records `(nonav, set())`. If `bad` contains any non-audio, non-video stream (such as a corrupt attachment or unsupported data stream), `flagged_other` is a subset of `nonav`. In Rung 3, the drop set is `nonav | flagged_audio | flagged_other`, which evaluates to `nonav`. Because `frozenset(nonav)` was already registered by Rung 1, Rung 3 is discarded by `if key in seen: continue`.
- **Why it matters**: Only Rung 1 survives in `out`, where `real` is `set()`. When `_remux` executes and successfully drops the bad stream, `if real:` evaluates to `False`. The fix applies and replaces the file on disk, but `self.to_screen` is never called. The removal occurs silently without any audit trail in the logs, violating the requirement of honest logs and named stream removals ("the drop line names its victims... so the next log can never be ambiguous").
- **Real failing scenario**: A video container with Stream 0 (`Video/h264`) and Stream 1 (`Attachment/none` or corrupt Data), where FFmpeg emits `Could not find codec parameters for stream 1`. `bad = {1}`, `nonav = {1}`, `flagged_other = {1}`. Ladder yields `[([1], set())]`. Stream 1 is stripped from the file, but 0 drops are logged.
- **Suggested fix**: Deduplicate by `frozenset(drop)` but preserve the most informative reporting set `real` (e.g. `seen[key] = max(seen[key], real, key=len)`), or key by `(frozenset(drop), frozenset(real))`.

---

### FINDING 4: Completeness Check Rejects Valid Multi-Program Transport Streams (MPTS) and Repetitive Stream Warnings
- **Severity**: HIGH
- **Evidence**:
  - `src/suravidl_engine/extract.py:254-255`:
    ```python
    if len(streams) != len(re.findall(r"Stream #0:\d+", err)):
        return None
    ```
- **What**: In `_streams_by_ffmpeg`, the parser validates that the number of parsed stream dict entries equals the total number of regex matches for `Stream #0:\d+` in FFmpeg's stderr output. In FFmpeg's `libavformat/dump.c`, when a transport stream contains multiple programs (`ic->nb_programs > 0`), `dump_stream_format` is invoked iteratively for each program. If streams belong to or are shared across programs, `Stream #0:N` is printed multiple times in the dump. Furthermore, if FFmpeg outputs diagnostic warnings or metadata referencing `Stream #0:N`, `re.findall` counts each occurrence.
- **Why it matters**: `streams` is a dictionary keyed by stream integer index `N`, so duplicate mentions result in `len(streams) < len(re.findall(...))`. The completeness check fails, returning `None`. `fix_file` bails with `"stream check could not read ffmpeg's report — leaving the file as-is"`. The fix will never execute for multi-program transport streams or files containing stream references in metadata.
- **Real failing scenario**: An MPEG-TS capture or broadcast feed containing Program 1 and Program 2 where Stream 0 is shared or repeated in the program map. `Stream #0:0` appears twice in FFmpeg's stderr. `len(streams)` is 1, while `len(re.findall(...))` is 2. `_streams_by_ffmpeg` aborts.
- **Suggested fix**: Verify completeness against the set of unique stream indices: `len(streams) == len(set(re.findall(r"Stream #0:(\d+)", err)))`, or anchor regex extraction strictly to the input dump stream table.

---

### FINDING 5: `_remux` Lacks `-dn` and `-ignore_unknown`, Causing Failures on Private Data Streams
- **Severity**: HIGH
- **Evidence**:
  - `src/suravidl_engine/extract.py:267-270`:
    ```python
    cmd = [ffmpeg, "-y", "-loglevel", "repeat+info", "-i", path, "-map", "0"]
    for idx in drop:
        cmd += ["-map", f"-0:{idx}"]
    cmd += ["-c", "copy"]
    ```
- **What**: In yt-dlp's own `FFmpegMetadataPP`, remux commands explicitly supply `-dn` and `-ignore_unknown` when executing `-map 0 -c copy`. `StreamCopyFixPP._remux` omits both flags. If an input container contains unrecognized data streams (e.g. SCTE-35 markers, proprietary telemetry PIDs, or unsupported binary descriptors) that are either unparsed or not recognized by the target container, `-map 0` forces FFmpeg to attempt copying them.
- **Why it matters**: Without `-ignore_unknown`, FFmpeg aborts stream copying when encountering uncopyable data streams. Because `-map 0` maps all streams by default, any unknown stream that is not explicitly named in `drop` causes FFmpeg to exit non-zero, causing all rungs of `_attempt_ladder` to fail.
- **Real failing scenario**: An HLS MPEG-TS stream carrying timed private metadata or SCTE-35 splice markers. FFmpeg fails to remux into MP4 because the MP4 muxer cannot copy the raw private data packets without `-dn` or `-ignore_unknown`.
- **Suggested fix**: Add `-dn` (or `-ignore_unknown`) to `_remux` command parameters, consistent with yt-dlp's metadata pass.

---

### FINDING 6: Unbounded Subprocess Calls Lack Timeouts and Buffer Exhaustive Logs in RAM
- **Severity**: HIGH
- **Evidence**:
  - `src/suravidl_engine/extract.py:245-247`:
    ```python
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "info", "-i", path],
        capture_output=True, text=True)
    ```
  - `src/suravidl_engine/extract.py:267`, `274`:
    ```python
    cmd = [ffmpeg, "-y", "-loglevel", "repeat+info", "-i", path, "-map", "0"]
    ...
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ```
- **What**: Both `_streams_by_ffmpeg` and `_remux` invoke `subprocess.run` without specifying `timeout=`. Additionally, `_remux` sets `-loglevel repeat+info` with `capture_output=True`, which captures all stdout and stderr in memory.
- **Why it matters**:
  1. If FFmpeg hangs on a corrupt stream, pipe stall, or unseekable input, the subprocess will block indefinitely. Because downloads run on a fixed worker pool of 4 threads (`POOL_SIZE = 4` in `jobs.py`), a hung FFmpeg process permanently leaks a worker slot.
  2. For large downloads (1–10 GB) with packet errors or timestamp discontinuities, `-loglevel repeat+info` causes FFmpeg to emit millions of lines of stderr. Buffering this entire output into a Python string via `capture_output=True` consumes excessive memory and risks Out-Of-Memory (OOM) termination on resource-constrained devices (such as Android).
- **Real failing scenario**: A 2 GB HLS download with frequent packet discontinuities. FFmpeg outputs hundreds of megabytes of log text during `-loglevel repeat+info`. Python crashes with `MemoryError` or Android kills the process due to RAM limits.
- **Suggested fix**: Add a reasonable timeout (e.g. `timeout=300`) to subprocess invocations, reduce log level to `warning` or `error` in `_remux`, and redirect stderr to `subprocess.DEVNULL` or a bounded buffer.

---

### FINDING 7: Unhandled `os.replace` Crashes When Files Are Locked or Open
- **Severity**: MEDIUM
- **Evidence**:
  - `src/suravidl_engine/extract.py:281`:
    ```python
    os.replace(tmp, path)
    return True
    ```
- **What**: In `_remux`, `os.replace(tmp, path)` is executed without exception handling. While atomic on POSIX, on Windows `os.replace` raises `PermissionError` (WinError 32) if the destination `path` is currently open by another handle (such as an active media player, Windows Explorer thumbnailer, or antivirus scanner).
- **Why it matters**: An uncaught `PermissionError` or `OSError` bubbles out of `_remux`. In `fix_file`, there is no `try...except` around `_remux`, so `fix_file` crashes. Furthermore, `tmp` is not cleaned up, leaving orphaned `.streamfix.mp4` files on disk.
- **Real failing scenario**: On Windows, downloading a file where Windows Search Indexer or a media player opens a read handle on the downloaded file immediately upon creation. `os.replace` raises `PermissionError`.
- **Suggested fix**: Wrap `os.replace` in a `try...except OSError` block, report a warning, and unlink `tmp` if replacement fails.

---

### FINDING 8: Double-Execution: Fixed Files Are Re-Probed and Potentially Re-Muxed in Post-Processing
- **Severity**: MEDIUM
- **Evidence**:
  - `src/suravidl_engine/extract.py:372`:
    ```python
    self.fix_file(info.get("filepath") or "")
    ```
  - `src/suravidl_engine/extract.py:402`:
    ```python
    pp.fix_file(d["filename"])
    ```
- **What**: On a fresh download, `_finished_hook` triggers `pp.fix_file(d["filename"])` and remuxes the file. Subsequently, yt-dlp finishes downloading and enters `post_process`, where `StreamCopyFixPP.run` calls `self.fix_file(info.get("filepath") or "")` on the exact same file a second time.
- **Why it matters**: Even if the file was already fixed by the progress hook, `_streams_by_ffmpeg` spawns FFmpeg again to re-probe the entire file. Worse, if the newly remuxed file still triggers a false-alarm warning under `analyzeduration 0` (e.g., `Could not find codec parameters for stream 0`), `bad` is non-empty on the second pass. Rung 1 will execute `_remux` AGAIN, needlessly remuxing multi-gigabyte media twice.
- **Real failing scenario**: A 1.5 GB download that is fixed in the progress hook. In post-processing, `run()` executes. If FFmpeg reports a false-alarm codec parameter warning on the output MP4 under minimal probe settings, the entire 1.5 GB file is remuxed a second time.
- **Suggested fix**: Maintain a set or attribute of already-fixed paths on the `StreamCopyFixPP` instance (or mark `info['__stream_copy_fixed'] = True`) to prevent redundant secondary passes.

---

### FINDING 9: Inverted Failure Ladder: Broken Video with Falsely Flagged Audio Is Unrecoverable
- **Severity**: MEDIUM
- **Evidence**:
  - `src/suravidl_engine/extract.py:354-358`:
    ```python
    ladder = [(nonav, set())]
    if flagged_audio:
        ladder.append((nonav | flagged_audio, set(flagged_audio)))
    if flagged_other:
        ladder.append((nonav | flagged_audio | flagged_other,
                       flagged_audio | flagged_other))
    ```
- **What**: The attempt ladder strictly follows the progression:
  1. Keep all (drop nonav only).
  2. Drop flagged audio.
  3. Drop flagged audio AND flagged non-audio (video).
  The ladder contains no rung that drops flagged video while retaining flagged audio.
- **Why it matters**: If a file contains a genuinely broken video track (e.g. invalid SPS/PPS, corrupt bitstream) that cannot be copied into MP4, and a healthy audio track that happened to trigger a false-alarm warning in `bad` under `analyzeduration 0`:
  - Rung 1 fails (video broken).
  - Rung 2 fails (drops audio, but video is still broken).
  - Rung 3 drops both video and audio (if only 1 video + 1 audio stream exist, `len(drop) == len(streams)`, skipping Rung 3).
  The fixer gives up completely, unable to recover the usable audio track.
- **Real failing scenario**: A stream with 1 uncopyable video stream and 1 healthy audio track, where both are flagged in `bad`. The ladder never tests dropping the video alone to save the audio.
- **Suggested fix**: In the attempt ladder, allow testing `nonav | flagged_other` (dropping broken video while preserving audio) as an intermediate rung before total removal.

---

### FINDING 10: Missing Audio Sample Rate and Channel Layout Edge Cases in `_parse_stream_dump`
- **Severity**: LOW
- **Evidence**:
  - `src/suravidl_engine/extract.py:233-235`:
    ```python
    for m in re.finditer(
            r"Stream #0:(\d+)(?:\[[^\]]*\])?(?:\([^)]*\))?: Audio: ([^\n]+)", err):
        if re.search(r"(^|,)\s*0 channels", m.group(2)):
            bad.add(int(m.group(1)))
    ```
- **What**: The regex only flags audio streams where `0 channels` appears preceded by a comma or the start of the audio descriptor string. If FFmpeg's `avcodec_string` outputs an uninitialized channel layout (which in FFmpeg causes channel layout to be omitted entirely, e.g. `Audio: mp3, s16p`), or formats channels with parentheses like `(0 channels)`, or reports a missing sample rate (`0 Hz`), the pattern fails to match.
- **Why it matters**: If an audio stream lacks sample rate or channel metadata but FFmpeg does not emit `Could not find codec parameters`, the stream is omitted from `bad`, bypassing the fix.
- **Real failing scenario**: An audio stream reporting `Audio: mp3, 0 Hz, stereo` or `Audio: mp3, s16p` without the explicit `, 0 channels` substring.
- **Suggested fix**: Expand the regex to detect `0 Hz` and audio descriptions lacking both standard channel layout names and channel counts.

---

### FINDING 11: Direct Mutation of Private `ydl._pps` Dict Is Vulnerable to yt-dlp API Drift
- **Severity**: LOW
- **Evidence**:
  - `src/suravidl_engine/extract.py:394-398`:
    ```python
    ydl.add_post_processor(pp, when="post_process")
    chain = ydl._pps.get("post_process")
    if chain and chain[-1] is pp and len(chain) > 1:
        chain.remove(pp)
        chain.insert(0, pp)
    ```
- **What**: `_attach_stream_copy_fix` directly accesses and mutates the private internal `ydl._pps` dictionary in `YoutubeDL`.
- **Why it matters**: yt-dlp frequently refactors internal structures (having already deprecated `parse_outtmpl` and other internals). While guarded by `try...except`, if yt-dlp changes `_pps` to an internal container or property, `StreamCopyFixPP` will fail to reorder itself to index 0, falling back to execution after other post-processors.
- **Suggested fix**: Check if `ydl._pps` is accessible before mutation and log an internal debug warning if reordering cannot take place.

---

### FINDING 12: Deterministic Temporary Filename Collides Under Concurrent Downloads
- **Severity**: LOW
- **Evidence**:
  - `src/suravidl_engine/extract.py:262-263`:
    ```python
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "mp4"
    tmp = f"{path}.streamfix.{ext}"
    ```
- **What**: The temporary remux file is named deterministically as `f"{path}.streamfix.{ext}"`.
- **Why it matters**: `suravidl` runs up to 4 concurrent worker threads (`POOL_SIZE = 4`). If two concurrent jobs (or a retried job racing with an existing process) target the same destination file path, both invoke `ffmpeg -y` targeting the identical `tmp` filename simultaneously, corrupting the file or colliding at `os.replace`.
- **Real failing scenario**: Two concurrent queue items downloading identical URLs or colliding output templates.
- **Suggested fix**: Append a unique token or PID (e.g. `f"{path}.streamfix.{os.getpid()}_{uuid.uuid4().hex[:6]}.{ext}"`) to the temporary filename.

---

## Ranked Top 5 Findings

| Rank | Finding ID | Severity | Summary |
| :--- | :--- | :--- | :--- |
| **1** | **FINDING 1** | **CRITICAL** | Incompatible subtitle passthrough under `-map 0 -c copy` fails all remux attempts on captioned MP4s. |
| **2** | **FINDING 2** | **CRITICAL** | Monolithic audio dropping in `_attempt_ladder` discards healthy secondary audio tracks. |
| **3** | **FINDING 3** | **HIGH** | Deduplication in `_attempt_ladder` keys only on `drop`, suppressing removal notifications. |
| **4** | **FINDING 4** | **HIGH** | Completeness check rejects valid multi-program transport streams (MPTS) and repetitive warnings. |
| **5** | **FINDING 6** | **HIGH** | Unbounded subprocess calls lack timeouts and buffer exhaustive logs into RAM under `-loglevel repeat+info`. |

---

## Refuted / Cannot Stand Behind

1. **`Language tag before PID in Stream #0:N`**:
   - *Hypothesis*: The regex `r"Stream #0:(\d+)(?:\[[^\]]*\])?(?:\([^)]*\))?"` assumes PID brackets `[...]` always precede language parentheses `(...)`, which would fail if language appeared first.
   - *Refutation*: In FFmpeg's `libavformat/dump.c` (`dump_stream_format`), the code prints `flags & AVFMT_SHOW_IDS` (`[0x%x]`) followed by `lang` (`(%s)`). PID strictly precedes language in FFmpeg's output generator.

2. **`-0:index` Mismatch vs Stream PID**:
   - *Hypothesis*: FFmpeg negative mapping requires stream PIDs rather than 0-based stream table indices.
   - *Refutation*: FFmpeg's `-map -0:{idx}` syntax specifies the stream index in the input file container (0, 1, 2...), not the PID. Mapping by PID requires the `-map -0:i:{pid}` syntax. `Stream #0:(\d+)` correctly extracts the stream index.

3. **`+faststart` Incompatibility with Android Minimal FFmpeg Build**:
   - *Hypothesis*: The Android FFmpeg build configured in `scripts/build_ffmpeg_android.sh` lacks components required for `-movflags +faststart`.
   - *Refutation*: Inspection of FFmpeg's `libavformat/movenc.c` shows that `+faststart` is executed via `shift_data()`, which re-opens the output file using the standard `file` protocol. The Android build script explicitly whitelists `--enable-protocol=file,pipe,data`.
