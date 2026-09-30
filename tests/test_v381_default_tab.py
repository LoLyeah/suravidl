"""v0.38.1 — quit and reopen lands on Download.

The app used to boot on the tab you left it on (localStorage "suravidl.tab").
The report: "After I quit, and opened the app again, can you make download
as the default page?" — so the remembered-tab restore is gone. The hash
stays a real address: a URL that names a tab (#settings in a bookmark or a
link) still opens it, and a mid-session reload still lands where you were.
"""
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "src" / "suravidl_engine" / "web" / "app.js").read_text()


def test_the_remembered_tab_is_gone():
    assert "suravidl.tab" not in APP
    assert "TAB_KEY" not in APP


def test_boot_lands_on_download():
    assert 'showTab(TABS.includes(want) ? want : "download", { keepScroll: true });' in APP


def test_the_hash_is_still_a_real_address():
    # a URL that names a tab still opens it...
    assert "location.hash.slice(1)" in APP
    # ...and showTab keeps the address in step
    assert 'history.replaceState(null, "", "#" + target)' in APP
