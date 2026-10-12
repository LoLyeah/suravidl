# Surfaces Security and Architecture Audit: suravidl

## 1. Executive Summary & Scope

This audit evaluates the surfaces of **suravidl** outside the Python engine domain, covering:
- Web UI frontend (`src/suravidl_engine/web/app.js`, `index.html`, `style.css`)
- Browser Extension (`extension/` for Chromium MV3 and Firefox MV2)
- Android WebView shell & native bridge (`android/app/`)
- CI/CD workflow security (`.github/workflows/`)
- Cross-boundary desktop glue (`src/suravidl_engine/__main__.py`) & CORS configuration (`src/suravidl_engine/api.py`)

Trust Model Baseline: The engine serves one local user over loopback. An attacker on the local network is treated as an accepted design trade-off, but surfaces reachable unauthenticated from a web page (via CORS, extension origins, or WebView bridges) are audited strictly.

---

## 2. Exhaustive XSS Enumeration: `app.js` `innerHTML` Sinks

Across `src/suravidl_engine/web/app.js` (6,393 lines), exactly 11 occurrences of `innerHTML` exist. Each site has been inspected and classified:

| # | File:Line | Code Snippet | Classification | Reachability & Safety Verdict |
|---|---|---|---|---|
| 1 | `src/suravidl_engine/web/app.js:891` | `s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-' + name + '"/></svg>';` | **Interpolated value** | **Latent Risk / Safe in Practice**: Concatenates `name` parameter into SVG string. Current call sites (`app.js:2965`, `app.js:3285`, `app.js:5228`) pass static literals (`"trash"`, `"info"`). Hostile titles/remote filenames never reach here. |
| 2 | `src/suravidl_engine/web/app.js:1734` | `box.innerHTML = "";` | **Static string** | **Safe**: Clears format picker options container. |
| 3 | `src/suravidl_engine/web/app.js:1742` | `box.innerHTML = "";` | **Static string** | **Safe**: Clears format picker options container on probe reset. |
| 4 | `src/suravidl_engine/web/app.js:1978` | `tb.innerHTML = "";` | **Static string** | **Safe**: Clears playlist table body. |
| 5 | `src/suravidl_engine/web/app.js:2103` | `box.innerHTML = "";` | **Static string** | **Safe**: Clears playlist format selection container. |
| 6 | `src/suravidl_engine/web/app.js:2689` | `sel.innerHTML = "";` | **Static string** | **Safe**: Clears preset selector `<select>` element. |
| 7 | `src/suravidl_engine/web/app.js:3035` | `chev.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-chev"/></svg>';` | **Static string** | **Safe**: Static inline SVG chevron icon markup. Remote titles/URLs on line 3036 are appended via `document.createTextNode()`. |
| 8 | `src/suravidl_engine/web/app.js:4310` | `box.innerHTML = "";` | **Static string** | **Safe**: Clears subtitles format selection box. |
| 9 | `src/suravidl_engine/web/app.js:5088` | `box.innerHTML = "";` | **Static string** | **Safe**: Clears yt-dlp advanced configuration container. |
| 10 | `src/suravidl_engine/web/app.js:5153` | `sel.innerHTML = "";` | **Static string** | **Safe**: Clears default preset selector `<select>`. |
| 11 | `src/suravidl_engine/web/app.js:5200` | `box.innerHTML = "";` | **Static string** | **Safe**: Clears preset list container. |

**Remote Data Handling**: Remote titles, error messages, and filenames generated via `yt-dlp` are bound exclusively using safe DOM primitives: `element.textContent` (defined in helper `el()` at `app.js:38`) and `document.createTextNode()` (e.g. `app.js:3036`). No active XSS vulnerability was identified in `app.js`.

---

## 3. Findings

### Finding 1: Permissive Extension Origin CORS Regex Allows Any Extension to Drive Local Engine & Expose API Token
- **Severity**: P1
- **Evidence**:
  - `src/suravidl_engine/api.py:396`:
    ```python
    allow_origin_regex=r"^(chrome-extension://[a-p]{32}|moz-extension://[0-9a-zA-Z-]{6,64})$",
    ```
  - `src/suravidl_engine/api.py:528-538`:
    ```python
    if page_key and k != page_key:
        raise HTTPException(status_code=401,
                            detail="this page needs its shell's key")
    html = (_web_dir() / "index.html").read_text(encoding="utf-8")
    cfg = json.dumps({"token": auth_token or "", ...})
    return HTMLResponse(html.replace('"__CFG__"', cfg))
    ```
  - `src/suravidl_engine/__main__.py:1415`:
    ```python
    url = f"http://127.0.0.1:{port}/"
    ```
- **What**: `CORSMiddleware` in `api.py` allows cross-origin requests from *any* Chrome extension (`chrome-extension://[a-p]{32}`) and *any* Firefox extension UUID (`moz-extension://[0-9a-zA-Z-]{6,64}`). Furthermore, on desktop shells, `page_key` is not configured, meaning unauthenticated `GET /` requests successfully return `index.html` with `auth_token` embedded in `window.__SURAVIDL__`.
- **Why it matters**: Any third-party browser extension installed in the user's browser (adware, coupon scrapers, malicious extensions) can issue a cross-origin `fetch("http://127.0.0.1:8787/")`, parse `window.__SURAVIDL__.token`, and obtain the engine's API token. With this token, the rogue extension can interact with all API endpoints (`POST /jobs`, read files, change settings, trigger shell operations).
- **Fix direction**: On desktop, generate and require a `page_key` like Android does (`EngineService.kt:84`), or do not embed the API token in `index.html`. For Chrome, pin the allowed CORS origin to the specific extension ID rather than a wildcard 32-character pattern.

---

### Finding 2: Extension Message Handler (`chrome.runtime.onMessage`) Lacks Sender Verification for Privileged Actions
- **Severity**: P1
- **Evidence**:
  - `extension/background.js:231-280`:
    ```javascript
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (msg && msg.type === "getMedia") { ... }
      if (msg && msg.type === "rank") { rankWithEngine(msg.items || []).then(sendResponse); return true; }
      if (msg && msg.type === "engineState") { engineState().then(sendResponse); return true; }
      if (msg && msg.type === "sendHandoff") { sendHandoff(msg.url, msg.urls, msg.tabUrl).then(sendResponse); return true; }
      if (msg && msg.type === "sendToEngine") { sendToEngine(msg.url).then(sendResponse); return true; }
      if (msg && msg.type === "sendBatch") { sendBatchToEngine(msg.urls).then(sendResponse); return true; }
      if (msg && msg.type === "recentJobs") { recentJobs().then(sendResponse); return true; }
      if (msg && msg.type === "pageFind") {
        const tabId = _sender && _sender.tab ? _sender.tab.id : undefined;
        ...
    ```
- **What**: While the `pageFind` message checks `_sender.tab.id` (line 272), all other message actions (`sendHandoff`, `sendToEngine`, `sendBatch`, `recentJobs`, `getMedia`) accept messages without verifying the sender's origin or context.
- **Why it matters**: `chrome.runtime.onMessage` receives messages from both extension UI contexts (popup/options) and content scripts injected into web pages. Because `pagefind.js` is injected into `<all_urls>` across all frames, any compromised content script or extension context can invoke `sendToEngine` or `sendBatch` to dispatch unauthorized download jobs to the local engine using the extension's stored API token, or query `recentJobs` to spy on active downloads.
- **Fix direction**: Verify that `!_sender.tab` (or `_sender.url === chrome.runtime.getURL("popup.html")`) for all privileged management actions in `background.js`, ensuring content scripts can only send `pageFind` events.

---

### Finding 3: In-Memory Request Headers in MV3 Service Worker Cause Silent Header/Cookie Loss
- **Severity**: P2
- **Evidence**:
  - `extension/background.js:122`:
    ```javascript
    const pending = new Map();
    ```
  - `extension/background.js:170`:
    ```javascript
    holdHeaders(details.url, pick);
    ```
  - `extension/background.js:191-194`:
    ```javascript
    const held = pending.get(details.url);
    if (held) commitHeaders(details.url, held);
    pending.delete(details.url);
    ```
- **What**: Captured request headers (`Cookie`, `User-Agent`, `Referer`, `Origin`) for non-obvious media requests are cached in an in-memory `Map` (`pending`) until the response headers verify the `Content-Type`.
- **Why it matters**: Chrome Manifest V3 service workers are ephemeral and terminate after 30 seconds of inactivity. If the worker terminates while media requests are in flight, `pending` is wiped. When the response arrives and wakes the worker, `pending.get(details.url)` returns `undefined`, permanently discarding the auth cookies and headers required to download the stream.
- **Fix direction**: Store pending headers in `chrome.storage.session` (or `chrome.storage.local` with timestamp-based pruning) rather than in-memory variables.

---

### Finding 4: Firefox Manifest Requests Unused `webRequestBlocking` Permission
- **Severity**: P2
- **Evidence**:
  - `extension/firefox/manifest.json:6`:
    ```json
    "permissions": ["webRequest", "webRequestBlocking", "storage", "menus", "<all_urls>"],
    ```
  - `extension/background.js:138-175`:
    ```javascript
    chrome.webRequest.onBeforeRequest.addListener(..., { urls: ["<all_urls>"] });
    chrome.webRequest.onBeforeSendHeaders.addListener(..., ["requestHeaders"].concat(EXTRA_HEADERS));
    ```
- **What**: The Firefox Manifest V2 declares `webRequestBlocking` in its `permissions`, but `extension/background.js` never passes `"blocking"` to any `chrome.webRequest` listener.
- **Why it matters**: Demanding synchronous blocking interception capability without actually modifying or blocking requests violates the principle of least privilege, widens the permission surface, and creates severe scrutiny and rejection risks during Mozilla Add-ons (AMO) review.
- **Fix direction**: Remove `"webRequestBlocking"` from `extension/firefox/manifest.json`.

---

### Finding 5: Application-Wide Cleartext Traffic Allowed on Android
- **Severity**: P2
- **Evidence**:
  - `android/app/src/main/AndroidManifest.xml:17`:
    ```xml
    android:usesCleartextTraffic="true">
    ```
- **What**: The Android manifest enables `android:usesCleartextTraffic="true"` globally at the `<application>` level.
- **Why it matters**: Loopback HTTP communication with the engine on `127.0.0.1:8787` requires cleartext support. However, setting this globally permits unencrypted HTTP traffic across the entire application, including external navigations in `BrowserActivity` and any external network connections, exposing user traffic on untrusted Wi-Fi.
- **Fix direction**: Remove `android:usesCleartextTraffic="true"` and specify `android:networkSecurityConfig="@xml/network_security_config"` restricting cleartext HTTP solely to `127.0.0.1` and `localhost`.

---

### Finding 6: In-App Browser `SniffBridge` Allows Untrusted Remote Pages to Spoof Media Detections
- **Severity**: P2
- **Evidence**:
  - `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:132`:
    ```kotlin
    webView.addJavascriptInterface(SniffBridge(), "SuravidlSniff")
    ```
  - `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:916-921`:
    ```kotlin
    inner class SniffBridge {
        @android.webkit.JavascriptInterface
        fun report(url: String?, via: String?, frame: String?) {
            SniffLog.add(url ?: return, via ?: "hook", frame ?: "", false)
        }
    }
    ```
  - `android/app/src/main/java/com/suravidl/app/Sniff.kt:63-79`:
    ```kotlin
    fun add(url: String, via: String, frame: String, mainFrame: Boolean): Boolean { ... }
    ```
- **What**: `BrowserActivity` exposes the `SuravidlSniff` interface to all third-party web pages loaded inside the in-app browser. The `report` method accepts arbitrary `url`, `via`, and `frame` strings without caller authentication.
- **Why it matters**: Any hostile webpage visited in `BrowserActivity` can execute `window.SuravidlSniff.report("http://...", "player", location.href)`. This allows an attacker to flood or poison the `SniffLog` table with attacker-controlled URLs, displace legitimate media items, and mislead the user into queueing malicious or unintended links for download.
- **Fix direction**: Generate a secret token per page load that only the injected `SniffScript` receives, and validate the token inside `report()`, or cross-verify reported URLs against intercepted network requests.

---

### Finding 7: Direct Expression Interpolation in GitHub Actions Shell Script
- **Severity**: P2
- **Evidence**:
  - `.github/workflows/android.yml:58-60`:
    ```yaml
    - name: Restore signing keystore
      run: |
        echo "${{ secrets.ANDROID_KEYSTORE_B64 }}" | base64 -d > "$RUNNER_TEMP/suravidl-release.keystore"
        echo "ANDROID_KEYSTORE_FILE=$RUNNER_TEMP/suravidl-release.keystore" >> "$GITHUB_ENV"
    ```
- **What**: The base64-encoded signing keystore secret is expanded directly into the inline bash script text using `${{ ... }}` syntax rather than an environment variable.
- **Why it matters**: Direct expression expansion in `run:` blocks is an unsafe GitHub Actions pattern. If a secret contains special shell characters or quotes, it can result in shell syntax corruption or command injection.
- **Fix direction**: Pass the secret via the step's `env:` block (e.g., `env: KEYSTORE_B64: ${{ secrets.ANDROID_KEYSTORE_B64 }}`) and reference it inside bash as `"$KEYSTORE_B64"`.

---

### Finding 8: Unsafe String Concatenation in `ico()` Helper in `app.js`
- **Severity**: P3
- **Evidence**:
  - `src/suravidl_engine/web/app.js:888-894`:
    ```javascript
    function ico(name) {
      const s = document.createElement("span");
      s.className = "ico";
      s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-' +
        name + '"/></svg>';
      return s;
    }
    ```
- **What**: The `ico()` utility function concatenates the `name` argument directly into an SVG HTML string assigned to `innerHTML`.
- **Why it matters**: While current call sites in `app.js` pass static strings (`"trash"`, `"info"`), the helper accepts dynamic arguments and constitutes a latent XSS sink if ever connected to user-controlled or remote data.
- **Fix direction**: Validate `name` against an allowlist of valid icon IDs or create SVG elements using `document.createElementNS` and `setAttribute`.

---

### Finding 9: Overly Broad `FileProvider` Path Configuration on Android
- **Severity**: P3
- **Evidence**:
  - `android/app/src/main/res/xml/file_paths.xml:6-10`:
    ```xml
    <paths xmlns:android="http://schemas.android.com/apk/res/android">
        <external-files-path name="external_files" path="." />
        <!-- apk updates live in cache/updates; only this subdirectory is exposed, keeping the rest of cache private -->
        <cache-path name="cache_updates" path="updates" />
    </paths>
    ```
- **What**: `file_paths.xml` configures `<external-files-path name="external_files" path="." />`.
- **Why it matters**: Exposing the entire external files root directory (`Android/data/com.suravidl.app/files/`) allows any file stored in the external app directory (including sensitive logs or temporary data) to be shared via `FileProvider.getUriForFile` if a path is passed to `openFile` or `shareFile`.
- **Fix direction**: Scope `<external-files-path>` to specific download subdirectories (e.g. `path="downloads"`).

---

### Finding 10: Broad Extension Content Script Injection at `document_start` Across All Frames
- **Severity**: P3
- **Evidence**:
  - `extension/manifest.json:7,11-14`:
    ```json
    "host_permissions": ["<all_urls>"],
    "content_scripts": [
      {
        "matches": ["<all_urls>"],
        "js": ["pagefind.js"],
        "run_at": "document_start",
        "all_frames": true
      }
    ]
    ```
  - `extension/firefox/manifest.json:6,10-13`:
    ```json
    "permissions": ["webRequest", "webRequestBlocking", "storage", "menus", "<all_urls>"],
    "content_scripts": [
      {
        "matches": ["<all_urls>"],
        "js": ["pagefind.js"],
        "run_at": "document_start",
        "all_frames": true
      }
    ]
    ```
- **What**: Both manifests request `<all_urls>` and inject `pagefind.js` at `document_start` across all frames (`all_frames: true`).
- **Why it matters**: Running content scripts in every iframe on every web page increases the attack surface and incurs overhead on complex pages with numerous third-party advertising or analytics iframes.
- **Fix direction**: Restrict content script execution to top-level frames or load dynamically upon detecting media requests.

---

### Finding 11: Discrepancy Between Shipped `LICENSE` and AMO Submission Documentation
- **Severity**: P3
- **Evidence**:
  - `docs/AMO-SUBMISSION.md:52-56`:
    ```markdown
    4. **Decide the licence.** AMO refuses a listing without one, and the repo
       currently has none. `docs/amo-metadata.json` is filled in with **MIT**;
       change `version.license` (and drop a `LICENSE` file in the repository)...
    ```
  - `LICENSE:1`:
    ```text
    MIT License
    ```
- **What**: `docs/AMO-SUBMISSION.md` asserts that the repository has no license and instructs the maintainer to drop a `LICENSE` file, but an MIT `LICENSE` file is already committed at the repository root.
- **Why it matters**: Inaccurate documentation creates confusion and inconsistency during package release and store submission checks.
- **Fix direction**: Update `docs/AMO-SUBMISSION.md` to reflect that `LICENSE` is present in the repository root.

---

### Finding 12: Emoji Glyph in Window Title Violates Brand & UI System Guidelines
- **Severity**: P3
- **Evidence**:
  - `src/suravidl_engine/web/app.js:871`:
    ```javascript
    document.title = t("🐴 suravidl");
    ```
  - `DESIGN.md:3`:
    ```markdown
    (2) one frost per dialog, drawn icons not glyphs
    ```
  - `src/suravidl_engine/web/index.html:29-30`:
    ```html
    <!-- one drawn icon system: stroke SVGs, never borrowed glyphs (emoji render
         in a different face on Android — the shell where it shows most) -->
    ```
- **What**: `applyLanguageChrome()` in `app.js` prepends a horse emoji glyph (`🐴`) to `document.title`.
- **Why it matters**: Contradicts the explicit house law defined in DESIGN.md rule (2) ("drawn icons not glyphs") and the index.html design rule prohibiting borrowed emoji glyphs.
- **Fix direction**: Update `app.js:871` to `document.title = t("suravidl");`.

---

## 4. Ranked Top 5 Findings

1. **[P1] Permissive Extension Origin CORS Regex Allows Any Extension to Drive Local Engine & Expose API Token** (`src/suravidl_engine/api.py:396`, `src/suravidl_engine/api.py:528-538`, `src/suravidl_engine/__main__.py:1415`)
2. **[P1] Extension Message Handler (`chrome.runtime.onMessage`) Lacks Sender Verification for Privileged Actions** (`extension/background.js:231-280`)
3. **[P2] In-Memory Request Headers in MV3 Service Worker Lead to Silent Header/Cookie Loss on Termination** (`extension/background.js:122-129`, `extension/background.js:170`, `extension/background.js:191-194`)
4. **[P2] In-App Browser `SniffBridge` Allows Untrusted Remote Pages to Spoof Media Detections** (`android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:132`, `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:916-921`)
5. **[P2] Application-Wide Cleartext Traffic Allowed on Android** (`android/app/src/main/AndroidManifest.xml:17`)
