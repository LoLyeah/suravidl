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


def test_the_storage_row_and_the_delete_dialog_cannot_disagree():
    """"Downloaded files: 2 files · 73.2 MB" sat above a confirm reading
    "Delete 0 files (0 B)" — both read /files/summary, but the row was only
    ever fetched once at init, so any delete done from another tab left it
    lying. It must re-read when Settings comes into view and after a per-job
    delete, and with nothing on disk the dialog must not open at all."""
    assert "refreshStorageInfo = show" in APP, "the row is never wired for re-read"
    # re-read on tab open (alongside the settings load) and after the trash button
    assert 'if (target === "settings" && refreshStorageInfo) refreshStorageInfo();' in APP
    after_delete = APP.split("toast(r.deleted")[1][:400].split("refreshJobs();", 1)[1]
    assert "if (refreshStorageInfo) refreshStorageInfo();" in after_delete
    # and no destructive dialog over an empty folder — both delete buttons run
    # the one flow, which re-reads the folder and refuses before asking
    flow = APP.split("const clearFiles = async (keepGallery)")[1]
    before_dialog = flow.split("askConfirm")[0]
    assert 'toast("nothing to delete")' in before_dialog
    assert "s.files === 0" in before_dialog
    assert '$("clearDownloadsBtn").onclick = () => clearFiles(false)' in APP
    assert '$("clearAppCopiesBtn").onclick = () => clearFiles(true)' in APP


def test_app_copies_only_keeps_the_gallery_copy():
    """"Add a button to delete only the downloaded files in the app's folder
    but not the copy to the gallery" (2026-09-26). /files/clear only ever
    empties the app's own folder; the Gallery/Music copies are removed by a
    separate host call — so this path must not make it, and both the confirm
    and the toast must say the copies stay."""
    assert 'id="clearAppCopiesBtn"' in HTML
    assert "hidden" in HTML.split('id="clearAppCopiesBtn"')[1][:120], \
        "the button starts hidden: browser builds write no gallery copy"
    assert 'if (GALLERY()) $("clearAppCopiesBtn").classList.remove("hidden")' in APP
    assert "if (!keepGallery && ANDROID() && window.AndroidHost.deleteMediaCopies)" in APP, \
        "only the full delete may touch the Gallery/Music copies"
    assert "The Gallery/Music copies stay." in APP
    assert "Gallery/Music copies kept" in APP


def test_toasts_sit_above_the_mobile_tab_bar():
    """#toasts sat 22px from the bottom, on top of the fixed tab bar: taps
    aimed at a tab hit the toast instead. The lane must carry the safe-area
    term — and since v0.38.2 it is adaptive: idle tabs dock at bar + 12px,
    furniture tabs (transport, Save strip) at bar + 84px."""
    assert "#toasts { left: 12px; right: 12px;" in CSS
    seg = CSS.split("#toasts { left: 12px; right: 12px;")[1].split("}")[0]
    assert ("bottom: calc(var(--tabbar-h) + 12px + env(safe-area-inset-bottom) "
            "+ var(--toast-lift, 0px))" in seg)
    # the lift over docked furniture is measured (syncToastLane), not a
    # static per-tab rule (v0.38.2)
    assert 'body[data-tab="download"] #toasts' not in CSS
    assert "function syncToastLane()" in APP


def test_touch_targets_are_thumb_sized_on_coarse_pointers():
    assert "@media (pointer: coarse)" in CSS
    assert "min-height: 44px" in CSS


def test_settings_inputs_have_names_and_modals_announce_themselves():
    for ident in ("setSubLangs", "archiveEntry", "setSbCats",
                  "setGeoCountry", "optionsSearch"):
        after = HTML.split(f'id="{ident}"')[1][:300]
        assert "aria-label" in after, f"{ident} needs an accessible name"
    # 6 dialogs: the player, the confirm sheet, the folder sheet, the
    # What's new card (2026-09-28) — plus the FAQ card and the tour's caption
    # (v0.39.4); every one of them announces itself
    assert HTML.count('role="dialog" aria-modal="true"') == 6


def test_the_cache_has_its_own_button_and_the_deletes_do_not_touch_it():
    """v0.24.9 folded the cache sweep into both file deletes ("the app cache
    was the piece with no owner", and the hint had to explain the side
    effect); the 2026-09-28 ask undid exactly that. Each button now does one
    visible thing, and the cache flow makes its own promise."""
    assert 'id="storageCache"' in HTML
    assert '$("storageCache").textContent' in APP
    assert 'id="clearCacheBtn"' in HTML and '$("clearCacheBtn").onclick' in APP
    assert '"/cache/clear"' in APP
    # the file deletes no longer bundle it, and nothing claims they do
    assert "The app cache is cleared too." not in APP
    assert "Both also clear the app cache" not in HTML
    flow = APP.split("const clearFiles = async (keepGallery)")[1].split('$("clearCacheBtn")')[0]
    assert "cacheBytes" not in flow, "the file path must not reason about the cache"
    # a cache-only clear asks with a verb that fits it and a promise it keeps
    cache_flow = APP.split('$("clearCacheBtn").onclick')[1][:800]
    assert 'okText: "Clear"' in cache_flow
    assert "nothing downloaded is touched" in cache_flow
