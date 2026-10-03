"""v0.40.4 "the marks" — Mark in / Mark out: the in-page player's own clock
writes the clip fields, so a section is cut from what you are watching
instead of a time typed from memory.

RED first: no such buttons on 0.40.3.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/suravidl_engine/web/app.js").read_text()
HTML = (ROOT / "src/suravidl_engine/web/index.html").read_text()


def _seg(source, start, end="\nfunction "):
    body = source.split(start)[1]
    return body.split(end, 1)[0]


def test_the_player_gains_mark_buttons():
    assert 'id="markIn"' in HTML and 'id="markOut"' in HTML
    head = HTML.split('id="playModal"')[1][:600]
    assert 'id="markIn"' in head and 'id="markOut"' in head, \
        "the marks live in the player's own head"
    assert "function markClip(" in APP


def test_the_marks_write_the_clip_fields_from_the_players_clock():
    seg = _seg(APP, "function markClip(")
    assert '"ovClipStart"' in seg and '"ovClipEnd"' in seg
    assert "clock(t)" in seg, "the fields take h:mm:ss; the clock speaks it"
    assert "currentTime" in seg
    assert "clip starts at " in seg and "clip ends at " in seg, \
        "a mark says where it landed"


def test_the_marks_follow_the_player_element():
    assert "let PLAY_NODE = null;" in APP
    open_seg = _seg(APP, "function openPlayerSrc(")
    assert "PLAY_NODE = node" in open_seg
    assert 'classList.toggle("hidden", !isVideo)' in open_seg, \
        "only a video has a clock to mark"
    close_seg = _seg(APP, "function closePlayer(")
    assert "PLAY_NODE = null" in close_seg, \
        "a released player has nothing left to mark"


def test_the_marks_are_wired_in_the_player():
    seg = _seg(APP, "function initPlayer(")
    assert 'markClip("in")' in seg and 'markClip("out")' in seg
