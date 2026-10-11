"""v0.46.7 "the brief" — the queue answers its own question (critique round 2).

Top 3 + the carried-over P2s:
P1 — no summary layer; the queue landed failure-first. Now: counts on the
chips, one mono state line with state dots, and the ordering ranks
running → filed → failures (gathered under a quiet caption).
P1 — the raw engine line was visible by default. Now: closed behind the
one Show details toggle that also owns its state (the desync is gone).
P2 — destructive verbs euphemized: 'Clear filed' → 'Delete filed files',
and the confirms name the disk consequence; fileless rows stop borrowing
the gravity.
P2 (carried) — the fold desync + its cluster: one flip() owning class +
row + aria + the receipt's a11y membership; a drawn caret affordance;
badge title/aria-label; and the --dim→--muted contrast fix (4.22:1 → pass).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text(
    encoding="utf-8")
CSS = (ROOT / "src" / "suravidl_engine" / "web" / "style.css").read_text(
    encoding="utf-8")
HTML = (ROOT / "src" / "suravidl_engine" / "web" / "index.html").read_text(
    encoding="utf-8")
NLBRACE = "\n}"


def test_the_chips_carry_counts_and_the_state_line_speaks():
    seg = APP[APP.index("function renderQueueActions("):]
    seg = seg[:seg.index(NLBRACE)]
    assert "counts[b.dataset.qfilter]" in seg
    assert 't(b.dataset.i18n || b.textContent)' in seg
    assert '"queueState"' in seg and "nothing running" in seg
    assert '"sdot " + tone' in seg
    assert 'id="queueState"' in HTML


def test_success_leads_and_failures_gather_under_a_caption():
    seg = APP[APP.index("const rank = (j) =>"):]
    seg = seg[:seg.index("renderBins")]
    assert 'b === "active" ? 0 : b === "filed" ? 1 : 2' in seg, \
        "running first, then filed, then failures"
    assert '"jgroup"' in APP
    assert "box.insertBefore(g, firstFailed)" in APP
    # the caption hides under any filter but All
    assert 'g.classList.toggle("hidden", QFILTER !== "all")' in APP


def test_the_raw_line_is_closed_by_default_and_one_toggle_owns_it():
    seg = APP[APP.index('} else if (j.status === "error" || j.status === "interrupted") {'):]
    seg = seg[:seg.index("const errText")]
    assert "errEl.hidden = true" not in seg  # hidden is set after the build
    seg2 = APP[APP.index("const errText = j.error || \"\";"):]
    seg2 = seg2[:seg2.index("const copy = el")]
    assert "errEl.hidden = true" in seg2, "closed by default"
    assert "errEl.onclick" not in seg2, "the text's own tap desynced the two"
    assert 'const open = more.getAttribute("aria-expanded") !== "true"' in seg2, \
        "one owner reads and writes one state"
    assert "errEl.hidden = !open" in seg2
    assert ".jerr[hidden] { display: none; }" in CSS, \
        "[hidden] must beat .clamp's display"


def test_the_human_sentence_carries_the_only_rose():
    assert ".jerrsay { margin-top: 8px; font-size: 13px; color: var(--err); }" in CSS
    seg = CSS[CSS.index(".jerr {"):]
    seg = seg[:seg.index("}")]
    assert "var(--muted)" in seg, "the machine dialect is neutral now, not a second alarm"


def test_destructive_words_name_the_disk():
    assert 't("Delete filed files ({n})"' in APP
    assert "Clear filed ({n})" not in APP, "the euphemism is retired"
    assert 't("Delete the {n} filed files?", { n: filed.length })' in APP
    assert 't("They leave your downloads folder.")' in APP
    assert 't("The file on disk goes too.")' in APP
    seg = APP[APP.index("const msg = (running ?"):]
    seg = seg[:seg.index("if (!(await askConfirm(msg")]
    assert '(j.filepath || running ? " " + t("This cannot be undone.") : "")' in seg, \
        "fileless rows stop borrowing the gravity"


def test_the_fold_has_one_owner_and_a_drawn_caret():
    seg = APP[APP.index("const flip = () => {"):]
    seg = seg[:seg.index("row.onclick")]
    assert 'title.classList.toggle("open", open)' in seg
    assert 'row.classList.toggle("open", open)' in seg
    assert 'aria-expanded' in seg
    assert "removeAttribute(\"aria-hidden\")" in seg
    assert 'details.setAttribute("aria-hidden", "true")' in APP
    assert 'id="i-chev"' in HTML, "a drawn caret, never a glyph"
    assert ".job.open .jobtitle .chev { transform: rotate(180deg); }" in CSS


def test_the_badge_says_what_it_counts():
    seg = APP[APP.index("function renderQueueBadge("):]
    seg = seg[:seg.index(NLBRACE)]
    assert 't("{n} downloads running", { n: active })' in seg
    assert 't("{n} downloads failed", { n: failed })' in seg
    assert 'badge.setAttribute("aria-label", why)' in seg


def test_the_dim_token_left_the_record_texts():
    for rule in (".job .jmeta.settled { margin-top: 6px; color: var(--muted);",
                 ".jdetails .jdlbl { color: var(--muted); }"):
        assert rule in CSS, rule
    seg = CSS[CSS.index(".job .path {"):]
    seg = seg[:seg.index("}")]
    assert "color: var(--muted)" in seg


def test_the_brief_speaks_indonesian_too():
    for pair in ('"nothing running": "tidak ada yang berjalan"',
                 '"The file on disk goes too.": "Berkas di disk ikut terhapus."',
                 '"Delete filed files ({n})": "Hapus berkas selesai ({n})"'):
        assert pair in APP, pair
