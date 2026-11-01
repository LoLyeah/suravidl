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
