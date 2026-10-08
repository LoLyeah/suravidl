"""v0.45.17 "the audit" — the confirmed findings of the independent audit.

An external auditor (Antigravity, isolated clone, 2026-10-07) reviewed
the stream-fix machinery. After confirmation against the tree and lab
probes, these findings were real and are fixed here:

- the remux now carries yt-dlp's own `-dn -ignore_unknown` (as tolerant
  as the metadata pass it protects) and converts text subtitles to
  mov_text for mp4 targets (the mp4 muxer cannot copy srt/webvtt; the
  encoder ships in both ffmpeg builds);
- the attempt ladder gives every flagged stream a LONE rung before the
  union — a false alarm on one track can never drag a healthy one out
  (the old rung dropped all flagged audio together: one bad mp3 could
  silence a file whose aac was merely mis-reported);
- the dedupe keeps the most informative report set;
- subprocess calls carry timeouts and the remux logs at `error` (a
  packet-error flood can no longer eat phone RAM), failing rungs clean
  their temp file, `os.replace` survives Windows file locks, and the
  temp name is unique per thread/pid;
- a file fixed by the finished-hook is skipped by the post-process pass
  (same path + mtime) instead of being probed/re-muxed twice;
- the completeness check compares unique index SETS (a repeated index
  in a diagnostic can no longer fake a shortfall);
- audio flags also catch `0 Hz`.

Refuted (kept as record): duplicate stream lines for multi-program
dumps (probed: each stream prints once); language-tag-before-pid order;
`-0:index` vs pid semantics; +faststart on the minimal build.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(encoding="utf-8")
CLS = SRC[SRC.index("class StreamCopyFixPP"):SRC.index("def _attach_stream_copy_fix")]


def test_the_remux_mirrors_yt_dlp_tolerance():
    assert '"-dn", "-ignore_unknown", "-c", "copy"' in CLS


def test_text_subtitles_convert_to_mov_text_for_mp4():
    # v0.45.18: the conversion is conditional; the final rung retries
    # without it and drops the unconvertible subs by name instead
    assert 'cmd += ["-c:s", "mov_text"]' in CLS
    assert 'cmd += ["-movflags", "+faststart"]' in CLS


def test_subprocess_calls_carry_timeouts():
    assert CLS.count("timeout=1800") == 1 and CLS.count("timeout=120") == 1


def test_the_remux_logs_at_error():
    assert '"-loglevel", "error", "-i"' in CLS


def test_the_temp_name_is_unique_per_thread():
    assert "threading.get_ident()" in CLS and "os.getpid()" in CLS


def test_os_replace_survives_a_lock():
    assert "except OSError:" in CLS and "could not replace the file" in CLS


def test_an_already_fixed_file_is_skipped():
    assert "fixed.get(path) == mtime" in CLS


def test_the_completeness_check_uses_sets():
    assert "set(streams) != mentioned" in CLS
    assert "Stream #0:(\\d+)" in CLS


def test_audio_flags_catch_zero_hz_too():
    assert "0 (channels|Hz)" in CLS


# ---- audit B (engine sweep) — confirmed findings ----

JOBS = (ROOT / "src" / "suravidl_engine" / "jobs.py").read_text(encoding="utf-8")
UPD = (ROOT / "src" / "suravidl_engine" / "updater.py").read_text(encoding="utf-8")
LOG = (ROOT / "src" / "suravidl_engine" / "logcap.py").read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "suravidl_engine" / "__main__.py").read_text(encoding="utf-8")


def test_no_bare_json_in_the_sidecar_list():
    # deleting a job must not take a user's document named like the media
    i = JOBS.index("SIDECAR_SUFFIXES")
    seg = JOBS[i:i + 400]
    assert '".info.json"' in seg and '".live_chat.json"' in seg
    assert '", ".json"' not in seg and '(".json"' not in seg


def test_one_paused_row_has_one_successor():
    assert 'if src.get("replaced_by"):' in JOBS
    assert 'live["replaced_by"] = job["id"]' in JOBS
    assert "replaced_by=excluded.replaced_by" in JOBS, "persisted"


def test_the_jobs_own_folder_wins_at_execution():
    assert 'target_dir = Path(job.get("download_dir") or self.download_dir)' in JOBS
    assert 'download_dir=src.get("download_dir"),' in JOBS


def test_a_successor_inherits_the_partials():
    assert 'partials=src.get("partials"))' in JOBS
    assert '"partials": list(partials) if partials else None,' in JOBS


def test_an_edit_can_clear_overrides():
    assert 'if "overrides" in patch:' in JOBS


def test_a_dead_playlist_is_not_a_success():
    assert "the playlist produced no downloads" in JOBS


def test_a_live_worker_blocks_delete():
    assert "self._running: set[str] = set()" in JOBS
    assert "job_id in self._running" in JOBS


def test_logs_get_scrubbed():
    assert "from .auth import scrub_secrets" in LOG


def test_the_update_cancel_closes_handles_first():
    i = UPD.index("def cancelled() -> bool:")
    seg = UPD[i:i + 700]
    assert "part.unlink" not in seg, "the unlink moved out of the live handle"
    assert "stopped = True" in UPD and "if stopped or cancelled():" in UPD


def test_the_port_check_reuses_addresses():
    assert "SO_REUSEADDR" in MAIN


def test_the_scrubber_really_redacts():
    import importlib
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "src"))
    from suravidl_engine import logcap
    importlib.reload(logcap)
    logcap.clear()
    logcap._push("https://cdn.example/master.m3u8?token=SUPERSECRET&x=1")
    joined = "".join(logcap.lines())
    assert "SUPERSECRET" not in joined and "token=" in joined


def test_the_successor_guard_and_override_clear_behavior(tmp_path):
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "src"))
    from suravidl_engine.jobs import JobManager
    import pytest as _pytest
    mgr = JobManager(download_dir=tmp_path)
    mgr._enqueue = lambda *a, **k: None       # no workers in this test
    job = mgr.create("https://example.com/v",
                     overrides={"subtitles_mode": "embed"})
    with mgr._lock:
        mgr._jobs[job["id"]]["status"] = "error"
    first = mgr.retry(job["id"], patch={"overrides": {}})
    assert first["overrides"] is None, "an edit can clear overrides"
    with _pytest.raises(ValueError):
        mgr.retry(job["id"])
