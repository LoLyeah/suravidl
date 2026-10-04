---
name: suravidl
description: "The Post House — an ingest room: graphite ground, smoked-glass plates, signal amber or the pine & cream voice for action, scope green for state"
colors:
  graphite-ground: "#0f1216"
  day-room: "#e7e4de"
  off-room: "#000000"
  film-white: "#e8eaed"
  slate-mist: "#a8b1bd"
  slate-dim: "#7f8a97"
  signal-amber: "#e8a33e"
  lamp-full: "#f3c169"
  amber-ink: "#f0c98a"
  pine-voice: "#14493C"
  cream-voice: "#F2E9D8"
  scope-green: "#4ecf83"
  tally-rose: "#ff8078"
  smoked-glass: "rgba(232, 236, 240, 0.05)"
  smoked-glass-strong: "rgba(232, 236, 240, 0.09)"
  ink-well: "rgba(4, 6, 8, 0.45)"
  panel-solid: "#14181d"
  lamp-glow: "rgba(232, 163, 62, 0.10)"
  darwin-wash: "rgba(15, 18, 22, 0.88)"
typography:
  title:
    fontFamily: "Archivo, system-ui, -apple-system, sans-serif"
    fontSize: "15.5px"
    fontWeight: 700
  body:
    fontFamily: "Archivo, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.1px"
  label:
    fontFamily: "Archivo, system-ui, -apple-system, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    letterSpacing: "0.09em"
  mono:
    fontFamily: "'Martian Mono', ui-monospace, Menlo, monospace"
    fontSize: "12.5px"
    fontWeight: 400
  readout:
    fontFamily: "'Martian Mono', ui-monospace, Menlo, monospace"
    fontSize: "19px"
    fontWeight: 600
    letterSpacing: "-0.02em"
rounded:
  sm: "8px"
  md: "9px"
  lg: "13px"
  xl: "16px"
  surface: "20px"
  toast: "12px"
  bay: "14px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "14px"
  lg: "18px"
  xl: "22px"
components:
  button-primary:
    backgroundColor: "{colors.signal-amber}"
    textColor: "#1a1305"
    rounded: "{rounded.md}"
    padding: "12px 22px"
  button-primary-hover:
    backgroundColor: "{colors.lamp-full}"
  button-glass:
    backgroundColor: "{colors.smoked-glass}"
    textColor: "{colors.film-white}"
    rounded: "{rounded.md}"
    padding: "9px 15px"
  chip:
    backgroundColor: "{colors.smoked-glass}"
    textColor: "{colors.slate-mist}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  input:
    backgroundColor: "{colors.ink-well}"
    textColor: "{colors.film-white}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
  card:
    backgroundColor: "{colors.smoked-glass}"
    rounded: "{rounded.surface}"
    padding: "18px"
---

# Design System: suravidl

## Overview

**Creative North Star: "The Post House"**

suravidl is an ingest room: you bring footage in, the scopes read it out loud,
you set what you're taking, one lamp starts the run, and finished takes get
stamped FILED and shelved in the bins. The room is cool graphite at night and
brushed aluminium with paper tape by day — a working post house, not a
showroom. Every surface is a smoked-glass instrument plate with a hairline
edge and one inset highlight; the only warm light in the room is the practical
lamp above the deck, and amber is what that lamp is made of: the START button,
the active tab's underline, an LED going live, the selection you just made.
The lamp has a second colour the user can choose — **pine & cream**, the
brand's own voice — and nothing else in the room changes with it.

The mood is calm and operational. An instrument, so numbers are the point:
every readout — scope values, file sizes, durations, versions, paths — is set
in a mono voice, and instrument vocabulary (scopes, tally lights, the
transport, the patch bay) names the parts. But it is an instrument for
people: one obvious button starts the work, errors are written in sentences
before they are written in stack traces, and a finished download says so.

**Key Characteristics:**
- Dark-first; light is the room at day (brushed alu + paper tape), AMOLED is
  the room with the lights off (true #000). One token set, three values.
- Smoked glass over one soft room lamp — a single radial glow, no
  background blur layer (the old three-radial aurora cost phones battery
  for decoration).
- One action light, two voices: signal amber (the house lamp) by default,
  or the pine & cream scheme — fills, borders, glows and washes all follow
  the accent; the three state lights (scope green / tally rose / warm
  amber) only ever carry state and never repaint with it.
- Two voices, both shipped with the app: Archivo for prose, Martian Mono for
  every machine readout.
- Machine-instrument shapes: 8–14px controls, 20px floating plates; pills for
  state. Nothing sharper than 8px, nothing rounder than a pill.
- Motion stays under half a second; reduced-motion stops it — never shortens it.
- On macOS the room itself is Apple's real glass: the page sits on Liquid
  Glass / vibrancy through a transparent window, behind a near-opaque wash
  of the theme's tone — the desktop reads as a hint, never as the background.

## Colors

A film-lab palette: graphite ink, film-white text, and the amber of a single
practical lamp, plus three honest state lights. The dark theme is normative;
light and AMOLED re-value the same roles (light darkens amber to #c07a16 with
#6b4308 as its ink so small amber text keeps 4.5:1; AMOLED sets the ground to
true #000 and drops shadows for hairlines). The accent has two voices —
signal amber and the pine & cream scheme; the state lights are signals, not
brand, and never follow it.

### Primary
- **Signal Amber** (#e8a33e): the action colour — the START and Probe fills,
  the active tab underline, LEDs in live states, the selection wash, the
  unsaved-settings dot. In light theme: #c07a16.
- **Lamp Full** (#f3c169): amber at full — hover on the primary fill only.
- **Amber Ink** (#f0c98a): amber as text — link buttons, readouts in an armed
  state, "this download only" markers. In light theme: #6b4308.
- **Pine & Cream — the scheme's second voice** (scheme `pine`): the same
  accent roles, re-valued in two tones. Light room: pine #14493C with cream
  #F2E9D8 as its ink. Dark and AMOLED rooms flip the chip: cream #F2E9D8
  with pine #14493C ink — dark pine sinks to 1.8:1 on graphite, the same
  measured swap the mark's theme twins make.

### Secondary (status)
- **Scope Green** (#4ecf83): good — completed pills, live scope LEDs, the
  FILED stamp, good messages.
- **Tally Rose** (#ff8078): refused — errors, failed probes, destructive
  actions, the human error line on a failed row.
- **Warm Amber** (amber again, at line weight): attention — paused/cancelled,
  warnings, "engine unreachable".

### Neutral
- **Graphite Ground** (#0f1216): the room. Light: #e7e4de. AMOLED: #000000.
- **Film White** (#e8eaed): primary text.
- **Slate Mist** (#a8b1bd): muted text — labels, hints, secondary copy.
- **Slate Dim** (#7f8a97): dim text — metadata, versions, placeholders.
- **Smoked Glass** (rgba(232,236,240,.05)): the glass of every plate, header
  and button; Strong (…,.09) for bars and hover fills.
- **Ink Well** (rgba(4,6,8,.45)): input wells — darker than the room, so
  fields read as recessed.
- **Panel Solid** (#14181d): the one honest slab — toasts and flattened
  surfaces where reading beats atmosphere.
- **Darwin Wash** (rgba(15,18,22,.88) at night): the page's own wash on the
  native macOS shell — the desktop shows through as a hint, never as ground.

### Named Rules
**The One Lamp Rule.** Each plate has at most ONE filled amber control; every
other appearance of amber in that region is a hairline, a glow, an underline
or an LED. Two filled amber buttons side by side is a signal failure.

**The Live-Light Rule.** Amber/Green/Rose never decorate: an LED is lit only
while its state is true (live, armed, filed, refused), and glow follows power
— lit LEDs glow faintly, dark ones don't.

**The Two Voices Rule.** The scheme switch re-values the accent family alone
— fills, hairlines, glows, the selection wash and the room lamp all ride the
accent tokens; the neutrals and the three state lights never repaint with it.

## Typography

**UI Font:** Archivo (variable, weight 100–900, OFL, **self-hosted** —
`fonts/archivo-var.woff2`, latin subset)
**Readout Font:** Martian Mono (variable, OFL, self-hosted —
`fonts/martian-mono-var.woff2`)

**Character:** One grotesque in a tight, app-sized band; hierarchy is carried
by weight, case and colour, not size. Mono is the instrument voice: it is
slightly WIDER and more present here than a decorative mono — readouts are the
product.

### Hierarchy
- **Title** (700, 15–16px): card titles and probe headings.
- **Body** (400, 14px, line-height 1.5): controls, inputs, descriptions.
- **Label** (600, 10–11px, letter-spacing .09–.14em, uppercase): scope names
  (10px), card kickers, section heads — small, spaced, quiet by design.
- **Small** (400, 12–12.5px): hints, footnotes, counters.
- **Readout / Mono** (400–600, 12–19px): scope readings — the largest mono in
  the app at 19px/600 — sizes, durations, paths, versions, error bodies,
  file names.

### Named Rules
**The Machine Voice Rule.** Anything a machine produced or consumes — sizes,
paths, versions, durations, error bodies, flags — is set in Martian Mono.
Prose stays in Archivo. A number presented as information is machine voice.

**The Quiet Label Rule.** Section labels never grow. If a section needs more
emphasis, change the content's weight or colour, not the label's size.

## Layout

A deck and a rail. The header strip (mark + wordmark + engine/yt-dlp version
meta in mono) sits over a content column; at ≥1080px a FILED TAKES rail
(newest first, count badge) stands beside it. The tab strip is a top row on
desktop and a fixed bottom bar under 900px (thumb reach, safe-area padding).
The scope strip is three readouts across the top of the deck. The transport —
what you're taking and the one button that starts it — is in-flow at the
deck's end on desktop (sticky bottom 14px) and a sticky bar parked above the
tab bar on phones (download tab only). Sticky, never fixed: this WebView
composites the backdrop pass in flow but not for fixed layers over scrolling
content (device photo, 2026-10-01), and in flow the bar can never overlap
the page's end. The patch bay ("This download only") sits under
the deck; Settings is a tab panel with sub-tabs and a sticky Save bar that
keeps the plate's glass and its bottom corners. Under the deck's footer sits
the meta row — the saved-to path in mono with copy / open, and the two
doors: FAQ answers the common questions, and a replayable tour walks the
room.

Spacing stays on a compact rhythm — 6 / 10 / 14 / 18 / 22px. Cards stack with
16px gaps; controls in a row breathe with 10–14px.

### Named Rules
**The Stable Shell Rule.** The shell never scrolls away: header and tab strip
stick, the mobile tab bar is fixed, the phone transport rides sticky above
it — parked while the deck scrolls, scrolling home with the deck's end.
Content moves; the instrument panel stays put.

**The Read-Before-Start Rule.** The deck's order is fixed: source → scopes →
take → START, then options. Nothing that acts on a probe may sit above it, and
a control that shapes a download must be visible next to the control that
starts it (the armed take lives on the transport, not in a collapsed block).

## Elevation & Depth

Ambient soft-lift over one room lamp. Depth is carried by translucency first —
smoked glass plates with a 1px inset highlight (the glass's wet edge) — and by
one deep diffuse shadow (dark: `0 26px 60px rgba(0,0,0,.55), 0 2px 10px
rgba(0,0,0,.35)`) that lifts the plate family off the room. Shadows are
ambient, never structural. On AMOLED the shadow drops to none and hairlines
take over; the light theme's shadow warms and softens. Toasts deliberately sit
on a near-opaque plate (Panel Solid) so text never fights the blur.

### Glass styles (the material system)
One material, two finishes. Every plate is a thin translucent fill over a
real `backdrop-filter` pass — the room and the content behind it stay
visible, and that visibility IS the material. Five parts, always the same:
fill (`--glass-bg`, `-strong` for bars), blur (`--glass-blur`), gloss image
(`--glass-gloss`, liquid only), hairline (`--glass-border`), and one inset
top highlight (`--glass-hi` — the glass's wet edge). Change the material by
changing tokens, never surface by surface.

- **Frosted (smoked) — the default:** `blur(14px) saturate(115%)`, no gloss,
  `--line` hairline, `--inset-hi` highlight. Matte smoked glass: the
  workhorse.
- **Liquid (polished):** `blur(26px) saturate(165%) brightness(1.04)`, a
  specular gloss at 150° (`rgba(255,255,255,.14) → .02 45% → .08`), a
  brighter top highlight (`rgba(255,255,255,.24)`), and `--accent-line`
  borders. Content behind it visibly smears; the panel reads wet.
- **Host deltas (Android):** the same tokens at a lighter radius — frosted
  `blur(11px) saturate(120%)`, liquid `blur(19px) saturate(165%)
  brightness(1.04)` with an accent-tinted gloss and a `.22` highlight. The
  shell may lighten the radius; it NEVER loses the material — this WebView
  composites `backdrop-filter` correctly in flow. Two device realities
  (measured against photos, 2026-10-01): the full-screen overlay keeps the
  dense v0.36 veil `rgba(3,5,12,.72)`, and the transport pours dense —
  85% panel-solid via `color-mix` — because this WebView does not composite
  the backdrop pass for floating plates in EITHER geometry (fixed or
  sticky): page text stays crisp through the glass. The blur declarations
  stay on both; a WebView that composites lights them up, and until then
  the pour carries the plate. Where a WebView truly cannot blur, the
  `@supports` block turns every plate solid — a fake half-glass never
  ships.
- **The native shell (macOS):** the window is transparent and the whole page
  rides Apple's real material — Liquid Glass (`NSGlassEffectView`) on
  macOS 26+, vibrancy (`NSVisualEffectView`) on older releases. The page
  carries a near-opaque wash of the theme's tone (`--darwin-wash`: graphite
  `rgba(15,18,22,.88)`, day-room `rgba(231,228,222,.90)`, AMOLED
  `rgba(0,0,0,.88)`). Alpha ≥ .86 is the contrast floor — even a white
  wallpaper spot keeps body text at 4.5:1 — and the desktop stays a blur
  you can feel more than see. Plates keep their tints, blur and hairlines
  on top of the wash; the material reads through, the page never sits bare
  on it.
- **Where it lands:** header, tab bar, cards, glass buttons, the scope
  strip, the patch bay, job rows, the transport, dialogs. A dialog's
  full-screen overlay frosts behind it too (`blur(10px) saturate(120%)`
  under the veil `rgba(4,6,9,.55)`) — the popup crisp, the room behind it
  at a smudge. (2026-10-01: the veil used to be a flat dim; the popup read
  as blur-less until it frosted.)
- **Flattened on purpose:** toasts (Panel Solid — reading beats atmosphere)
  and the phone's Settings Save strip (rows scroll beneath it). Both keep
  hairlines and radii so they still read as plates; solid is a legibility
  choice, never a fallback for ability.

### Named Rules
**The Real Glass Rule.** Every blurred surface ships `-webkit-backdrop-filter`
beside `backdrop-filter`, and unsupported engines fall back to SOLID panels
(@supports) — never a fake half-glass. Blur is a real material, not a tint.

**The Measured-Blur Rule.** Glass is judged on pixels, never by "can I
still read the text behind it" — smeared text at phone scale still reads as
text. Verify in three layers: computed values per style, the full alpha
stack, and one capture with real content passing behind the plate —
compared by edge energy (blurred vs crisp). A build that shipped working
blur keeps it until pixels prove otherwise.

**The Wash Rule.** The page never floats bare on the native material, and
the wash never drops below the contrast floor — deep enough that text holds
over any wallpaper, shallow enough that the desktop stays a hint behind the
glass.

**The AMOLED Hairline Rule.** Where there is no shadow (AMOLED), borders carry
all separation; never re-introduce grey shadows there.

## Shapes

Machined plates: 8–9px for buttons and fields, 12–13px for the transport and
toasts, 14px for the patch bay, 20px for cards, modals and the FILED stamp's
plate family; full pills (999px) for chips, status and the progress bar. The
app mark is a 30px rounded square (9px radius) in the theme's brand chip
carrying the letterform. Borders are 1px hairlines that strengthen to
accent-line on selection, focus or an armed state.

### Named Rules
**The Nothing Sharp Rule.** If it can be touched, it is rounded ≥8px. Radii
above 14px are reserved for surfaces that float over content, never for
inline controls.

**The Armed Means Lit Rule.** A selected pick (`.picked`) keeps its amber
edge and glow until the take is spent or replaced — and only ONE pick can be
lit at a time; the paint comes from the one render function that owns the
take.

## Components

Tactile instruments — machined glass you can press.

### The Transport (signature)
The deck's one starter: a TAKE readout in mono ("best available", or the
armed pick's label in amber ink), a Studio ghost button (opens the patch
bay), and the START lamp — the ONE amber fill of the region. Its label echoes
the take ("START · 720p"). Parked sticky above the phone tab bar; sticky at
the deck's end on desktop. Fired = spent: the take clears, every pick unlights,
the readout returns to "best available".

### Switchgear (picks)
Quality chips, format-row Take buttons and audio picks ARM — they never
start a download. Armed = `data-pick` match: amber border, faint wash. A
second tap disarms. Labels stay human ("this file" for a bare direct link).

### The Scope Strip
Three scopes — SOURCE · FORMATS · LARGEST — each a tiny uppercase label, an
LED, and a mono reading (the widest mono in the app). State is the strip's:
off (dim dashes, "feed the deck a link"), live (green LEDs, "take ready — set
the deck, press START"), bad (rose LEDs + a say line pointing at the error
above). The strip is read, not pressed.

### Buttons
- **Primary (`.btn.prime`):** the accent fill (amber by default; pine or
  cream under the pine scheme), dark scheme ink, 700, glow
  `0 10px 22px -10px var(--accent-glow)` + inset top light. One per plate.
- **Glass (`.btn`):** smoked fill over blur, hairline, film-white text;
  hover lifts the fill and warms the border (hover-capable pointers only).
- **Ghost (`.ghost-sm`):** transparent, hairline, muted; destructive variants
  carry tally rose. Row actions live here.
- **States:** press scales to .97; busy pulses (1.1s) and refuses pointers;
  disabled drops opacity and refuses transform; focus-visible is a 2px
  accent outline at 2px offset — everywhere, always.

### Job rows
Pill + (completed) FILED stamp; title link; mono meta (size · time · site);
path line in mono; actions Play / Copy / Retry / Delete (+ "Edit & retry").
A failed row leads with the human sentence in tally rose ("the site says this
link does not exist (404) — check it was copied whole"); the raw engine text
sits clamped behind "Show details". A live row's fill glides for exactly one
poll interval (1.1s linear) so it never stalls between polls. The title folds
open a receipt — the real bytes on disk and the saved path in mono — and the
open state rides an explicit row class (no `:has()`), so engines without it
still expand it.

### The FILED TAKES rail (≥1080px)
Newest takes first: bin title + mono file name, count badge in amber. The
rail is a shelf, not a second queue — its items open the take.

### Toasts
Near-opaque plate, 12px radius, a state dot (green / rose / amber), message
13px; choices wrap under the message. Completion toasts carry actions (Play /
Show folder). The lane is measured, never tuned: at every width it lifts
above what is actually docked at the bottom right now — the transport once it
pins, the settings Save strip while it is up — and falls back to just above
the tab bar on phones and the bottom corner on desktop.
The measured offset
IS the lane's bottom edge — it wins over the fallback, it never adds to it
(v0.43.4).

### The Appearance swatches
Three rows of tiles in Settings: theme (Light / Dark / AMOLED), glass finish
(Frosted / Liquid) and scheme (Amber / Pine & cream). Each tile is a mini
preview of the room it opens; the chosen one wears the accent edge with a
soft ring, and picking re-dresses the whole room in one transition and says
so in a toast. Under the pine scheme the theme previews wear the pine lamp.

### Named Rules
**The Machined Press Rule.** Every control answers a press physically before
it answers with state: scale .97 down, then the work. No tappable surface
ships without a press state.

**The Finish Speaks Rule.** Completion is an event, not a pill flip: one
transition-fired toast with real actions, a stamp on the row, the take in the
bins. Nothing important settles silently in a tab nobody is watching.

**The Measured Lane Rule.** A floating lane never guesses: it measures what
is actually docked at the bottom right now and lifts above it; nothing
docked, it falls to the host's own corner. A fixed lift tuned for one tab is
a bug with a delay.

## Do's and Don'ts

### Do:
- **Do** keep amber scarce and purposeful: fills only on the one action per
  plate, elsewhere hairline / glow / underline / LED.
- **Do** give every focusable element a 2px accent `:focus-visible` ring at
  2px offset, and every touchable one a press state.
- **Do** guard all hover styling in `@media (hover: hover)`; on touch screens
  the press state is the only feedback.
- **Do** keep machine text (paths, sizes, versions, error bodies, flags) in
  the Martian Mono stack, and machine numbers at readout size on the scopes.
- **Do** stop motion — not shorten it — under `prefers-reduced-motion`;
  infinite animations must be set to none (a .001s infinite loop is MORE
  motion, not less) and the delays zeroed, or staggered rows still wait out
  their choreography.
- **Do** keep touch targets ≥44px tall on coarse pointers
  (`@media (pointer: coarse)`) with safe-area padding at the bottom edge.
- **Do** keep every blurred surface paired with `-webkit-backdrop-filter` and
  a solid `@supports` fallback.
- **Do** keep the darwin wash at .86 alpha or deeper — it is the contrast
  floor over any wallpaper, and the reason the page never sits bare on the
  material.

### Don't:
- **Don't** add accent hues beyond the two sanctioned voices (signal amber,
  pine & cream) and the three state lights; a third decorative hue is how
  this room stops reading as one instrument.
- **Don't** reintroduce gradient chrome: the only sanctioned gradient is the
  liquid glass's specular gloss (a material), never a coloured button fill.
- **Don't** use pure black (#000) except AMOLED's ground and video
  letterboxing; graphite is the room.
- **Don't** set text directly on the lamp glow; every text surface needs
  glass or a plate beneath it.
- **Don't** exceed the half-second ceiling or delay repeat interactions with
  entrance choreography.
- **Don't** use radius below 8px on interactive chrome, or leave a sharp
  corner on a floating surface.
- **Don't** start a download from a pick, and don't light two picks at once —
  the transport is the only starter, and the take is one thing.
- **Don't** let the page float bare on the native material or drop the wash
  below the contrast floor — the desktop is a hint, never the ground.

## The mark (brand)

The mark is one idea: a download arrow with the play knocked out of it, on a
tile. Drawn single-path SVG in `assets/brand/` — no text, no mask, no
gradient, no embedded raster. Every raster under `assets/`, `extension/icons/`
and the Android `mipmap-*` sets is generated from those masters by
`scripts/build_brand.py`; never hand-edit a PNG.

- **Pine & cream, two tones, theme-swapped.** The tile and the arrow carry the
  brand; the play triangle is a knockout that inherits the tile, so one mark
  serves every surface.
  - **Light room:** pine tile `#14493C`, cream arrow `#F2E9D8` (8.5:1).
  - **Dark & AMOLED rooms:** the chip flips — cream tile `#F2E9D8`, pine arrow
    `#14493C`. The pine tile would sink on those grounds (1.8:1 graphite,
    2.0:1 AMOLED); the cream chip reads like the header glow (15.6:1 / 17.4:1).
  - The header mark consumes `--mark-tile` / `--mark-arrow` from the theme
    blocks; the launcher and favicon files are the pine tile in every theme —
    system surfaces don't follow app themes, and the accent scheme never
    repaints the mark.
- **Do** keep the play a knockout and the geometry untouched; **don't** recolor
  the tile to amber — amber is the instrument's signal, not the brand, and the
  mark must survive at 16px (the old blue mark did not).
- Lockups — mark + wordmark outlines (Archivo 600, the app's own face) — live
  beside it: `lockup-horizontal.svg`, `lockup-horizontal-dark.svg`,
  `lockup-stacked.svg`.
