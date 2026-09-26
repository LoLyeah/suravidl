"""A structured engine error must survive the trip to the UI.

The engine now answers "Unsupported URL" with {message, hint, unsupported}
instead of a bare string: the message is for the user, the flag is for the UI
(which will offer the browser in M3). app.js must keep the whole detail on the
Error it throws — and still show a human message, never "[object Object]".
"""
from pathlib import Path

APP = (Path(__file__).parent.parent
       / "src/suravidl_engine/web/app.js").read_text()


def test_the_ui_shows_the_message_of_a_structured_error():
    assert 'typeof detail === "object"' in APP
    assert "detail.message" in APP


def test_the_ui_keeps_the_whole_detail_for_later_decisions():
    assert "err.detail = detail" in APP
