"""v0.40.11 "the shelf" — the sniff browser's chrome, unsqueezed.

The 2026-10-04 screenshot: the status line ("nothing found — press play,
then Scan") shared one row with five fixed-width chips. On a narrow phone
the chips ate the row, the weight-1 status text collapsed to about a
character wide, and its words stacked letter by letter into a tall ladder
while the chips floated in its middle. The status reads on its own
full-width shelf now, and the chips slide sideways when the phone is too
narrow for them.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER = (ROOT / "android/app/src/main/java/com/suravidl/app/BrowserActivity.kt").read_text()


def _build_ui_seg():
    i = BROWSER.index("private fun buildUi()")
    return BROWSER[i:BROWSER.index("root.addView(chipRoll", i) + 400]


def test_the_status_line_has_its_own_shelf():
    seg = _build_ui_seg()
    assert "root.addView(status" in seg, "the status line left its own full-width row"
    assert "LinearLayout.LayoutParams(MATCH, WRAP))" in seg, "status lost its full width"
    # the squeeze cannot come back: the status must never ride the chip row
    assert "row.addView(status" not in seg


def test_the_chip_rail_slides_when_the_phone_is_narrow():
    seg = _build_ui_seg()
    assert "HorizontalScrollView(this)" in seg, "the chips lost their slide"
    assert "isHorizontalScrollBarEnabled = false" in seg, "a scrollbar would mar the rail"
    assert "chipRoll.addView(row" in seg, "the chips left the rail"
    # every control still rides the rail — none was dropped to make room
    for label in ("ads blocked", "mobile site", "Scan", "Clear list", "Clear data"):
        assert label in seg, f"the rail lost {label!r}"
