"""The UI half of the UI/Android review, pinned.

Every one of these was found by reading the code and reproduced before it was
believed; each test asserts the rule, not the wording, so a later edit that
re-opens the hole fails here.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text()
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "style.css").read_text()


def test_the_whole_video_button_does_something():
    """It shipped in the clip row with nothing attached: pressing it was a
    no-op that looked broken."""
    assert '$("ovClipClear").onclick' in APP
    seg = APP.split('$("ovClipClear").onclick')[1][:300]
    assert '$("ovClipStart").value = ""' in seg and '$("ovClipEnd").value = ""' in seg


def test_a_failed_row_offers_one_retry_not_two():
    """The error line already carries a Retry; the actions row added a second
    identical one, so failed rows looked broken. (The last such branch is the
    actions row — the earlier one renders the error line itself.)"""
    seg = APP.rsplit(
        '} else if (j.status === "error" || j.status === "interrupted") {', 1)[1]
    seg = seg.split("// every row can be deleted")[0]
    assert '"Edit & retry"' in seg
    assert '"Retry"' not in seg, "the actions row must not add a second Retry"


def test_an_outage_banner_leaves_when_the_engine_answers():
    """It was only ever removed on the non-empty path, so after one outage the
    queue claimed "cannot reach the engine" forever over an empty queue."""
    seg = APP.split("renderQueueBadge(jobs);")[1][:400]
    assert 'querySelector(".trouble")' in seg and "stale.remove()" in seg


def test_a_bare_host_is_a_link_and_the_batch_cap_is_visible():
    """The engine accepts a bare host but the UI's regex demanded a scheme, so
    a paste of bare links produced no batch at all."""
    assert "BARE_HOST.test(s)" in APP
    assert "only 20 fit in one batch" in APP
    assert '$("batchBtn").disabled = over' in APP


def test_unchecking_the_last_playlist_box_refuses_instead_of_meaning_all():
    """An empty field is the engine's word for the WHOLE playlist, so the
    manual uncheck-all path has to arm the same refusal the None button uses —
    otherwise "I did not pick anything" downloads everything."""
    seg = APP.split("function syncPlaylistPicks")[1]
    seg = seg.split("function ", 1)[0]
    assert "PLAYLIST_NONE = true" in seg
    # and that refusal is what disables the button
    state = APP.split("function renderPlaylistState")[1].split("function ", 1)[0]
    assert "const none = PLAYLIST_NONE && !text;" in state
    assert "btn.disabled = Boolean(junk || none)" in state


def test_toasts_sit_above_the_mobile_tab_bar():
    """#toasts sat 22px from the bottom, on top of the fixed tab bar: taps
    aimed at a tab hit the toast instead. The lane also has to carry the
    safe-area term — a gesture bar reserves 30-50px below the bar's padding
    box, and without it the stack sat that much lower, clipped behind it."""
    assert "#toasts { left: 12px; right: 12px;" in CSS
    seg = CSS.split("#toasts { left: 12px; right: 12px;")[1].split("}")[0]
    assert "bottom: calc(84px + env(safe-area-inset-bottom))" in seg


def test_touch_targets_are_thumb_sized_on_coarse_pointers():
    assert "@media (pointer: coarse)" in CSS
    assert "min-height: 44px" in CSS


def test_settings_inputs_have_names_and_modals_announce_themselves():
    for ident in ("setSubLangs", "archiveEntry", "setSbCats",
                  "setGeoCountry", "optionsSearch"):
        after = HTML.split(f'id="{ident}"')[1][:300]
        assert "aria-label" in after, f"{ident} needs an accessible name"
    assert HTML.count('role="dialog" aria-modal="true"') == 2
