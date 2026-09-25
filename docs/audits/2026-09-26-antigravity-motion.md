# Antigravity UI/UX + motion review — verdicts (2026-09-26)

An independent motion/UX pass over `src/suravidl_engine/web/` (21 findings: 9
UX, 12 motion), run read-only against the tree as it stood before this pass.
Every claim was reproduced against the code, the CSSOM, or a live page before
anything changed — three were already fixed in the same sitting, and two were
rejected on evidence. Nothing here trusts the reviewer's word.

Method: the engine on a scratch `HOME`, a real Chrome on the page, live probes
(`getAnimations()`, computed styles, `getBoundingClientRect()` sampled every
100 ms across poll boundaries) and a throttled fixture server so a download
stays in every state long enough to watch. Text-level regression tests live in
`tests/test_web_motion.py`.

## Part A — UX & interaction

| # | Finding | Verdict | What actually changed |
|---|---|---|---|
| UX-H01 | No pending state on download triggers | **Fixed** | `startJob(..., triggerBtn)` disables + `.busy`-pulses the button for the round-trip; every trigger (format `Get`, quality chips, best/audio buttons, playlist button, the audio "more" select) passes itself in. Also: an empty link now says "paste a video link first" instead of a bare 4xx toast. |
| UX-H02 | Stale row during async cancel+delete | **Fixed** | The row is marked `.pending` (dimmed, `pointer-events: none`) and its pill reads "stopping…" / "deleting…" before `settleThenDelete`'s up-to-3s loop; a failed delete removes the mark again. |
| UX-H03 | Sticky footer hides the field under the keyboard | **Fixed, differently** | Rather than unpinning the Save bar (it is pinned on purpose), a `focusin` handler scrolls the field into view *only when it is actually obscured*, with `behavior: auto` under reduced motion. Keeps the bar's one-tap save on a phone. |
| UX-M01 | Unsaved settings invisible | **Fixed** | `markSettingsDirty()` puts a `•` on the Settings tab (`::after`, amber) while the form holds edits; cleared on load and on save. |
| UX-M02 | "This download only" says only a count | **Fixed** | The chip's `title` + `aria-label` now name the active override keys (and the preset), so a leftover clip/subtitle filter is visible without opening the block. |
| UX-M03 | Option rows unreachable by keyboard | **Fixed** | Roving tabindex: the list owns **one** tab stop, arrows/Home/End move inside, Enter/Space insert — with `role="button"` and a focus ring. (The review's snippet would have added 322 tab stops.) Verified live: focus → first row, ↓ → second, Enter → the arg lands in the textarea and the raw-args switch arms. |
| UX-M04 | Playlist range reacts only on blur | **Fixed** | `input` listener alongside `change`. |
| UX-L01 | Redundant ✕ in the Settings header | **Fixed** | Hidden at ≥900px (the tab rail is the way out there), kept on phones where it is the one-handed back; gains an `aria-label`. |
| UX-L02 | Focus rings inconsistent on ghost buttons | **Fixed** | `.ghost-sm` and `textarea` join the `:focus-visible` rule. |

## Part B — Motion

| # | Finding | Verdict | What actually changed |
|---|---|---|---|
| MOT-H01 | Progress bar stutters against the 1200 ms poll | **Fixed** | New `--t-poll: 1.1s` token; `.bar .fill.active` glides linearly across the whole poll window. Test pins the pairing (`0.8 × interval ≤ token ≤ interval`) so the two can never drift apart. **Measured live: 15 sampled frames where the bar moved while the poll value was static.** |
| MOT-H02 | `.swap` drops the row 6px on every status change | **Fixed, softer** | The cue stays (the content *did* change) but becomes opacity-only, `.55 → 1` — no translate. Rejected the "remove it entirely" suggestion: status-change feedback is the point. |
| MOT-H03 | Rows vanish with no exit | **Already fixed in this pass** | `.leaving` + `@keyframes leave` (down-and-out), triggered via `leaveRow()` before the empty state fades in, with an `animationend` + timer backstop. **Constraint-safe**: transform/opacity only — the review's own version animated `max-height`/padding, which relayouts the queue every frame. |
| MOT-H04 | Modal exit cut off half-visible | **Fixed** | `.overlay.closing .modal` ends at `opacity: 0` (was `.5`) and finishes inside `closeModal()`'s 170 ms timer. Verified live: opacity 0 at 160 ms, overlay `.hidden`, player body released. |
| MOT-M01 | Card rise replays on every tab switch | **Rejected — measured false** | With the queue tab hidden and shown, `getAnimations()` reports only the tab buttons' colour transitions; no `rise` on any card. Chrome does not restart a finished `animation` when `display` flips. The 0.5s/0.12s delays apply to first load only. |
| MOT-M02 | Unbounded `floaty` loop | **Already fixed in this pass** | The empty state is a one-shot `fade`; reduced motion now sets `animation-iteration-count: 1 !important` (the old `.001s` duration alone ran `floaty` at ~1 kHz) and covers `*::before`/`*::after`, so the progress sheen stops too. |
| MOT-M03 | Queued/merging show no progress at all | **Fixed** | Every `ACTIVE` status renders a bar: real progress while downloading, a muted full-width indeterminate track (with the same sheen) for queued/merging. The poll no longer writes a width into an indeterminate fill, and `metaParts` stops printing "0%" / "0 B / 0 B" for states that know nothing. |
| MOT-M04 | Player bypasses the modal transition | **Fixed** | `closePlayer()` goes through `closeModal()` and releases the `<video>` 180 ms later. |
| MOT-M05 | Android: 70px blur + animated transform | **Fixed** | `html[data-host="android"] body::before { animation: none !important; filter: blur(34px) }` — the aurora is decoration, the download is the job. |
| MOT-L01 | Theme switch covers only 4 selectors | **Fixed** | Scoped `html.theming` cross-fade (background/colour/border) for the ~400 ms the switch lasts, applied by `applyTheme()`. The blanket-selector suggestion was rejected: it would have overridden every component's own (faster) hover timing permanently. |
| MOT-L02 | Toast stack jumps when one is dismissed | **Rejected — by design** | Every fix (max-height, margin, FLIP) animates layout on each dismissal, which this stylesheet deliberately avoids everywhere else. The jump is one toast's height, on dismissal only. Documented rather than papered over. |
| MOT-L03 | Staggered format rows feel slow | **Fixed (partial)** | Stagger cap lowered 240 ms → 150 ms, keeping the cascade but arriving sooner. |

## The three highest-impact changes, as the reviewer ranked them

1. **Progress bar glide** — confirmed as the worst offender (a 220 ms animation
   followed by ~1 s of dead time, every poll). Fixed with the paired token.
2. **`.swap` glitch** — confirmed; calmed to a fade that keeps the signal.
3. **Queue exit** — confirmed; shipped with layout-safe keyframes.

## Numbers

- 21 findings: **17 fixed**, **2 already fixed** in this same pass before the
  report landed, **2 rejected** with evidence (one by direct measurement).
- 17 new regressions in `tests/test_web_motion.py`; full suite **346 passed**.
- Live-verified after the change: glide, indeterminate bar, clean meta line,
  delete-in-flight state, row exit, modal exit (opacity 0), scoped theme
  cross-fade, dirty dot, keyboard browse/insert, reduced-motion behaviour.
