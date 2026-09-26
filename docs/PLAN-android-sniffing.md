# PLAN — "Capture anything": unsupported URLs on Android (+ better everywhere)

Status: **proposed**, 2026-09-26. Needs a go/no-go before M2.

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
| A page whose player builds the URL in JS (MSE / `blob:`) | ✗ nothing to extract — **this is the gap** |
| Any of the above, *desktop*, while the video is playing | extension sniffs the request + captures Cookie/UA/Referer ✓ |

So "unsupported URL" today means **JS-driven players**. Pasting a `.mp4` or
`.m3u8` link into suravidl on Android already works.

## 3. Why the fix is a browser, and why it needs two layers

- Chromium **never** calls `shouldInterceptRequest` for `blob:` URLs
  (intentional — issues.chromium.org/41377198). MSE players (`hls.js`,
  `dash.js`, Shaka) fetch segments and often never expose a plain media URL.
  Network interception alone is therefore not enough.
- The proven Android pattern (checked against the open-source
  `alexch33/super-video-downloader`): intercept **every** request in a WebView,
  classify candidates by asking the server again **with the page's cookies**
  (a `WebResourceRequest` exposes *request* headers only, never response
  headers — so a preflight fetch is how you learn `Content-Type`), and inject a
  JS interceptor at page start for the players that build URLs in JS.
- Rejected on purpose: VPN-based sniffers (NetGuard/PCAPdroid style) — needs
  the VPN permission, sees the whole device, hostile to this project's
  "no exposed surface" stance. Also rejected: root, MITM CA, hidden WebViews
  kept alive off-screen.

## 4. Design

### A. Engine = the shared brain (small, testable offline)

1. `POST /classify` — `{url, headers}` → `{kind: video|hls|dash|audio|image|drm|page|unknown, mime, size, final_url}`.
   `HEAD`, falling back to `GET Range: bytes=0-0`; HLS/DASH/DRM read from the
   first KB (`#EXT-X-KEY:…METHOD=SAMPLE-AES`, `<ContentProtection>`).
   Every shell uses it: Android's handoff list, the extension popup, the web UI.
2. Probe errors gain `unsupported: true` + a human `hint`, so the UI offers
   "look for the stream in the browser" instead of a red toast.
3. The canonical media pattern list gets **one owner** (here):
   `GET /sniff/patterns` → `{"ext": [...], "hints": [...]}`. The extension stops
   hard-coding `MEDIA_RE` (`extension/background.js:4`), Android fetches the
   list at boot with a baked-in fallback.

### B. Android: the in-app sniffer browser (the real work)

- `BrowserActivity` — WebView + URL bar + back/reload + an "**N found**" bar.
  Opened from the Download tab ("🔍 Find video on a page") or from the share
  flow when a page probes unsupported.
- `SnifferWebViewClient` — four capture layers, cheapest first:
  1. `shouldInterceptRequest` on every request: string match only (shared
     pattern list), no IO on that thread, returns null. Catches media loads and
     manifest XHR/fetch.
  2. `onLoadResource` — second net for anything layer 1 misses.
  3. **Document-start JS hooks** (`WebViewCompat.addDocumentStartJavaScript`,
     gated by `WebViewFeature.isFeatureSupported`; fallback: inject on
     `onPageStarted`, which is what the OSS app does): wrap `fetch`,
     `XMLHttpRequest.open`, the `HTMLMediaElement.src` setter and
     `URL.createObjectURL` (tag blobs, remember the manifest the player
     fetched), and post `{url, via}` to Kotlin via
     `WebViewCompat.addWebMessageListener` (allowed-origin allow-list;
     fallback: one tiny `@JavascriptInterface` object on old WebViews).
     **This is what makes MSE/blob players visible.**
  4. **Retro scan** on demand and at page stop:
     `performance.getEntriesByType('resource')` filtered by pattern — catches
     everything requested before our hooks existed, plus worker fetches.
- Dedupe, keep insertion order, cap per page (extension uses `KEEP_PER_TAB=20`
  — mirror it), remember the page URL for the `Referer`.
- Handoff: tapping a candidate → **Kotlin** (never the page) → engine
  `/classify` (kind/size/DRM judgement → UI says "HLS · 1080p · 42 MB" or
  "DRM-protected — can't do that"), then `/probe` with
  `{Cookie: CookieManager.getCookie(url), Referer: pageUrl, User-Agent: settings.userAgentString}`.
  Probe formats feed the **existing** format/preset UI; if probe cannot extract,
  fall back to a direct job with the same headers (`JobRequest.headers` already
  supports this).
- Security: the browser is sandboxed (`allowFileAccess=false`, no mixed
  content, no `file://`), and page JS can never reach the engine — only Kotlin
  speaks to `127.0.0.1:8787`, so the token stays out of the page.
- Privacy: browser cookies live in the app's WebView profile like any browser;
  "Clear browser data" joins Settings → Device; sniffed cookies are used **per
  job only** and are never written to the cookie vault.

### C. Desktop parity (small)

- Extension gains `onHeadersReceived` → records the response `Content-Type`
  for candidates (extensions *can* see response headers; a WebView cannot) and
  prefers manifests over segments (a `.ts`/`.m4s` hit offers its parent
  `.m3u8`).
- Popup shows kind/size from `/classify`; the probe-unsupported hint becomes a
  proper desktop affordance ("extension will find it — press play").

### D. Zero-code stopgap (optional, docs only)

Firefox for Android installs Mozilla-signed add-ons from file, and the engine's
CORS already allows `moz-extension://` origins. Signing the MV2 build as
*unlisted* on AMO would give Firefox-based sniffing on Android today with no app
code — at the cost of installing Firefox, installing the `.xpi`, and pasting
the engine token into the extension options (needs a "copy engine token" row in
Android Settings → Device). Worth a README paragraph; not a substitute for B.

## 5. Milestones

Each its own version + tagged release; TDD as usual; offline fixtures only.

- **M1 — engine brain** (v0.24.0): `/classify`, `/sniff/patterns`,
  `unsupported:true` probe errors; `tests/test_classify.py` + HLS/DASH/DRM head
  fixtures. Hours, no Android dependency — desktop gains value immediately.
- **M2 — Android browser + sniffer, no handoff** (v0.24.1): `BrowserActivity`,
  layers 1–2, candidate list UI, and an **offline instrumentation test** (a
  `ServerSocket` fixture server serves a page whose script fetches
  `/fixture.m3u8`; assert the sniffer collected it), plus a manual pass on the
  phone.
- **M3 — handoff + JS hooks** (v0.24.2): layers 3–4, `/classify` call,
  cookies/UA/referer handoff, "N found → Download", probe-unsupported prompt
  from the share path, "Clear browser data".
- **M4 — desktop parity + docs** (v0.24.3): `onHeadersReceived`,
  manifest-over-segments, README capture matrix, Firefox-Android stopgap +
  engine-token row.

Backlog after that: live/HLS-growing streams; subtitle capture for sniffed
streams; per-site memory "this site needs the browser".

## 6. Risks & honest limits

- **DRM stays out** (Widevine/PlayReady). The sniffer will *find* DRM
  manifests; `/classify` marks them and the UI says so instead of failing at
  60%.
- **MSE with no manifest and no discoverable URL** (some live/obfuscated
  players) can still come up empty — the browser says "play 5–10 s, then Scan
  again"; segments-only capture is a documented non-goal for now.
- **Sniffed URLs expire** (signed CDN tokens) → handoff downloads immediately;
  persisted job headers keep retries working.
- **Arms race**: sites obfuscating URLs will need the JS-hook layer — that is
  why it is in the design, not an afterthought.
- APK grows ~0 (system WebView), no new permissions, no VPN, no root.

## 7. Decisions needed

1. Build B (in-app browser) at all — it is the only real answer for Android.
2. Firefox-Android stopgap: document it, or skip?
3. Order: M1 first (engine; helps desktop now), then M2/M3?
