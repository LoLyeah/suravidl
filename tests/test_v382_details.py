"""v0.38.2 — the toast lane adapts; the expanded queue card reads like a receipt.

Two device reports (2026-10-01):

1. "Why the toast is still way above the bottom bar like it's above something
   missing? ... make it adaptive, if there's a functional button below it then
   add padding, if not then don't." The phone lane was pinned at bar + 84px on
   EVERY tab — a value tuned to clear the Download tab's transport — so on
   Queue and yt-dlp it hovered over nothing. Now the lane clears what each tab
   actually has: idle tabs dock at bar + 12px, Download keeps +84px for the
   transport, Settings' +150px (the pinned save strip) stays as it was.

2. "in Queue when the card expand, other than name show us the file size and
   the location too — it's expanding for a reason." The unfolded card gains a
   size + saved-path block; the engine reports the real bytes on disk
   (size_bytes — statted for single files, summed for playlist rows).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "suravidl_engine" / "web"
CSS = (WEB / "style.css").read_text()
APP = (WEB / "app.js").read_text()


def test_the_phone_toast_lane_measures_instead_of_guessing():
    """The lane must clear furniture only when furniture is really docked:
    the transport is sticky (at the top of the page it sits mid-panel), the
    Save strip docks with the settings scroll. A static per-tab rule is
    wrong both ways; the JS measures and only then lifts the lane."""
    # the fallback everywhere on a phone: just above the tab bar
    assert "bottom: calc(var(--tabbar-h) + 12px + env(safe-area-inset-bottom));" in CSS
    # no static per-tab overrides remain in the mobile block
    seg = CSS.split("@media (max-width: 899px)")[-1]
    assert 'body[data-tab="download"] #toasts' not in seg
    assert 'body[data-tab="settings"] #toasts { bottom: calc(' not in CSS
    # the measurement itself
    assert "function syncToastLane()" in APP
    assert '".transport, #panel-settings .modal-foot"' in APP
    assert "if (r.bottom < vh - 140) continue;" in APP       # docked-only
    assert "syncToastLane();\n  $(\"toasts\").append(t);" in APP   # wired into toast()
    assert "syncToastLane();\n}" in APP                      # and into showTab's tail
    # desktop keeps its own settings lane
    assert 'body[data-tab="settings"] #toasts { bottom: 150px; }' in CSS


def test_expanded_card_shows_size_and_location():
    assert '"jdetails"' in APP
    assert "humanBytes(j.size_bytes)" in APP
    assert '"jdpath"' in APP
    # the receipt only exists while the title is unfolded (v0.39.12: an
    # explicit row class — `:has()` is dropped whole by older engines)
    assert ".job.open .jdetails" in CSS


def test_engine_reports_real_bytes(tmp_path):
    from suravidl_engine.jobs import JobManager

    f = tmp_path / "Nadia.mp4"
    f.write_bytes(b"x" * 4096)
    job = JobManager._row_to_job({"filepath": str(f), "files": None})
    assert job["size_bytes"] == 4096


def test_engine_sums_playlist_files(tmp_path):
    from suravidl_engine.jobs import JobManager

    d = tmp_path / "list"
    d.mkdir()
    a = d / "one.mp4"
    a.write_bytes(b"y" * 1000)
    b = d / "two.mp4"
    b.write_bytes(b"z" * 500)
    job = JobManager._row_to_job({"filepath": str(d), "files": json.dumps([str(a), str(b)])})
    assert job["size_bytes"] == 1500


def test_engine_makes_no_claim_when_nothing_is_on_disk(tmp_path):
    from suravidl_engine.jobs import JobManager

    job = JobManager._row_to_job({"filepath": str(tmp_path / "gone.mp4"), "files": None})
    assert job["size_bytes"] is None


def test_the_live_listing_reports_size_too(tmp_path):
    """get()/list() hand out in-memory copies that never pass through the row
    serializer — the stat has to happen there as well or the API answers
    null (caught live on the 0.38.2 build)."""
    from suravidl_engine.jobs import JobManager

    mgr = JobManager(download_dir=tmp_path)
    f = tmp_path / "x.mp4"
    f.write_bytes(b"q" * 777)
    mgr._jobs["j1"] = {"id": "j1", "status": "completed", "filepath": str(f), "files": None}
    assert mgr.get("j1")["size_bytes"] == 777
    assert mgr.list()[0]["size_bytes"] == 777
