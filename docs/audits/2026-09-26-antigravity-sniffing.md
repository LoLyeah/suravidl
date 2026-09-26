# Audit — "capture anything" arc, 2026-09-26 (Google Antigravity)

**What this is.** The v0.24.4 tree was handed to an independent agent (Google
Antigravity CLI, `agy 1.2.11`, headless, read-only brief) covering the whole
sniffing arc — engine `classify`/`rank`, the MV3 extension, the Android
in-app browser, and their tests. It wrote a 21 KB report, 15 findings.

**What was done with it.** Nothing was taken on trust, and two findings were
**downgraded with reasons** (1 and 3) rather than fixed as reported. Each
confirmed finding was reproduced against the real code path first, fixed, and
pinned by a test that fails without the fix — including one *mutation check*
(the pattern-persistence fix reverted in a clone: the new restart check fails,
which is how a test for it is known to be real). Everything else was either
already known (the decoration in test 15 was found here by mutation first) or
deliberate, and is recorded as such below.

## Verdict per finding

| # | Claim (agy's words) | Verified? | Outcome |
|---|---------------------|-----------|---------|
| 1 | **High** — a hostile page can swap `window.__svSniffSrc` and get JS eval'd in child frames | ⚠️ **half true, impact overstated** — a page can already `eval()` into its *own same-origin* frames, so it gains no privilege. The real half is the *other* property: resetting `__svSniffDoc` re-ran the hooks on every injection (re-wrapping `fetch`/XHR/MS) | **Hardened**: both globals are `Object.defineProperty`'d non-writable, non-configurable, non-enumerable, with an assignment fallback for engines that refuse |
| 2 | **High** — infinite `/classify` retry loop in the browser | ✅ **real, and the worst of the batch** — a null verdict left `info[url]` unset while `classifyQueue` had already been drained, so `render()` re-queued it forever: an unthrottled loop hammering the engine | **Fixed**: a null verdict is stored as a sentinel (`{"error": true}`) — the engine saying no is an answer too |
| 3 | **High** — SSRF in `/classify` (private IPs, cloud metadata, redirects) | ⚠️ **real but not SSRF as described** — no exfiltration path exists: the verdict is rendered in the *local app's* list, which the attacking page cannot read. What was real: the engine would fetch a link-local/metadata address on request | **Fixed narrowly**: link-local + cloud-metadata hosts are refused before any fetch, with the reason in the note. **Loopback and RFC1918 stay allowed on purpose** — the engine *is* on loopback, and a NAS is a legitimate thing to download from. Anti-DNS-rebinding is deliberately out of scope for a local tool |
| 4 | **Medium** — MV3 pattern cache broken across worker restarts | ✅ **real, and mine** — `loadPatterns` stored only `patternsAt`, so after the (routine) worker restart the 24 h timer was fresh while the regex was the baked-in fallback: the engine's list was effectively never used | **Fixed**: the list itself is persisted and re-applied at startup. **Mutation-verified** — reverting the fix makes the new restart check fail |
| 5 | **Medium** — an extension-less media URL found only by its response carries no headers | ✅ real — `onBeforeSendHeaders` only stored what already looked like media, so a `video/*` response upgrade arrived with nothing | **Fixed**: headers are held (memory only, bounded, never stored) and committed only when the response proves media — the "nothing but media headers reaches storage or the engine" rule holds |
| 6 | **Medium** — `SniffLog` compound ops not atomic, `version` not atomic | ✅ real — `add()` is called from the WebView handler thread, the JS bridge and the UI thread; a concurrent `clear()` could make `items[index] = …` throw | **Fixed**: one critical section + `AtomicInteger`, and a thread-hammering test on device |
| 7 | **Medium** — same-origin manifest collision in `rank()` misattributes fragments | ✅ real — the reason named the wrong playlist when an ad's manifest shared the origin | **Fixed**: the fragment is attributed to the manifest it actually lives next to (longest common path prefix) |
| 8 | **Medium** — query strings misclassified as manifests | ✅ real — `clip.mp4?origin=playlist` was treated as a playlist, which hid *other* rows it had no business hiding | **Fixed**: hints are matched against the path only. (The shells' prefilter keeps the broad URL-wide check: a miss there costs a candidate, never a wrong row) |
| 9 | **Medium** — `tabs.onRemoved` not chained with `update()` | ✅ real — the same read-modify-write race as v0.24.4, in a second place | **Fixed**: through `update()`; the harness now closes a tab while another tab is recording |
| 10 | **Medium** — "Clear browsing data" doesn't clear the captured finds | ✅ real — the URLs of a session stayed on screen after a wipe that the user asked for *because* of that session | **Fixed**: cookies/storage/cache **and** the find list + verdicts; the confirm says so, and so does `docs/SNIFFING.md` |
| 11 | **Low** — non-constant-time token comparison | ✅ real (loopback-only, so marginal) | **Fixed**: `secrets.compare_digest`, matching what `/jobs/{id}/stream` already did |
| 12 | **Low** — orphaned `target=_blank` WebViews | ✅ real — each popup is a whole Chromium instance and was never destroyed | **Fixed**: tracked and destroyed the moment its URL is handed over, plus in `onDestroy` |
| 13 | **Low** — README says v0.22.0; API table misses the new endpoints | ✅ real | **Fixed**: badge is current; `/classify`, `/sniff/patterns`, `/sniff/rank` are in the table |
| 14 | **Low** — FairPlay with an HTTPS key URI not detected | ✅ real — a `KEYFORMAT="com.apple.streamingkeydelivery"` playlist with `METHOD=AES-128` slipped through as downloadable, which the docs deny | **Fixed**: key-delivery formats are detected regardless of `METHOD`, with a test |
| 15 | **Low** — tautological tests / static substring checks | ⚠️ **partly right, and the worst one was already known** — a mutation check run here had shown that deleting the `offerBrowser()` call entirely still passed (`the promise exists` ≠ `the promise is reached`) | **Fixed where it matters**: assertions that the wiring is *reached* (`offerBrowser(e, url);`, `rankIfNeeded()` called, not only defined); the Download chip is tagged with its URL and an **on-device** test proves a live row carries it. The `FixtureServer` guard check is **kept deliberately** — it is a meta-test protecting the *meaning* of `HandoffTest`: remove the guard and that test would still pass while proving nothing. Still not covered end-to-end: the tap itself, which needs the engine in-process (noted in the test's docstring) |

## Where the regressions live

No new file: the tests went where the behaviour lives — `tests/test_rank.py`
(query strings, manifest attribution), `tests/test_classify.py` (FairPlay,
link-local refusal, LAN still allowed), `tests/test_sniff_shell_mirrors.py`
(hook hardening, chip tagging, clear-data), `tests/test_sniff_handoff.py`
(the wiring is reached), `extension/test_harness.mjs` (worker restart,
held-then-committed headers, tab-close race) and `SnifferTest.kt`
(finds survive concurrent adders; a live row carries its Download button).

Suite after the audit: **426 passed** (was 418), extension runtime checks ✅.

## Deliberate, not a bug (agy agreed)

- The loopback page key gating `GET /` on Android (CSRF defence, not a secret).
- AES-128 HLS without `SAMPLE-AES` is *downloadable*, and is classified as such.
- Two `pattern` lists (engine + shells) is the design; a test keeps the shells'
  lists a subset of the engine's.
- Cross-origin `blob:` players remain invisible without `androidx.webkit`.
