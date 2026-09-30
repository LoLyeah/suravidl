---
name: suravidl
description: "The Post House — an ingest room: graphite ground, smoked-glass plates, signal amber for action, scope green for state"
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
  scope-green: "#4ecf83"
  tally-rose: "#ff8078"
  smoked-glass: "rgba(232, 236, 240, 0.05)"
  smoked-glass-strong: "rgba(232, 236, 240, 0.09)"
  ink-well: "rgba(4, 6, 8, 0.45)"
  panel-solid: "#14181d"
  lamp-glow: "rgba(232, 163, 62, 0.10)"
typography:
  title:
    fontFamily: "Archivo, system-ui, -apple-system, sans-serif"
    fontSize: "15px"
    fontWeight: 700
  body:
    fontFamily: "Archivo, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.1px"
  label:
    fontFamily: "Archivo, system-ui, -apple-system, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    letterSpacing: "0.14em"
  mono:
    fontFamily: "'Martian Mono', ui-monospace, Menlo, monospace"
    fontSize: "12.5px"
    fontWeight: 400
rounded:
  sm: "8px"
  md: "9px"
  lg: "13px"
  xl: "16px"
  surface: "20px"
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
- One action colour: signal amber, only where you press or progress. Three
  state colours (scope green / tally rose / warm amber) only ever carry state.
- Two voices, both shipped with the app: Archivo for prose, Martian Mono for
  every machine readout.
- Machine-instrument shapes: 8–14px controls, 20px floating plates; pills for
  state. Nothing sharper than 8px, nothing rounder than a pill.
- Motion stays under half a second; reduced-motion stops it — never shortens it.

## Colors

A film-lab palette: graphite ink, film-white text, and the amber of a single
practical lamp, plus three honest state lights. The dark theme is normative;
light and AMOLED re-value the same roles (light darkens amber to #c07a16 with
#6b4308 as its ink so small amber text keeps 4.5:1; AMOLED sets the ground to
true #000 and drops shadows for hairlines).

### Primary
- **Signal Amber** (#e8a33e): the action colour — the START and Probe fills,
  the active tab underline, LEDs in live states, the selection wash, the
  unsaved-settings dot. In light theme: #c07a16.
- **Lamp Full** (#f3c169): amber at full — hover on the primary fill only.
- **Amber Ink** (#f0c98a): amber as text — link buttons, readouts in an armed
  state, "this download only" markers. In light theme: #6b4308.

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

### Named Rules
**The One Lamp Rule.** Each plate has at most ONE filled amber control; every
other appearance of amber in that region is a hairline, a glow, an underline
or an LED. Two filled amber buttons side by side is a signal failure.

**The Live-Light Rule.** Amber/Green/Rose never decorate: an LED is lit only
while its state is true (live, armed, filed, refused), and glow follows power
— lit LEDs glow faintly, dark ones don't.

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
- **Label** (700, 9.5–10px, letter-spacing .14em, uppercase): scope names,
  card kickers, section heads — small, spaced, quiet by design.
- **Small** (400, 12–12.5px): hints, footnotes, counters.
- **Readout / Mono** (400, 11.5–15px): scope readings (the largest mono in the
  app), sizes, durations, paths, versions, error bodies, file names.

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
deck's end on desktop (sticky bottom 14px) and a fixed bar above the tab bar
on phones (download tab only). The patch bay ("This download only") sits under
the deck; Settings is a tab panel with sub-tabs and a sticky Save bar that
keeps the plate's glass and its bottom corners.

Spacing stays on a compact rhythm — 6 / 10 / 14 / 18 / 22px. Cards stack with
16px gaps; controls in a row breathe with 10–14px.

### Named Rules
**The Stable Shell Rule.** The shell never scrolls away: header and tab strip
stick, the mobile tab bar is fixed, the phone transport floats above it.
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
  composites `backdrop-filter` correctly (proved on device pixels: ghost
  text behind the transport measured edge energy 19 against crisp text's
  81). Where a WebView truly cannot blur, the `@supports` block turns every
  plate solid — a fake half-glass never ships.
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

**The AMOLED Hairline Rule.** Where there is no shadow (AMOLED), borders carry
all separation; never re-introduce grey shadows there.

## Shapes

Machined plates: 8–9px for buttons and fields, 12–13px for the transport and
toasts, 14px for the patch bay, 20px for cards, modals and the FILED stamp's
plate family; full pills (999px) for chips, status and the progress bar. The
app mark is a 30px rounded square (9px radius) in Signal Amber carrying the
letterform. Borders are 1px hairlines that strengthen to accent-line on
selection, focus or an armed state.

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
the take ("START · 720p"). Fixed above the phone tab bar; sticky at the
deck's end on desktop. Fired = spent: the take clears, every pick unlights,
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
- **Primary (`.btn.prime`):** Signal Amber fill, #1a1305 text, 700, glow
  `0 10px 22px -10px rgba(232,163,62,.55)` + inset top light. One per plate.
- **Glass (`.btn`):** smoked fill over blur, hairline, film-white text;
  hover lifts the fill and warms the border (hover-capable pointers only).
- **Ghost (`.ghost-sm`):** transparent, hairline, muted; destructive variants
  carry tally rose. Row actions live here.
- **States:** press scales to .97; busy pulses (1.1s) and refuses pointers;
  disabled drops opacity and refuses transform; focus-visible is a 2px amber
  outline at 2px offset — everywhere, always.

### Job rows
Pill + (completed) FILED stamp; title link; mono meta (size · time · site);
path line in mono; actions Play / Copy / Retry / Delete (+ "Edit & retry").
A failed row leads with the human sentence in tally rose ("the site says this
link does not exist (404) — check it was copied whole"); the raw engine text
sits clamped behind "Show details". A live row's fill glides for exactly one
poll interval (1.1s linear) so it never stalls between polls.

### The FILED TAKES rail (≥1080px)
Newest takes first: bin title + mono file name, count badge in amber. The
rail is a shelf, not a second queue — its items open the take.

### Toasts
Near-opaque plate, 12px radius, a state dot (green / rose / amber), message
13px; choices wrap under the message. Completion toasts carry actions (Play /
Show folder) and the toast lane sits above the mobile tab bar and the
Settings Save bar (lane math via --tabbar-h).

### Named Rules
**The Machined Press Rule.** Every control answers a press physically before
it answers with state: scale .97 down, then the work. No tappable surface
ships without a press state.

**The Finish Speaks Rule.** Completion is an event, not a pill flip: one
transition-fired toast with real actions, a stamp on the row, the take in the
bins. Nothing important settles silently in a tab nobody is watching.

## Do's and Don'ts

### Do:
- **Do** keep amber scarce and purposeful: fills only on the one action per
  plate, elsewhere hairline / glow / underline / LED.
- **Do** give every focusable element a 2px amber `:focus-visible` ring at
  2px offset, and every touchable one a press state.
- **Do** guard all hover styling in `@media (hover: hover)`; on touch screens
  the press state is the only feedback.
- **Do** keep machine text (paths, sizes, versions, error bodies, flags) in
  the Martian Mono stack, and machine numbers at readout size on the scopes.
- **Do** stop motion — not shorten it — under `prefers-reduced-motion`;
  infinite animations must be set to none (a .001s infinite loop is MORE
  motion, not less).
- **Do** keep touch targets ≥44px tall on coarse pointers
  (`@media (pointer: coarse)`) with safe-area padding at the bottom edge.
- **Do** keep every blurred surface paired with `-webkit-backdrop-filter` and
  a solid `@supports` fallback.

### Don't:
- **Don't** add accent hues beyond signal amber + the three state lights; a
  second decorative hue is how this room stops reading as one instrument.
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
