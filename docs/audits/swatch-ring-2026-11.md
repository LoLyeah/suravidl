# The swatch ring, second pass — and why Material You was absent (2026-11)

Argon High reviewed v0.48.0 against the owner's screenshot. Two of its three
findings were real and shipped in v0.48.1; the selection treatment it
recommended is below, with the one part I changed.


## Bug 1 — "the colour border is still weird"
- **Defect** (`style.css:1443-1445`): `.swatch.on` sets `border-color: var(--accent)` and `box-shadow: inset 0 0 0 1px var(--accent2, var(--accent))`. In AMOLED Pine (`style.css:152-153`), `--accent` is `#F2E9D8` and `--accent2` is `#ffffff`. Two 1px strokes at radius 12px (`style.css:1433`) fuse into a hard 2px near-white headlight on tap with zero focus involved.
- **Comparison & Costs**:
  1. *Check badge* (circle in `--accent` with `--accent-fg` glyph + quiet border): Fails WCAG AA in Light Amber (`style.css:72,81`: `#1a1305` on `#c07a16` is 3.85:1 < 4.5:1). Three filled accent badges in one card break The One Lamp Rule (`DESIGN.md:191`). Focus is distinct outside.
  2. *Filled tint* (`--accent-soft` bg + `--accent-line` border): Quiet plate (`DESIGN.md:103`). In Light, `--accent-line` is 32–36% alpha (`style.css:75,147`, <2.1:1 on `#e7e4de`), requiring `--accent2` override (`style.css:1452`). Focus is distinct outside.
  3. *2px accent bar on one edge*: Horns on rounded corners (`border-radius: 12px`, `style.css:1433`). Light Amber `--accent` is 2.74:1 (<3:1 non-text).
  4. *Recommended (Post House Live-Light)*: Option 2 tint + 1px `--accent-line` hairline (`--accent2` in Light) + 6px live tally LED dot on `.sw-label` (`DESIGN.md:106,195`) with `--accent-ink` label (>=4.5:1 in all schemes, `tests/test_v480_themes.py:82`).
- **Focus Rule** (`style.css:391-397,1448`): Drop `.swatch.on:focus-visible` inset shadow (`style.css:1448`). Add `@media (pointer: coarse) { .swatch:focus-visible { outline: none; } }` so touch taps never ring, while Tab keeps `outline: 2px solid var(--ring)` (`style.css:395-396`).
- **Exact CSS**:
```css
.swatch.on { border-color: var(--accent-line); background: var(--accent-soft); box-shadow: inset 0 1px 0 var(--inset-hi); color: var(--text); }
.swatch.on .sw-label { color: var(--accent-ink); }
.swatch.on .sw-label::before { content: ""; display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 999px; vertical-align: 1px; background: var(--accent); box-shadow: 0 0 6px var(--accent-glow); }
html[data-theme="light"] .swatch.on { border-color: var(--accent2); }
html[data-theme="light"] .swatch.on .sw-label::before { background: var(--accent2); box-shadow: none; }
@media (pointer: coarse) { .swatch:focus-visible { outline: none; } }
```

## Bug 2 — "where's the material you?"
- **Defects Confirmed**:
  1. *Boot path* (`app.js:1560,6179`): `applyTheme` first called at `app.js:6179`. With stored accent `"pine"` (`app.js:1622-1623`), `accent === "dynamic"` (`app.js:1560`) is false. `applyDynamicPalette()` never runs; `#swDynamic` stays hidden (`index.html:516`).
  2. *Bridge name* (`MainActivity.kt:90`, `app.js:1518`): Matches (`"AndroidHost"`). Guard (`MainActivity.kt:366`) is `SDK_INT < 31` and try/catch (`MainActivity.kt:408`) catches `Throwable`, so it never throws before returning.
  3. *Kotlin JSON syntax bug* (`MainActivity.kt:392`): `"\"lamp\":\"" + lamp + "}"` omits `\"` before `}`. Emits invalid JSON (`"lamp":"rgba(...)}`), causing `JSON.parse` (`app.js:1522`) to throw and `readDynamicPalette` (`app.js:1525`) to return `null`.
- **Where Boot Call Belongs** (`app.js:6178`): Immediately before `applyTheme` at `app.js:6179`. In Android WebView `AndroidHost` is bound before page execution (`MainActivity.kt:90`). Calling before `applyTheme` populates `--dyn-*` on `:root` before `data-accent="dynamic"` evaluates, avoiding fallback flash, and unhides `#swDynamic`. If bridge is absent/pre-31, `readDynamicPalette()` safely returns `null` (`app.js:1519-1526`).
- **Resume Re-read** (`app.js:1618`): Wallpaper changes outside the app must re-theme on return. Add `if (document.visibilityState === "visible") window.onDynamicPaletteChanged?.();` inside the existing `visibilitychange` listener (`app.js:1618`).
- **Headless Proof & Pins**: Launch headless Chrome with mock `window.AndroidHost = { dynamicPalette: () => validJson }`, boot with `CURRENT.accent = "pine"`, and assert `!$("swDynamic").classList.contains("hidden")` and `--dyn-accent` is set on `:root`.

## Summary
```css
.swatch.on { border-color: var(--accent-line); background: var(--accent-soft); box-shadow: inset 0 1px 0 var(--inset-hi); color: var(--text); }
.swatch.on .sw-label { color: var(--accent-ink); }
.swatch.on .sw-label::before { content: ""; display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 999px; vertical-align: 1px; background: var(--accent); box-shadow: 0 0 6px var(--accent-glow); }
html[data-theme="light"] .swatch.on { border-color: var(--accent2); } html[data-theme="light"] .swatch.on .sw-label::before { background: var(--accent2); box-shadow: none; }
@media (pointer: coarse) { .swatch:focus-visible { outline: none; } }
```
- **Boot fix** (`app.js:6178`): Insert `applyDynamicPalette();` immediately before `applyTheme(...)` at `app.js:6179` (and fix quote at `MainActivity.kt:392`).
- **Pin 1** (`tests/test_v480_themes.py:56`): Assert `border-color: var(--accent-line)` in `.swatch.on` and `inset 0 0 0 1px` not in `.swatch.on`.
- **Pin 2** (`tests/test_v480_themes.py:120`): Assert `"applyDynamicPalette();\napplyTheme("` in `app.js` and `"\"lamp\":\"" + lamp + "\"}"` in `MainActivity.kt`.

---

## What shipped

- **The ring.** Argon was right that v0.48.0's "fix" was still a ring: 1px
  `--accent` (#F2E9D8) plus 1px inset `--accent2` (#ffffff) fuse into a 2px
  near-white edge on AMOLED + Pine. Selection is now a tint, a hairline and a
  6px LED before the label — the One Lamp Rule's own vocabulary.
- **The second defect Argon found, which I had missed:** the Kotlin bridge
  emitted `"lamp":"rgba(...)}` with no closing quote, so `JSON.parse` threw and
  *every* palette was null, even on a capable phone. Fixed; a test pins the
  fragment so it cannot come back.
- **The third defect, mine:** `applyDynamicPalette()` — the only code that
  unhides the Wallpaper swatch — ran only when the accent was ALREADY
  `dynamic`. A scheme nobody can see cannot be chosen. It now runs before the
  first `applyTheme`.
- **Not taken:** Argon's `@media (pointer: coarse) { .swatch:focus-visible {
  outline: none } }`. A live tap probe showed `:focus-visible` does not match
  after touch at all (the ring was the selected style, not focus), so
  removing the outline would only cost keyboard users on tablets.
