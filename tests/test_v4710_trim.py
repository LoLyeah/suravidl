"""v0.47.10 "the trim" — one completion label, and no alarm-coloured dot.

Owner's screenshot (2026-10-21): a finished row wore COMPLETED and FILED side
by side — two green words for one fact — and the YouTube rows carried a red
dot that reads as "something is wrong". The stamp is gone (the pill says it
once), and the queue row's site LED is gone too (the host is already printed
in the meta line); the probe card keeps its site tint as a text colour.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text()
CSS = (ROOT / "src/suravidl_engine/web/style.css").read_text()


def test_a_completed_row_is_named_once():
    assert 'el("span", "stamp", t("FILED"))' not in APP
    assert 'el("span", "pill " + j.status' in APP, "the pill still names the state"


def test_the_queue_row_wears_no_alarm_dot():
    assert ".job[data-livery] .jobtop::before" not in CSS
    assert ".card[data-livery] #probeMeta" in CSS, "the probe card keeps its tint"


def test_the_bulk_actions_keep_their_word():
    assert "Delete filed files" in APP
    assert "Clear history" in APP
