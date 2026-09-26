# PLAN — "Capture anything": unsupported URLs on Android (+ better everywhere)

Status: **revised v2**, 2026-09-26 — after testing a real JS-only player live
(see §3). **M1 shipped (v0.24.0), M2 shipped (v0.24.1), M3 shipped (v0.24.2)** —
the browser finds streams *and* hands them to the engine with its own cookies,
User-Agent and referer. M4 (desktop parity + docs) is next.

## 1. The question

*"Is it possible to download a video from a URL yt-dlp doesn't support? On
desktop the extension does that — how do we do it on Android?"*

Short answer: **yes, and more of it already works than it looks.** What Android
is missing is a *sniffer* — something that watches what the page actually
loads and hands us the real media URL. On desktop that is the MV3/Firefox
extension (`webRequest`). Android has no extension model, so it has to live in
the app.

## 2. What already works today

Verified against a live engine (`:8809`, 2026-09-26):

| Input | Result |
|---|---|
| Raw media URL (`https://…/sample-5s.mp4`) | `/probe` → `"direct": true`, formats listed → downloads ✓ |
| HLS manifest (`https://…/x36xhzz.m3u8`) | formats extracted (`protocol: m3u8_native`) → downloads ✓ |
| A page whose `<video><source src=…>` is real HTML (w3schools) | yt-dlp's **generic extractor** found the mp4 → playlist of 2 ✓ |
| A JS-only player (tested: `vidmonstr.com/e/<id>`, §3) | `ERROR: Unsupported URL` — **the gap** |
| Any of the above, *desktop*, while the video is playing | extension sniffs the request + captures Cookie/UA/Referer ✓ |

So "unsupported URL" today means **JS-driven players**. Pasting a `.mp4` or
`.m3u8` link into suravidl on Android already works.

## 3. Case study — a JS-only player, tested live

The site: `vidmonstr.com/e/<id>`, an ad-heavy adult streaming embed behind
Cloudflare. The exact asset stays in the manual test list, not in this repo.

What the test found:

- **yt-dlp: `ERROR: Unsupported URL`.** No generic-extractor fallback — the
  page carries no extractable media markup.
- **The page has no `<video>` at all.** The player is a **same-origin iframe**
  (`/ip129jk?id=<hex>&t=<JWT>`) whose JS is **obfuscated and booby-trapped**
  (a `placeholder_anti_debug` helper) and holds `videoId` + `viewToken`; it
  builds its own media plumbing. Nothing media-shaped is requested until a real
  gesture happens.
- **A document-start script DOES run inside subframes.** With hooks installed
  before navigation, a live MSE player in that page produced a full chain:

  ```
  media.src       → https://<cdn>/…/<id>.20.mp4
  createObjectURL → blob:https://<origin>/<uuid>  [MediaSource]
  source.src      → blob:https://<origin>/<uuid>
  addSourceBuffer → MSE:video/mp4; codecs="avc3.42e01e, mp4a.40.2"
  currentSrc      → blob:https://<origin>/<uuid>
  ```

  Two conclusions, both now design requirements:
  1. Interception (`shouldInterceptRequest` / `webRequest`) **cannot** see this
     — Chromium never reports `blob:` requests (issues.chromium.org/41377198).
     The JS-hook layer is the only thing that can, so it is not optional.
  2. Hooks must run in **every frame**, not just the main one — validated live.
- **The captured MSE chain belonged to an ad, not the video.** The site's ad
  jungle (pop-unders, a webcam-ad creative with its own MSE player, several
  tracker XHRs) is ~100% of the request stream until the user actually plays.
  Consequence: never show raw URL patterns to the user — classify first (§4A).
- **Headless clicking could not start the real player** (ad gate + gesture +
  anti-debug; the player surface measured 0×0 and the ad layer swallowed the
  clicks). That is fine and *informative*: capture is a **user-driven** act.
  The app watches while the user presses play on their own phone with their own
  session — which is also exactly what the desktop extension does, and what
  keeps cookies/clearance valid.

### What this changes in the plan

1. Hooks (layer 3) run in **all frames**; each capture records the **frame URL**
   as well as the page URL — the Referer a signed media URL wants is often the
   *player iframe*, not the outer page.
2. Candidates are **classified before they are shown** (`/classify`, §4A):
   kind, MIME, size, DRM. Ad creatives drop out by MIME, not by domain lists.
3. The list is **ranked by "what you're watching"**: the candidate equal to the
   top-level player's `currentSrc` / last `media.src` goes first. This is the
   single most useful signal on an ad-soaked page.
4. UX copy is honest: *"Press play for a second, then tap Found."* The sniffer
   does not defeat ad gates, anti-bot or anti-debug code — it captures what the
   user's own session fetches, which is all any downloader can honestly claim.

## 4. Design

### A. Engine = the shared brain (small, testable offline)

1. `POST /classify` — `{url, headers}` → `{kind: video|hls|dash|audio|image|drm|page|unknown, mime, size, final_url}`.
   `HEAD`, falling back to `GET Range: bytes=0-0`; HLS/DASH/DRM read from the
   first KB (`#EXT-X-KEY:…METHOD=SAMPLE-AES`, `<ContentProtection>`). Used by
   every shell: the Android handoff list, the extension popup, the web UI.
2. Probe errors gain `unsupported: true` + a human `hint`, so a UI offers
   "look for the stream in the browser" instead of a red toast (this is the
   `vidmonstr` path).
3. The canonical media pattern list gets **one owner** (here):
   `GET /sniff/patterns` → `{"ext": [...], "hints": [...]}`. The extension stops
   hard-coding `MEDIA_RE` (`extension/background.js:4`); Android fetches the
   list at boot with a baked-in fallback. Patterns are a *prefilter only* —
   they decide what gets classified, never what gets shown.

### B. Android: the in-app sniffer browser (the real work)

- `BrowserActivity` — WebView + URL bar + back/reload + an "**N found**" bar.
  Opened from the Download tab ("🔍 Find video on a page") or from the share
  flow when a page probes unsupported.
- `SnifferWebViewClient` — four capture layers, cheapest first:
  1. `shouldInterceptRequest` on every request: string match only (shared
     pattern list), no IO on that thread, returns null. Catches media loads and
     manifest XHR/fetch — **not** `blob:` (Chromium by design).
  2. `onLoadResource` — second net for anything layer 1 misses.
  3. **Document-start JS hooks in every frame**
     (`WebViewCompat.addDocumentStartJavaScript` — or, on current
     androidx.webkit, its successor `addJavaScriptOnEvent` — gated by
     `WebViewFeature.isFeatureSupported`; fallback: inject on `onPageStarted`,
     which is what the working OSS app does). Hooks wrap `fetch`,
     `XMLHttpRequest.open`, the `HTMLMediaElement.src` / `HTMLSourceElement.src`
     setters, `URL.createObjectURL` (tags MSE/blob and keeps the manifest the
     player fetched) and `MediaSource.addSourceBuffer`. Results post to Kotlin
     via `WebViewCompat.addWebMessageListener` (allowed-origin allow-list;
     fallback: one tiny `@JavascriptInterface` object on old WebViews).
     **This is the only layer that sees MSE players.**
  4. **Retro scan** on demand and at page stop:
     `performance.getEntriesByType('resource')` filtered by pattern — catches
     everything requested before our hooks existed, plus worker fetches.
- Candidate record: `{url, via, frameUrl, pageUrl, seenAt}`; dedupe, keep
  insertion order, cap per page (extension uses `KEEP_PER_TAB=20`; mirror it).
- Handoff: tapping a candidate → **Kotlin** (never the page) → `/classify` →
  the UI shows "HLS · 1080p · 42 MB" / "DRM-protected — can't do that" →
  `/probe` with headers `{Cookie: CookieManager.getCookie(url), Referer:
  frameUrl ?? pageUrl, User-Agent: settings.userAgentString}`. Probe's formats
  feed the **existing** quality/preset UI; if probe cannot extract, fall back
  to a direct job with the same headers (`JobRequest.headers` already supports
  it).
- Ranking: "what you're watching" (top-level `currentSrc` / last `media.src`)
  first, then manifests, then progressive files; ad creatives drop out by MIME.
- Security: the browser is sandboxed (`allowFileAccess=false`, no mixed
  content, no `file://`), and page JS can never reach the engine — only Kotlin
  speaks to `127.0.0.1:8787`, so the token never reaches a page.
- Privacy: browser cookies live in the app's WebView profile like any browser;
  "Clear browser data" joins Settings → Device; sniffed cookies are used **per
  job only** and never written to the cookie vault.

### C. Desktop parity (small)

- Extension gains `onHeadersReceived` → records the response `Content-Type`
  for candidates (extensions *can* see response headers; a WebView cannot) and
  prefers manifests over segments (a `.ts`/`.m4s` hit offers its parent
  `.m3u8`).
- Popup shows kind/size from `/classify` and uses the same "now playing"
  ranking; the probe-unsupported hint becomes a proper desktop affordance
  ("extension will find it — press play").

### D. Zero-code stopgap (optional, docs only)

Firefox for Android installs Mozilla-signed add-ons from file, and the engine's
CORS already allows `moz-extension://` origins. Signing the MV2 build as
*unlisted* on AMO would give Firefox-based sniffing on Android today with no app
code — at the cost of installing Firefox, installing the `.xpi`, and pasting
the engine token into the extension options (needs a "copy engine token" row in
Android Settings → Device). Worth a README paragraph; not a substitute for B.

## 5. Milestones

Each its own version + tagged release; TDD as usual; offline fixtures only.

- **M1 — engine brain** (v0.24.0, **shipped**): `/classify`, `/sniff/patterns`,
  `unsupported:true` probe errors; `tests/test_classify.py` + HLS/DASH/DRM head
  fixtures; and a regression test built on §3: a page yt-dlp refuses must come
  back as `unsupported` **with the browser hint**. Hours, no Android
  dependency — desktop gains value immediately.
- **M2 — Android sniffer browser** (v0.24.1, **shipped**): `BrowserActivity`
  with all four layers — `shouldInterceptRequest`, `onLoadResource`, the JS
  hooks (also injected into *same-origin* child frames, each report carrying
  the frame's URL) and the `performance`-timeline sweep — plus the candidate
  list, a host-gated entry point in the Download tab, and the offline
  instrumentation test this section asked for. **No new dependency and no new
  permission**: the system WebView *is* the browser, and `androidx.webkit` —
  the only thing that would reach a *cross-origin* frame's scripts — is
  deferred to M3 by choice. Measured cost: **+20 KB** on the debug APK.
- **M3 — the handoff** (v0.24.2, **shipped**): every find carries the engine's
  verdict (`POST /classify`, sent with the headers a guarded URL needs even to be
  looked at) and a Download button that posts to `/jobs` with this WebView's
  cookie jar, its own User-Agent, and the **frame** it came from as the referer
  — frame-first, per §4. DRM and `blob:`/`mse:` rows explain themselves instead
  of offering a button that cannot work; "Clear browsing data" takes the word;
  and an "unsupported URL" probe answer now offers "Open in the browser ↗", the
  consumer the M1 structured error was built for. Verified by an instrumented
  test against a **guarded** fixture — 403 without the browser's cookie *and*
  referer — so a green run means the captured headers reached yt-dlp.
  `androidx.webkit` still not taken: the cross-origin-frame gap stays open, on
  purpose.
- **M4 — desktop parity + docs** (v0.24.3): `onHeadersReceived`,
  manifest-over-segments, README capture matrix, Firefox-Android stopgap +
  engine-token row, and a short `docs/SNIFFING.md` stating what is and is not
  promised.
- **Manual checklist on the phone** (not CI): (1) the §3 site — press play,
  tap Found; (2) an ordinary `<video>` page; (3) a plain `.mp4` link; (4) an
  HLS demo stream; (5) a DRM sample (must say "can't do that").

Backlog after that: live/HLS-growing streams; subtitle capture for sniffed
streams; per-site memory "this site needs the browser"; and a per-ABI APK split
(arm64-only release, x86_64 kept for the emulator — that half is 22.8 MB of the
35.6 MB APK), parked by decision in favour of M2→M4 first.

## 6. Risks & honest limits

- **Ad gates, anti-bot and anti-debug code are not our fight.** The sniffer
  captures what the user's own session fetches while they watch. If a site
  never hands media to the browser (DRM, obfuscated segment-only MSE), the UI
  says exactly that instead of pretending.
- **DRM stays out** (Widevine/PlayReady). The sniffer will *find* DRM
  manifests; `/classify` marks them and the UI says so instead of failing at
  60%.
- **MSE with no manifest and no discoverable URL** (some live/obfuscated
  players) can still come up empty — the browser says "play a few seconds, then
  Scan again"; segments-only capture is a documented non-goal for now.
- **Sniffed URLs expire** (signed CDN tokens, JWTs — the tested site's player
  URL carries a `t=<JWT>`): handoff downloads immediately; persisted job
  headers keep retries working.
- **Ad/tracker noise is enormous** on these pages — classification and ranking
  are load-bearing, not polish.
- APK grows ~0 (system WebView), no new permissions, no VPN, no root.

## 7. Decisions needed

1. Build B (in-app browser) at all — it is the only real answer for Android.
2. Firefox-Android stopgap: document it, or skip?
3. Order: M1 first (engine; helps desktop now), then M2/M3?
