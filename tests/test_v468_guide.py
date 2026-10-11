"""v0.46.8 "the guide" — three field reports from the phone, one batch.

1. The watch list's cold start: an add-by-URL row that works from zero, and
   a numbered three-step how-to shown only while the list is empty.
2. The follow button rendered as a giant black star on Android: the icon
   used class "ic" — a class that never existed — so the SVG was unsized;
   and the symbol carried no fill, so it painted default black. Both fixed
   to the house pattern (span.ico + paint on the symbol tag).
3. No highlight on the audio-only picks: renderTake lights [data-pick]
   buttons with .picked, but the look was scoped to .qrow — the audio row
   and the format rows lit nothing. The look is now top-level, and the
   transport take for keep-original reads "audio" (it truncated to
   "audio · k…" on a phone; the START button spells the full take).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(
    encoding="utf-8")
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")


def test_the_star_is_a_house_icon_now():
    assert 'class="ic"' not in HTML, "the phantom class is retired"
    assert ('<button id="followBtn" class="btn sm"><span class="ico">'
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<use href="#i-star"/></svg></span>') in HTML
    assert '<symbol id="i-star" viewBox="0 0 24 24" fill="currentColor">' in HTML
    assert '<symbol id="i-chev" viewBox="0 0 24 24" fill="currentColor">' in HTML


def test_the_picked_light_reaches_the_audio_row():
    assert ".qrow .btn.picked, .btn.picked {" in CSS
    seg = CSS[CSS.index(".qrow .btn.picked, .btn.picked {"):]
    seg = seg[:seg.index("}")]
    assert "var(--accent-soft)" in seg and "var(--accent-line)" in seg


def test_the_take_reads_audio_not_a_truncation():
    seg = APP[APP.index("function renderTake()"):]
    seg = seg[:seg.index("function commitTake")]
    assert 'TAKE.label === "keep original" ? t("audio")' in seg
    assert 'b.setAttribute("aria-pressed", on ? "true" : "false")' in seg
    assert 't("audio · {label}", { label: t(TAKE.label) })' in seg


def test_the_watch_list_adds_from_zero():
    assert 'id="followUrl"' in HTML and 'id="followAddBtn"' in HTML
    assert 'data-i18n-ph="Paste a playlist or channel link"' in HTML
    seg = APP[APP.index("if ($(\"followAddBtn\")) {"):]
    seg = seg[:seg.index("if ($(\"followBtn\")) {")]
    assert 'api("/follows", { method: "POST"' in seg
    assert 'e.key === "Enter"' in seg, "Enter is the desk's habit too"
    assert "await renderFollows()" in seg


def test_the_how_to_shows_only_at_the_cold_start():
    assert 'id="followsHow"' in HTML
    for n, frag in ((1, "Probe a playlist or channel link"),
                    (2, "everything already in it is marked seen"),
                    (3, "checks run while the app does")):
        assert f'<span class="fh-n">{n}</span>' in HTML
        assert frag in HTML, frag
    assert ('$("followsHow").classList.toggle("hidden", FOLLOWS.length > 0)'
            in APP)


def test_api_reads_never_ride_a_cache():
    assert 'fetch(path, { cache: "no-store", ...opts, headers: H() })' in APP


def test_the_guide_speaks_indonesian_too():
    for pair in ('"Nothing followed yet — how it works:": "Belum ada yang diikuti',
                 '"Paste a playlist or channel link": "Tempel tautan daftar putar'):
        assert pair in APP, pair
