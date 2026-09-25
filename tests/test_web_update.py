"""The update check, after the cramped header pill.

The old UI appended a one-line button into the header: on a phone it was a
squeezed strip between the title and the edge, it could not say what version
was newer, and it had no way to be dismissed. It is now one persistent notice
with real choices (Get it / Later / Skip this version) plus a Settings row
that can be looked at any time. These tests pin that shape.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()


def _fn(name, end_marker):
    """The source of a function: from its declaration to `end_marker`."""
    assert f"{name}" in APP, f"{name} is missing"
    return APP.split(name, 1)[1].split(end_marker, 1)[0]


def test_the_cramped_header_pill_is_gone():
    """It sat between the title and the edge with no room to say anything."""
    assert "updateSlot" not in APP and "updateSlot" not in HTML
    assert "updateLink" not in APP and "updateLink" not in CSS
    # the version line it sat beside stays
    assert 'id="versions"' in HTML and 'loadVersions' in APP


def test_the_update_notice_is_a_persistent_toast_with_choices():
    banner = _fn("function showUpdateBanner", "\n/** force")
    assert "sticky: true" in banner, "the notice must wait for an answer"
    assert "Skip this version" in banner and "Later" in banner
    assert "Get ${u.latest}" in banner
    # exactly one notice, however many times the check runs
    assert 'document.querySelector(".toast.update")' in banner
    # "Get it" opens the release page: nothing here installs anything
    assert "openExternal(u.url)" in banner


def test_sticky_toasts_wait_and_plain_ones_do_not():
    t = _fn("function toast", "\nfunction dismiss")
    assert "opts.sticky" in t and "4200" in t
    # the choice buttons must not let their click also dismiss by bubbling
    assert "ev.stopPropagation()" in t


def test_skip_and_remember_are_per_device_and_survive_a_restart():
    assert 'skipped: "suravidl.upd.skipped"' in APP
    assert 'snooze: "suravidl.upd.snooze"' in APP
    assert "SNOOZE_MS: 24 * 60 * 60 * 1000" in APP, "Later must mean a day, not forever"
    # 'Later' writes the deadline, 'Skip' writes the version
    later = _fn('{ label: "Later"', "},")
    assert "Date.now() + UPD.SNOOZE_MS" in later
    skip = _fn('{ label: "Skip this version"', "},")
    assert "updStore.set(UPD.skipped, u.latest)" in skip


def test_a_skipped_or_snoozed_version_does_not_pop_up_by_itself():
    check = _fn("async function checkAppUpdate", "\nfunction wireUpdateRow")
    assert "const skipped = updStore.get(UPD.skipped" in check
    assert "Number(updStore.get(UPD.snooze" in check
    # the boot check respects both; the explicit one (force) does not
    assert "if (force || (!skipped && Date.now() >= until)) showUpdateBanner(u)" in check


def test_the_settings_row_always_answers_the_button():
    """Settings → General → Updates: state, versions, and the way to ask again."""
    for el_id in ("updState", "updMeta", "updGet", "updSkip", "updCheck"):
        assert f'id="{el_id}"' in HTML, f"{el_id} is missing from Settings"
    wire = _fn("function wireUpdateRow", "\n/** Open a link outside")
    assert "checkAppUpdate(true)" in wire, "Check now must force past skip/snooze"
    assert "latest version" in wire          # up to date: say so
    assert "update check failed" in wire     # and when the check itself fails
    row = _fn("function renderUpdateRow", "\n/** The one persistent notice")
    assert "up to date" in row
    assert '"Skip this version"' in row and "Stop skipping" in row, \
        "a skipped version must stay reachable from Settings"
    # the row must re-read the stored answer even before this session has one
    assert "JSON.parse(updStore.get(UPD.last" in row


def test_the_notice_survives_being_dismissed_by_a_choice():
    """Skipping hides the notice now and keeps the row honest afterwards."""
    skip = _fn('{ label: "Skip this version"', "},")
    assert "renderUpdateRow()" in skip
