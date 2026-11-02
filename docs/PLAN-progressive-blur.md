# Progressive blur: is it possible, and should we?

Audit by Argon (agy, "use Argon high") on a clone of `5fa2d14`, with the
mechanism re-measured here in Chromium before the verdict was accepted.

## What was measured here (not reasoned)

- **The mechanism works.** A fixture with three stacked leaf layers
  (`backdrop-filter: blur(2|8|22px)`, staggered
  `mask-image: linear-gradient(to bottom, …)`) produced a real optical ramp:
  fully smeared at the top, crisp below the band — verified on the rendered
  frame, not from the CSS.
- **Cost on desktop Chromium is small.** A 120 px band with three layers over
  a scrolling page: 121 frames / 2 s without it, 120 frames / 2 s with it;
  worst frame 17 ms → 33 ms once (no sustained drop).
- **Android was NOT measured.** The emulator board can do it (`dumpsys
  gfxinfo … framestats`), but that is a job, not a guess.

## What Argon concluded (reasoning, with file:line)


## 1. Feasibility Verdict: Optical Physics & Engine Reality
- **Spatial ramp in CSS:** CSS Filter Effects 2 defines `backdrop-filter: blur(<length>)` with a fixed scalar. A spatial ramp ($\sigma(y) = y \cdot \sigma_{\max} / H$) cannot be declared natively.
- **Mask on glass element (Technique B):** **Fails optically.** Blending a $14\text{px}$ blur with transparent background is an Orton/unsharp halo, not a radius ramp. High-frequency glyphs remain sharp at 65% contrast inside a diffuse glow. Violates *The Real Glass Rule* ([DESIGN.md:334-336](file:///tmp/agy-blur/DESIGN.md#L334-L336)) and *The Measured-Blur Rule* ([DESIGN.md:338-343](file:///tmp/agy-blur/DESIGN.md#L338-L343)).
- **SVG filter (Technique C):** **Dead on arrival.** SVG `<feGaussianBlur>` `stdDeviation` is a uniform scalar. Furthermore, WebKit (`WKWebView` on macOS, `WebKitGTK` on Linux) silently ignores `url(#filter)` in `-webkit-backdrop-filter`, leaving zero blur.
- **Stacked backdrop layers (Technique A):** **Only working mechanism.** Stacking $\ge 3$ leaf slices ($2\text{px} \to 5\text{px} \to 11\text{px}$) with staggered `mask-image: linear-gradient(...)` piecewise-approximates a ramp. Works in Blink/WebView2 and WebKit leaf nodes, but costs $O(n)$ compositor passes.

## 2. Cost on Mid-Range Android WebView & Scrolling Content
- **Compositor overhead:** Mid-range mobile GPUs (Adreno 610/619, Mali-G52/G57) use Tile-Based Deferred Rendering (TBDR). Sampling external pixels in `backdrop-filter` breaks on-chip SRAM tiling, forcing a tile flush to LPDDR RAM, offscreen FBO allocation (`GrSurfaceProxy`), two separable Gaussian passes, and mask composite in `viz::SkiaRenderer`.
- **Compounding over scrolling glass:** In `#panel-queue` ([index.html:380](file:///tmp/agy-blur/src/suravidl_engine/web/index.html#L380)) and `#formats` ([style.css:468-479](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L468-L479)), `.card` plates *already* execute a `backdrop-filter` pass. Adding 3 stacked skirt layers over scrolling cards forces 4 sequential RenderPasses and 8 FBO switches per frame, adding 5–8ms to GPU frame time and dropping 60fps scroll to 30–45fps. `style.css:215-217` and `style.css:1603-1629` already clamped Android blur to $11\text{px}$ and disabled ambient animations for battery. Android budget allows **0 extra stacked backdrop layers**.
- **Metrics to verify before committing:** `adb shell dumpsys gfxinfo <pkg> framestats` (p95 `< 16.6ms`), Chromium Perfetto trace `SkiaRenderer::DrawRenderPassQuad` count per `BeginImplFrame`, and `skia/gpu_resources` scratch texture allocation.

## 3. Fit in THIS UI ("The Post House" vs. "Apple Showroom")
- **Design language clash:** `DESIGN.md:97-108` defines suravidl as "The Post House" — machined optical plates with $1\text{px}$ hairlines (`--glass-border`) and top inset specular highlights (`inset 0 1px 0 var(--glass-hi)`). Progressive blur is an Apple borderless-fog idiom; blurring inside a bordered plate contradicts its physical material.
- **`header` ([style.css:282-298](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L282-L298)):** **Anti-pattern.** A downward ramp blurs `.tabs` ([index.html:83-93](file:///tmp/agy-blur/src/suravidl_engine/web/index.html#L83-L93)) at `scrollTop == 0`. Clashes with `border-bottom: 1px solid var(--line-soft)` and elevation shadow.
- **`.bins` ([style.css:412-426, 457](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L412-L426)):** **Noise.** Dedicated column 1; no content ever scrolls underneath it.
- **`.modal` ([style.css:1154-1175](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L1154-L1175)):** **Noise.** Centered popup with `100vmax` shadow curtain; nothing scrolls behind its outer perimeter.
- **Above `.transport` ([style.css:848-859, 1499-1510](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L848-L859)) & `.modal-foot` ([style.css:1292](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L1292)):** **Only viable candidate.** When `#formats` scrolls, text peeks through the $10\text{px}$–$14\text{px}$ gap beneath the floating capsule. A top-to-bottom ramp ($0\text{px} \to 12\text{px}$) behind `.transport` quiets the gap, but double-blurs the card's top highlight (`inset 0 1px 0 var(--glass-hi)`).

## 4. Backdrop-Root Rule Coexistence & The Plan
- **The Invariant:** Under W3C Filter Effects 2 §3.1, `backdrop-filter != none` and `mask-image != none` establish Backdrop Roots. Any pseudo-element on `.transport` or `.card` samples an empty buffer (dead frost) outside the plate's border box. Progressive blur layers **must be separate DOM sibling leaf nodes** outside existing glass plates.
- **Dissolve contract collision:** `.tab-in > .subpanel > :not(...)` ([style.css:398-403](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L398-L403)) would animate the skirt from `opacity: 0`, recreating the `v0.47.24-26` backdrop root. Must add `:not(.prog-skirt)` to the exclusion list.
- **Honest Verdict:** **Not worth shipping.** 3–4 stacked backdrop passes cripple Android scroll and smear the machined 1px bevel aesthetic.
- **Nearest Cheap Alternative (Earns Its Place):** A zero-pass Aperture Scrim on `.transport` and `.modal-foot`:
  `box-shadow: var(--shadow), inset 0 1px 0 var(--glass-hi), 0 14px 20px 6px var(--bg);` ([style.css:858](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L858), [:1292](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L1292)).
  Quiets the $14\text{px}$ gap under the bar at **0 extra GPU passes** and **0 backdrop-root risk**.
- **Experimental Spike Plan (if pursued):**
  1. *Smallest honest version:* Sibling `<div class="prog-skirt" aria-hidden="true"><i></i></div>` inside `#subLink` ([index.html:116](file:///tmp/agy-blur/src/suravidl_engine/web/index.html#L116)) before `#transport`. 3 leaf pseudo-layers (`::before` 2px, `> i` 5px, `::after` 11px) with staggered `mask-image` linear gradients.
  2. *Degradation:* `html[data-host="android"] .prog-skirt { display: none; }` ([style.css:1603](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L1603)); `@supports not (backdrop-filter: blur(1px))` falls back to `none`.
  3. *Contract tests:* Add `tests/test_prog_skirt_contract.py` asserting `.prog-skirt` is excluded in `style.css:398-401`, has no opacity/mask on its parent, and is disabled on Android. Update `tests/test_v4725_dissolve.py:46-51` and `tests/test_v4726_once.py:59-64`.
  4. *Abort criteria:* Abort if `#formatSection.card` top highlight smears into a milky band, if continuous scroll frame time on Desktop Chromium increases by $> 2.0\text{ms}$, or if WebKitGTK produces clipping seams.

## Summary
1. **Verdict:** Not worth shipping. True progressive blur violates "The Post House" machined plate aesthetic and severely overspends Android's GPU scroll budget.
2. **The Mechanism:** True progressive blur requires $\ge 3$ stacked leaf sibling layers with increasing radii and staggered gradient masks ($O(n)$ FBO passes); a single masked blur is merely an unsharp alpha halo.
3. **The First Step:** Ship the zero-pass `0 14px 20px 6px var(--bg)` aperture shadow on `.transport` ([style.css:858](file:///tmp/agy-blur/src/suravidl_engine/web/style.css#L858)) to quiet the scroll gap without extra render passes.
