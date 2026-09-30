"""v0.37.0 — The Post House: the replacement world, pinned.

The redesign keeps every behavior contract the earlier suites lock, and adds
the new world's own: a self-hosted instrument language (no aurora, no emoji
glyphs, drawn SVG icons), the two journey ends the critique found —
**choosing vs downloading** (controls arm a take; only the transport START
commits) and **a finish that speaks** (FILED stamp + one completion toast with
Play / Show folder) — plus the newcomer aids: scope strip, bins rail, and
human-first error lines with the machine text behind a toggle.

Colour: every small-text token clears 4.5:1 against its own theme ground.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "src/suravidl_engine/web"
APP = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def _fn(name):
    assert "function " + name in APP, name + " is gone"
    return APP.split("function " + name, 1)[1].split("\nfunction ", 1)[0]


# --- the world -------------------------------------------------------------

def test_the_aurora_is_replaced_by_the_room():
    """The old world: three 70px-blurred radial gradients drifting under every
    surface. The Post House is a lit room — one lamp glow, no drift, no blur."""
    assert "keyframes drift" not in CSS, "the aurora still drifts"
    assert "filter: blur(70px)" not in CSS
    assert "room-lamp" in CSS or "--lamp" in CSS


def test_faces_ship_with_the_app():
    """Zero @font-face rules shipped before: most machines rendered the whole
    design in system fonts. The faces are now self-hosted woff2."""
    assert "@font-face" in CSS
    for fam in ("Archivo", "Martian Mono"):
        assert fam in CSS
    assert "/static/fonts/" in CSS
    assert "fonts.googleapis.com" not in HTML + CSS
    for f in ("archivo-var.woff2", "martian-mono-var.woff2"):
        assert (WEB / "fonts" / f).is_file(), f


def test_icons_are_drawn_not_borrowed_glyphs():
    """Emoji as iconography in a system that specifies one type family: on
    Android they render in a different font — in the shell that is most
    visible. Icons are SVG symbols in one stroke."""
    assert 'id="i-' in HTML, "no icon sprite"
    assert 'use href="#i-' in HTML or "use href='#i-" in HTML or 'href="#i-' in HTML
    glyphs = "🔍🗑🔋⏻⬇☰⌥⚙●✓✕↗"
    for g in glyphs:
        assert g not in HTML, f"{g} still in the markup"
        assert g not in APP, f"{g} still in app.js"


def test_the_markup_carries_the_room(tmp_path=None):
    """ids the new world adds — every one is wired in app.js."""
    for elem_id in ("scopeStrip", "scopeSrc", "scopeFmt", "scopeSize",
                    "scopeSay", "binsRail", "binsList", "binsCount",
                    "takeSay", "studioBtn", "probeSay", "probeDetails"):
        assert f'id="{elem_id}"' in HTML, elem_id


# --- journey end 1: choosing vs downloading --------------------------------

def test_chips_arm_a_take_and_never_start():
    """Eleven controls each fired a download on one tap; only `Get` said so.
    Selection is now an arm step — the transport START is the one committer."""
    q = _fn("renderQualityRow")
    assert "armTake" in q and "startJob" not in q, "quality chips still start jobs"
    assert "function armTake(" in APP and "function commitTake(" in APP
    assert "let TAKE = {" in APP
    # the format table's Get is an arm too
    rp = _fn("renderProbe")
    assert "armTake" in rp, "format rows still start jobs"
    assert "bestBtn" in _fn("commitTake"), "the transport lamp is not the committer"


def test_the_transport_says_what_it_will_start():
    assert '"START · "' in APP, "the lamp does not name the take"
    assert "function renderTake(" in APP and "takeSay" in _fn("renderTake")


def test_the_audio_picks_arm_too():
    assert 'armTake("audio-m4a"' in APP
    assert 'armTake("audio-native"' in APP
    assert 'armTake("audio-mp3"' in APP
    # and the more-formats select arms instead of firing
    seg = APP.split('$("audioMore").onchange', 1)[1].split("\n};", 1)[0]
    assert "armTake" in seg and "startJob" not in seg


def test_a_commit_spends_the_take():
    """One-shot, like the per-download block: after the job starts the chips
    are clear again and the NEXT download does not inherit a stale pick."""
    c = _fn("commitTake")
    assert "TAKE.fmt = null" in c and "TAKE.preset = null" in c
    assert "renderTake()" in c


def test_the_armed_strip_still_rides():
    """v0.35's contract kept: the strip names what rides the next download."""
    assert "next download:" in _fn("renderOvCount")


# --- journey end 2: a finish that speaks -----------------------------------

def test_a_completed_download_speaks():
    """A finished download turned a pill green in a tab you were not on."""
    assert "let JOB_STATE = new Map()" in APP
    fn = _fn("onFiled")
    assert "Play" in fn and "Show folder" in fn
    assert "toast(" in fn


def test_the_finish_stamps_the_row():
    assert 'el("span", "stamp", "FILED")' in APP or '"FILED"' in APP
    assert ".job .stamp" in CSS


def test_the_bins_rail_collects_the_takes():
    assert "function renderBins(" in APP
    seg = _fn("refreshJobs")
    assert "renderBins(" in seg, "the poll never repaints the bins"


# --- newcomer aids ---------------------------------------------------------

def test_the_probe_landing_fills_the_scopes():
    assert "function setScopes(" in APP
    assert 'setScopes("scan"' in APP
    assert 'setScopes("bad"' in APP
    rp = _fn("renderProbe")
    assert "setScopes(" in rp


def test_errors_lead_with_the_human_consequence():
    assert "function humanErr(" in APP
    assert "humanErr(" in APP.split("async function doProbe")[1].split("\nfunction ")[0]
    eb = APP.split('} else if (j.status === "error" || j.status === "interrupted") {', 1)[1]
    eb = eb.split("} else if (j.filepath)")[0]
    assert "humanErr(" in eb, "a failed job row leads with machine text"


# --- colour: the floor, computed -------------------------------------------

def _theme_block(theme):
    anchor = f'html[data-theme="{theme}"]'
    return CSS.split(anchor, 1)[1].split("}", 1)[0]


def _token(block, name):
    m = re.search(rf"--{name}:\s*([^;]+);", block)
    assert m, f"--{name} missing"
    return m.group(1).strip()


def _rgb(value):
    value = value.strip()
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(rgb):
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _over(fg_rgba, bg):
    """Alpha-composite an rgba()/hex string over an opaque rgb tuple."""
    m = re.match(r"rgba?\(([^)]+)\)", fg_rgba)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        r, g, b = (int(float(parts[i])) for i in range(3))
        a = float(parts[3]) if len(parts) > 3 else 1.0
    else:
        r, g, b = _rgb(fg_rgba)
        a = 1.0
    return tuple(round(r * a + bg[i] * (1 - a)) for i, c in enumerate((r, g, b)))


def test_every_theme_holds_the_contrast_floor():
    for theme in ("dark", "light", "amoled"):
        b = _theme_block(theme)
        bg = _rgb(_token(b, "bg"))
        for tok in ("text", "muted", "dim", "ph"):
            r = _ratio(_rgb(_token(b, tok)), bg)
            assert r >= 4.5, f"{theme} --{tok} is {r:.2f}:1"
        # the armed strip: accent-ink over accent-soft over the ground
        strip = _over(_token(b, "accent-soft"), bg)
        ink = _rgb(_token(b, "accent-ink"))
        r = _ratio(ink, strip)
        assert r >= 4.5, f"{theme} accent-ink on the strip is {r:.2f}:1"


# --- the floors held from before -------------------------------------------

def test_the_browser_surfaces_carry_the_palette():
    assert "::selection { background: var(--sel" in CSS
    assert "caret-color: var(--accent)" in CSS
    assert "scrollbar-width: thin; scrollbar-color: var(--dim) transparent" in CSS
    assert "font-variant-numeric: tabular-nums" in CSS


def test_coarse_pointers_get_real_targets():
    assert "@media (pointer: coarse)" in CSS
    block = CSS.split("@media (pointer: coarse)", 1)[1].split("@media", 1)[0]
    assert "44px" in block


def test_focus_is_visible_on_every_control():
    """`.get` and `.stab` fell back to a near-black UA ring on the near-black
    page (critique). They join the focus group."""
    seg = CSS.split(":focus-visible", 1)[1].split("}", 1)[0]
    for sel in (".get", ".stab", ".linkbtn"):
        assert sel in seg, sel


def test_the_smoked_glass_is_material_not_decoration():
    """The brief's glass lives on as the instrument face: frosted/polished map
    to blur + bevel + gloss on readout plates — but the page's own ground does
    not fade out behind it (no full-page glass overlay)."""
    assert "html[data-glass=" in CSS
    assert "backdrop-filter" in CSS
    assert "@supports not" in CSS  # fallback when blur is unavailable
