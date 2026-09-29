---
name: suravidl
description: "Aurora-glass UI — a quiet night instrument for downloading video"
colors:
  midnight-aurora: "#06080f"
  starlight: "#e9edf9"
  moon-mist: "#93a0bd"
  twilight: "#5d6a88"
  aurora-indigo: "#6366f1"
  comet-cyan: "#22d3ee"
  aurora-veil: "#c7d2fe"
  aurora-green: "#34d399"
  nova-rose: "#fb7185"
  solar-amber: "#fbbf24"
  glass-haze: "rgba(148, 163, 241, 0.07)"
  aurora-glow: "rgba(99, 102, 241, 0.18)"
  ink-pool: "rgba(6, 9, 18, 0.55)"
  moonbeam: "rgba(255, 255, 255, 0.10)"
typography:
  title:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "15.5px"
    fontWeight: 600
  body:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.1px"
  label:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
    letterSpacing: "0.12em"
  mono:
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace"
    fontSize: "11.5px"
    fontWeight: 400
rounded:
  sm: "10px"
  md: "12px"
  lg: "14px"
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
    backgroundColor: "{colors.aurora-indigo}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  button-glass:
    backgroundColor: "{colors.glass-haze}"
    textColor: "{colors.starlight}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  chip:
    backgroundColor: "{colors.aurora-glow}"
    textColor: "{colors.aurora-veil}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  input:
    backgroundColor: "{colors.ink-pool}"
    textColor: "{colors.starlight}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
  card:
    backgroundColor: "{colors.glass-haze}"
    rounded: "{rounded.surface}"
    padding: "18px"
---

# Design System: suravidl

## Overview

**Creative North Star: "The Aurora Observatory"**

suravidl's interface is an instrument deck under polar light: a dark, quiet
room where the aurora — three drifting radial gradients, blurred 70px — glows
behind frosted glass panels, and every control reads like a machined surface
you can press. It is an application, not a document: the layout is a stable
shell (sticky glass header over a left rail on desktop, a fixed bottom tab bar
on phones) with a single 980px column of glass cards doing the work. Density is
comfortable-compact and type stays in a tight ≈10–16px band, because the
audience is watching a queue, not reading prose. Every shell — desktop, phone,
extension — fronts this one visual world.

The mood is calm, nocturnal, and precise — light you watch by, not light that
shouts. The aurora never competes: it sits at 55% opacity under the panels on
dark (14% on AMOLED, brighter but pastel on light), and the panels themselves
are thin periwinkle glass (7% indigo haze) with hairline borders and one inset
top highlight — a real sheet of glass catching the room's light. Color is a
signal, not decoration: the indigo→cyan gradient appears only on primary
actions (Probe, Download, Save) and on progress, and the three status lights
(green / rose / amber) only ever carry state.

Every interaction is physical but quiet: buttons, tabs and swatches press down
(scale .97), busy controls pulse, rows fade in place instead of jumping, and
nothing anywhere exceeds half a second. On touch, taps never eat a
double-tap-zoom and hover styling disappears; in Android's WebView the aurora
freezes and blur drops to 11px, so a download is never taxed by decoration.

**Key Characteristics:**
- Dark-first — light and AMOLED are token swaps, not separate designs
- Glass over aurora: translucent cards, hairline borders, inset top highlight
- Two accents with fixed jobs: indigo = interactive, cyan = momentum
- One tight family (Inter) plus mono for machine text only
- Soft-instrument shapes: nothing sharper than 10px; pills for state
- Motion under half a second; reduced-motion stops it, never shortens it

## Colors

A night-sky palette: near-black ink, moonlit text, and a single aurora running
indigo-to-cyan, plus three honest status lights. The dark theme is normative
here; light and AMOLED re-value the same roles (light swaps the accent to the
iOS-style daylight blue #0a84ff; AMOLED sets the ink to true #000).

### Primary
- **Aurora Indigo** (#6366f1): the interactive color — active tabs, count
  badges, focus rings, selected chips, link buttons, and the first stop of
  every gradient.
- **Aurora Glow** (rgba(99, 102, 241, 0.18)): indigo at 18% — the soft fill
  behind quiet-accent surfaces (chips, "get" buttons, selected states).
- **Aurora Veil** (#c7d2fe): pale indigo — the text and glyphs that sit ON the
  glow (chip labels, get-button text).

### Secondary
- **Comet Cyan** (#22d3ee): the momentum color — second stop of the action
  gradient and of the progress fill, the LIVE chip, toast accents. Never used
  for static chrome: where cyan is, something is moving or is about to.
- The action gradient (120deg, indigo → cyan) is the only sanctioned gradient
  in UI chrome; it marks primary buttons and progress.

### Tertiary (status)
- **Aurora Green** (#34d399): success — completed pills, good messages.
- **Nova Rose** (#fb7185): error — failed pills, destructive actions, error
  text and lines.
- **Solar Amber** (#fbbf24): attention — paused / cancelled, warnings, the
  unsaved-settings dot, "engine unreachable" text.

### Neutral
- **Midnight Aurora** (#06080f): the ink the whole app sits on.
- **Starlight** (#e9edf9): primary text — an off-white with a cool cast; pure
  #fff is reserved for text on accent gradients.
- **Moon Mist** (#93a0bd): muted text — labels, hints, secondary copy.
- **Twilight** (#5d6a88): dim text — metadata, version strings, placeholders.
- **Glass Haze** (rgba(148, 163, 241, 0.07)): the periwinkle glass of every
  card, header and button.
- **Ink Pool** (rgba(6, 9, 18, 0.55)): input wells — darker than the room, so
  fields read as recessed.
- **Moonbeam** (rgba(255, 255, 255, 0.10)): hairlines — all borders and
  dividers.

### Named Rules
**The Signal, Not Wallpaper Rule.** Accent covers a small fraction of any
screen — a glow, a badge, one gradient button per region. The room is ink and
glass; the aurora is what you notice BECAUSE it is rare.

**The Two-Light Rule.** Indigo means "interactive". Cyan means "moving or in
progress". A surface that stores neither never wears either.

## Typography

**UI Font:** Inter (with system-ui, -apple-system, "Segoe UI" fallbacks)
**Mono Font:** JetBrains Mono (with ui-monospace, Menlo fallbacks)

**Character:** One quiet family in a tight, app-sized band — hierarchy is
carried by weight, case and color rather than size. Mono is a second voice,
reserved for machine text.

### Hierarchy
- **Title** (600, 15.5–16px): card titles and probe headings; the largest text
  in the app.
- **Body** (400, 14px, line-height 1.5, letter-spacing .1px): all controls,
  inputs, buttons and descriptions.
- **Label** (600, 12.5px, letter-spacing .12em, uppercase): section headings
  (SETTINGS, DOWNLOADS, "Appearance") — small, spaced, muted, quiet by design.
- **Small** (400, 12–12.5px): hints, footnotes, counters.
- **Mono** (400, 11.5–12.5px): versions, file paths, sizes, durations, error
  messages, raw args.

### Named Rules
**The Quiet Label Rule.** Section headings never grow. If a section needs more
emphasis, change the content's weight or color, not the label's size; the
uppercase 12.5px label is the app's loudest structural voice.

**The Machine Voice Rule.** Anything a machine produced or consumes — sizes,
paths, versions, flags, error lines — is set in mono. Prose stays in Inter.

## Layout

A stable single-column shell: sticky glass header (12px × 20px padding) over a
max-980px content column (22px × 20px padding). At ≥900px the tabs become a
208px sticky left rail (top: 64px) beside the column; below 900px they dock as
a fixed bottom bar (thumb reach, safe-area padding, equal segmented columns).
≤640px hides the version meta and tightens page padding; ≤560px modals become
full-height sheets with a sticky head and a sticky Save bar that rides above
the tab bar.

Spacing runs on a compact rhythm — 6 / 10 / 14 / 18 / 22px — for gaps, card
padding and page padding; controls inside a row breathe with 10–14px gaps and
cards stack with 16px margins.

### Named Rules
**The Stable Shell Rule.** The shell never scrolls away: header sticks, the
rail sticks, the mobile tab bar is fixed. Content moves; the instrument panel
stays put.

## Elevation & Depth

Ambient soft-lift. Depth is carried by translucency first — glass panels over
the aurora, each with a 1px inset highlight (the glass's wet edge) — and by a
single deep, diffuse shadow (0 24px 60px rgba(2,4,10,.5)) that lifts the whole
card family off the night. Shadows are ambient, never structural: they say
"this pane floats", not "this ranks higher". On AMOLED the shadow drops to none
and hairlines take over; the light theme's shadow warms and softens. Overlays
blur their backdrop 10px and dim it; message surfaces (toasts) deliberately sit
on a near-opaque plate (rgba(13,17,30,.97)) so text never fights the blur.

### Shadow Vocabulary
- **card-lift** (`0 24px 60px rgba(2,4,10,.5)`): under cards, modals and
  toasts (dark; AMOLED: none; light: a softened pair).
- **scroll-shade** (`0 8px 26px rgba(0,0,0,.28)`): the sticky header once
  content scrolls beneath it.
- **accent-spark** (`0 6px 22px rgba(99,102,241,.18)`, hover
  `0 10px 30px rgba(99,102,241,.45)`): the primary button's own glow.
- **status-halo** (`0 0 14px <state background>`): pills glow faintly in their
  state color.

### Named Rules
**The Glass Above Aurora Rule.** Every elevated surface is glass over the
backdrop — blur, hairline, inset highlight — never an opaque slab. The one
exception is the reading path: toasts go opaque, because a message must win
over atmosphere.

**The AMOLED Hairline Rule.** When there is no shadow (AMOLED), borders carry
all the separation; never re-introduce grey shadows there.

## Shapes

Soft instruments: every surface is a rounded rectangle — 10px (fields, small
buttons), 12px (buttons, tabs), 14px (toasts, swatches, the paste field), 16px
(queue rows), 20px (cards), 22px (modals) — plus the full pill (999px) for
chips, status, badges and the progress bar. There are no sharp corners
anywhere in the chrome. Borders are 1px hairlines (Moonbeam) that strengthen to
accent-line when a surface is selected or focused. The app mark is a 30px
rounded square (9px radius) carrying the gradient.

### Named Rules
**The Nothing Sharp Rule.** If it can be touched, it is rounded ≥10px. Radii
above 20px are reserved for surfaces that float over content (cards, modals),
never for inline controls.

## Components

Tactile instruments — machined glass you can press.

### Buttons
- **Shape:** 12px radius, 8×14px padding, 7px icon gap.
- **Primary (`.btn.prime`):** the indigo→cyan gradient on white text, weight
  600, accent-spark glow, 1px inset highlight. One per region — it is the
  page's answer to "what next".
- **Glass (`.btn`):** Glass Haze fill over blur, hairline border, Starlight
  text; hover lifts 1px and strengthens the fill (hover-capable pointers only).
- **Small / ghost (`.btn.sm`, `.ghost-sm`):** 10px / 9px radii for row actions;
  ghost is transparent with a hairline and muted text.
- **Danger (`.btn.danger`):** Nova Rose fill, line and text; also the confirm
  dialog's affirmative.
- **States:** press scales to .97 (buttons, tabs, swatches); busy pulses;
  disabled drops to ~50% opacity and refuses transform; focus-visible is a 2px
  Aurora Indigo outline at 2px offset — everywhere, always.

### Chips
- **Style:** pill, 11px text, Aurora Glow fill, Aurora Veil text, 1px
  accent-line border.
- **Pressed:** `aria-pressed="true"` flips to solid Aurora Indigo with white
  text — paint and semantics move together.

### Cards / Containers
- **Corner:** 20px radius. **Background:** Glass Haze + gloss layer over
  blur(16px) saturate(125%). **Border:** hairline (the liquid glass style swaps
  it to accent-line). **Shadow:** card-lift + inset top highlight. **Padding:**
  18px; stacked with 16px gaps.

### Inputs / Fields
- **Style:** Ink Pool wells, hairline border, 10px radius (the paste field:
  14px radius, 13×16px padding — the app's front door).
- **Focus:** the paste field swaps the standard ring for a border shift to
  accent-line plus a 4px Aurora Glow halo; plain inputs keep the global 2px
  outline.
- **Labels:** 12px Moon Mist above the control; hints in Small muted text.

### Navigation
- **Style:** icon + label tabs, 12px radius, muted text at rest.
- **Active:** Glass Strong fill + accent-line border + Starlight text (desktop
  rail: Aurora Glow fill); a count badge in solid Aurora Indigo where relevant.
- **Touch:** below 900px the same markup becomes a fixed bottom bar — icons
  grow to 17px, labels shrink to 10px.

### Status Pill
- **Shape:** pill, 11px / 600, letter-spacing .02em.
- **Spelling by state:** downloading / queued / merging = Aurora Glow fill,
  veil text, faint accent glow; completed = Aurora Green family; error /
  interrupted = Nova Rose; paused / cancelled = Solar Amber.

### Progress Bar
- **Track:** 8px pill of ink at 70%. **Fill:** the action gradient. A live
  download's width glides for exactly one poll interval (1.1s linear) so it
  never stalls between polls; indeterminate work shows a full muted track with
  a moving sheen — "working, position unknown".

### Toasts
- **Style:** near-opaque plate (Panel Solid), 14px radius, card-lift shadow,
  13px text; a state dot (green / rose / indigo) leads. Choices wrap under the
  message; update toasts carry the accent border and wait for an answer.

### Named Rules
**The Machined Press Rule.** Every control answers a press physically before
it answers with state: scale .97 down, then the work. No tappable surface ships
without a press state.

## Do's and Don'ts

### Do:
- **Do** keep the gradient scarce: primary actions, progress fill, the app
  mark — nowhere else.
- **Do** give every focusable element a 2px Aurora Indigo `:focus-visible`
  ring at 2px offset, and every touchable one a press state.
- **Do** guard all hover styling in `@media (hover: hover)`; on touch screens
  the press state is the only feedback.
- **Do** keep machine text (paths, sizes, versions, errors, flags) in the mono
  stack.
- **Do** stop motion — not shorten it — under `prefers-reduced-motion`;
  infinite animations must be set to `none` (a .001s infinite loop is MORE
  motion, not less).
- **Do** keep touch targets ≥44px tall on coarse pointers
  (`@media (pointer: coarse)`) with safe-area padding at the bottom edge.

### Don't:
- **Don't** use pure black (#000) except AMOLED's background and video
  letterboxing.
- **Don't** introduce hard or dark shadows; the card-lift family is ambient
  only — and on AMOLED it is absent, not weakened.
- **Don't** set text directly on the aurora; every text surface needs glass or
  a plate beneath it.
- **Don't** exceed the half-second ceiling or delay repeat interactions with
  entrance choreography.
- **Don't** use radius below 10px on interactive chrome, or leave a sharp
  corner on a floating surface.
- **Don't** add new accent hues beyond indigo / cyan + the three status
  lights; a fourth hue is how this deck stops reading as one instrument.
