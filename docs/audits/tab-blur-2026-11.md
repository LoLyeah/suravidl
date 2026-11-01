# Tab-switch blur audit (2026-11)

Reported: switching tabs, the frosted blur is gone for the length of the
arrival fade and then appears abruptly. Audit by Argon (Gemini via agy, high),
mechanism re-measured here in Chrome before the fix was accepted.

## Mechanism

 The blur is absent during the switch because animating `opacity` on the incoming `.panel` makes it an active **backdrop root**.
 Under W3C CSS Filter Effects Module Level 2 (§3.1) and Chromium's compositor (`cc`/Blink), any element with `opacity < 1` (or an active compositor opacity animation) creates an isolated stacking context that establishes a backdrop root image.
 Descendant surfaces with `backdrop-filter: var(--glass-blur)` (`.card`, `.transport`, `#panel-settings .modal-foot`) can only sample pixels rendered within that backdrop root. Because `.panel` has no background, its backdrop buffer is transparent; blurring transparent pixels produces empty pixels, so glass surfaces render flat.
 While v0.45.11 fixed the *retained* backdrop root after completion (`animation-fill-mode: none`), `.panel` remains a backdrop root for the entire 140ms (`--t-fast`) duration while `tabIn` runs. At 140ms, the animation finishes, `.panel` returns to `opacity: 1`, the backdrop root is destroyed, and Chromium abruptly samples the page backdrop, causing the blur to pop in without transition.

Our own measurement (Chrome 154, 420x180 glass card over an 8 px striped
backdrop, edge energy = mean |x[i]-x[i-1]| inside the card):

| state | edge energy |
|---|---|
| glass at full opacity | 0.24 (blurred) |
| ancestor at opacity .5 | 52.19 (raw stripes) |
| ancestor filter: opacity(.5) | 52.19 |
| + will-change: backdrop-filter | 52.19 |
| + transform: translateZ(0) | 52.19 |
| + isolation: isolate | 52.19 |

So no CSS escape hatch exists: the fix has to stop animating opacity on an
ancestor of the glass.

## Fix shipped (v0.47.24 "the wash")

- `.tab-in` / `.spanel-in` no longer animate opacity on the panel; a
  `::after` wash (sibling of the cards, `pointer-events: none`, `z-index: 1`)
  clears from .45 to 0 over `--t-fast`.
- Rests at `opacity: 0`, and the keyframes carry an explicit `to` — a `from`
  alone settles at the element own opacity (1), i.e. an opaque slab.
- Verified in the browser: panel opacity stays 1 for the whole switch; the
  wash samples 0.45 / 0.12 / 0.03 / 0 / 0 at t = 0/35/70/105/140 ms; panel
  brightness 27.9 at 10 ms vs 33.6 at 140 ms (the veil clears).
- Pinned by `tests/test_v4724_wash.py` (no opacity animation on panels, wash
  shape, no retained fill).

## Second pass: Argon high (rejected v0.47.24's wash)

Run through agy's own `argon-subagent` skill ("use Argon high"), in a clone,
asked to be adversarial about the wash. Verdict: reject. The objections that
survived checking against this tree:

- **Punch-through.** The transport is `z-index: 30` (`style.css:836`), the save
  strip `3` (`:1260`); the veil was `1` — pinned furniture stayed bright while
  the cards dimmed.
- **Wrong colour.** The veil was `var(--bg)`; over white cards in the light
  theme (`--bg: #e7e4de`) that is a beige film, and in Settings `.spanel` sits
  inside a card, so `spanelWash` painted page background into the card.
- **Spent in two frames.** With `--t-fast` (.14 s) and e-out the veil measured
  .45 / .12 / .03 at 0/35/70 ms — a luminance stutter, not an arrival.
- `border-radius: inherit` on a panel with no radius resolves to 0.

Refuted from the same report: "`.tab-in` is never removed" is harmless — the
wash rests at `opacity: 0`, and the class is removed and re-added on the next
switch; and "tests/test_v4724_wash.py does not exist" was true only because
the clone predated the commit.

**v0.47.25 "the dissolve"** takes its structural advice, not its code: plates
never fade, contents do. `.tab-in > :not(.card):not(.transport):not(.bins)`,
`.tab-in .card > *` and the `.spanel-in` equivalents animate `contentIn`
(from opacity 0) over `--t-fast`. Verified in Chrome: during the switch the
panel and card are both at opacity 1, the card still reports
`blur(14px) saturate(1.15)`, its first child is mid-`contentIn`, and no
ancestor of a glass plate is below opacity 1.
