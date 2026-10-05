# Independent audit — 2026-10-05 (Google Antigravity)

**What this is.** The v0.44.0 tree was handed to an *independent* agent
(Google Antigravity CLI, `agy 1.2.16`, run headless in `--mode plan
--sandbox`) in **two passes in parallel**, each against its own throwaway
clone: a **Settings deep-dive** (`REPORT-SETTINGS-UI.md`, 34 KB, 45
findings) and a **sweep of every other surface** — download, queue,
yt-dlp, chrome, themes, accessibility, i18n, extension
(`REPORT-UI-SWEEP.md`, 32 KB, 45 findings).

**What was done with it.** Nothing was taken on trust. Every finding was
checked against the running engine (booted on loopback, DOM driven
through CDP) and the real source before anything changed — an audit is
evidence, not truth. Confirmed findings were fixed; findings the audit
overstated are recorded as **narrowed**; deliberate, documented designs
it mis-read are recorded as **refuted**. The same release also finished
the audit's own "flagged, not done" list: queue bulk actions, the
yt-dlp log card, the desktop folder picker, the Settings IA moves, and
the extension's Indonesian.

**Where the regressions live.** `tests/test_audit4_fixes.py` — each pin
reproduces a confirmed defect, and the narrowed/refuted entries carry
tests that record the narrower truth.

## Settings (the deep-dive's confirmed set)

| # | Finding | Verdict | Fix (v0.45.0) |
|---|---------|---------|---------------|
| 1.1 | Sub-tabs carried `aria-selected` only — no roving tab stop, no arrows — while the main deck's comment claimed they already had the pattern | confirmed (live) | `syncStabTabs()` + arrows/Home/End, mirroring the deck |
| 1.2 | Blanket `input`/`change` listener lit the dirty dot on self-persisting controls (language, default preset) and scratch boxes | confirmed (live) | id-filtered listener (`DIRTY_IGNORE`) |
| 2.1 | "1–4 · applied live" on Concurrent downloads was untrue — only Save persisted it | confirmed | the field now posts just its own key on change |
| 2.2 | Appearance swatches exposed no selected state to assistive tech (class-only) | confirmed (live) | `aria-pressed`, labelled groups; also: scheme selection now survives a settings load (`CURRENT` dropped `accent`) |
| 4.1 | "Save as preset" diffed against the stale disk snapshot, not the live form | confirmed | one payload builder (`settingsFormPayload`), shared by Save and the diff |
| 6.1 | "Test cookies" silently saved every dirty panel first | confirmed | `/auth/check` takes transient cookie overrides; the form is never committed by a test |
| 8.1 | Android cookie-vault wipe had no confirmation, against the house's own rule | confirmed | `askConfirm`, same as every other delete |
| 5.2 | Copy-token fallback said "select it above" over a *masked* token | confirmed | `execCommand` fallback; on failure the full token is revealed and selected |
| 9.1 | Indonesian split-string produced "di tab tab yt-dlp →" | confirmed | fragment translation fixed |
| 9.3 | Light-theme selected outline measured 2.74:1 (`#c07a16` on `#e7e4de`) | confirmed (measured) | the darker voice (`--accent2`, 3.6:1) in light |
| 9.2 | "Empty number inputs corrupt settings" | narrowed — the engine clamps every range (`int_in`); nothing corrupted | the form now mirrors the clamps back |
| 4.2 | "Presets can be saved nameless" | narrowed — the server answered a clean 400 | a client-side check added anyway (no round trip) |
| 9.7 | Reduced-motion `.001s` called a DESIGN violation | refuted — it is the documented technique; the bay door's `transitionend` needs an end to fire | no change; pinned with the rationale |
| 4.3 | Preset rows "show pointer cursor and hover state" | refuted — `cursor: default` and the muted hover were already there | no change |

The remaining confirmed minors (panel DOM order and `aria-labelledby`
linkage, aria-describedby hints, delete buttons naming their target, the
desktop-only reveal row, archive toggle placement, mono inputs for
machine strings…) are all fixed in the same release.

## The sweep (everything outside Settings)

| # | Finding | Verdict | Fix (v0.45.0) |
|---|---------|---------|---------------|
| 24 | `@supports not` glass fallback omitted `.scope`, `.job`, `.bin` and friends — unreadable 5% panes where blur is unavailable | confirmed | every glass plate falls back to solid |
| 37 | The `#noSound` listener lived at the end of `initFolderSheet()` (an Android dialog initializer) | confirmed | moved to the deck's own boot |
| 5 | The onboarding empty state sat *below* the transport it describes | confirmed (live) | moved above the probe card |
| 12 | The FILED TAKES rail scrolled away (Stable Shell rule) | confirmed | sticky at ≥1080px |
| 3 | Studio button didn't announce what it opens | confirmed | `aria-controls` + `aria-expanded` follow the door |
| 7 | A successful probe announced nothing to screen readers | confirmed | sr-only live line |
| 13 | Queue progress bars were generic divs | confirmed | `progressbar` role + live `aria-valuenow` |
| 40 | Format rows injected stagger delays under reduced motion | confirmed | guarded by `motionMs` |
| 42/43 | Options page labels had no `for=`; the popup version chip was hardcoded | confirmed | fixed; the chip reads the manifest at runtime |
| 33 | "🐴 title untranslated" | refuted — the brand mark, pinned by test | no change |

Not taken in this release (recorded, with the raw findings as the
reference): focus movement after a probe, an inline spinner on pending
queue rows, central Escape-key handling, and a few copy/layout nits.
