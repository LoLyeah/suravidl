"""v0.45.13 "the anchor" — deleting a job must not move the reader.

Report (Android, 2026-10-07): "after deleting failed job, the screen
automatically scrolls to the bottom". Reproduced live on a scratch
engine with real failed jobs: it was NOT scrolling — it was content
motion. The renderer's placement loop ran BEFORE the dying rows were
marked `.leaving`, so its anchor chain walked onto the just-deleted row
while it still looked ordinary: every other row was inserted IN FRONT
of it and the deleted row visibly sailed to the end of the list while
fading. Marked-first ordering + anchors that skip dying rows keep every
row in place; leaveRow's keepView re-anchors the reader's topmost
visible row after the removal (Chromium's native anchoring can pick the
dying node and land the viewport anywhere).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(encoding="utf-8")


def _fn(name):
    return APP.split(f"function {name}(")[1].split("\n}")[0]


def test_dying_rows_are_marked_before_the_placement_loop():
    """keep is filled from the list, THEN the leavers are marked, THEN the
    order is placed — the exact order that stops the hoist."""
    seg = _fn("refreshJobs")
    i_keep = seg.index("const keep = new Set(list.map")
    i_mark = seg.index("leaveRow(r, true)")
    # the first "for (const j of list)" in the body is the JOB_STATE
    # bookkeeping loop far above — anchor the PLACEMENT loop at its head
    i_loop = seg.index("let prev = null;")
    assert i_keep < i_mark < i_loop, "the three passes must stay ordered"


def test_anchors_skip_dying_rows():
    seg = _fn("refreshJobs")
    i = seg.index("let anchor = prev ? prev.nextElementSibling")
    chunk = seg[i:i + 700]
    assert 'classList.contains("leaving")' in chunk, \
        "the anchor chain must skip past dying rows"
    assert "anchor = anchor.nextElementSibling" in chunk


def test_leave_row_keeps_the_readers_spot():
    seg = _fn("leaveRow")
    assert "keepView" in seg
    assert "scrollingElement" in seg, "the anchor math uses the real scroller"
    # the engine's removals ask for the view anchor; filters do not
    assert "leaveRow(r, true)" in APP


def test_the_pin_comment_names_the_report():
    i = APP.index("mark the dying rows BEFORE the placement loop")
    assert "content motion, not scrolling" in APP[i:i + 600]


# ---- second half: the merge fix, completed (the "finished" hook) ----

SRC = (ROOT / "src" / "suravidl_engine" / "extract.py").read_text(encoding="utf-8")


def test_the_finished_hook_cleans_before_any_pass():
    """v0.45.12's PP saved the RETRY; a FRESH download still died inside
    yt-dlp's own FixupM3u8 (per-info fixups run ahead of every attached
    PP — `additional_pps + self._pps` in run_all_pps — so its `-map 0
    -c copy` met the broken stream first and the PP never entered). The
    finished-download progress hook cleans the file before anything."""
    i = SRC.index("def _attach_stream_copy_fix")
    seg = SRC[i:i + 1800]
    assert "add_progress_hook" in seg
    assert 'd.get("status") == "finished"' in seg
    assert 'pp.fix_file(d["filename"])' in seg
    assert 'when="post_process"' in seg, "the PP stays for retries"


def test_fix_file_is_shared_by_hook_and_pp():
    cls = SRC[SRC.index("class StreamCopyFixPP"):SRC.index("def _attach_stream_copy_fix")]
    assert "def fix_file(self, path" in cls
    run = cls[cls.index("def run(self, info)"):]
    assert "self.fix_file(" in run, "run() delegates to the shared core"
    assert "additional_pps" in cls, "the docstring records WHY the hook exists"
