# Raw audit — Play Protect "may be harmful" (October 2026)

Unedited output of an independent read-only audit of the tagged tree
(v0.47.13), run with Gemini via Antigravity. Findings were re-checked by
hand before any fix; what was accepted, corrected or deliberately left as
design is recorded in `docs/SECURITY.md`, which is the authoritative page.
Severity labels here are the auditor's.

# Google Play Protect Security & Heuristic Audit Report

**Target**: `suravidl` Android Application (`com.suravidl.app`, version `0.47.13`, versionCode `166`)  
**Context**: Google Play Protect flagged sideloaded update as "potentially harmful application" (PHA).  
**Mode**: Read-only static analysis and architecture audit.

---

## 1. Executive Verdict & Play Protect Heuristics Assessment

Google Play Protect's "this app may be harmful" flag on `com.suravidl.app` is triggered by a combination of high-confidence heuristic signatures typical of Potentially Harmful Applications (PHAs). Specifically, the APK combines:

1. **`REQUEST_INSTALL_PACKAGES` + Automated APK Downloader (Dropper/Downloader Heuristic)**:  
   The manifest requests `REQUEST_INSTALL_PACKAGES` (`AndroidManifest.xml:7`), while the engine downloads release APKs from GitHub into app cache (`updater.py:389-438`), and the UI dispatches `Intent.ACTION_VIEW` targeting package installation (`MainActivity.kt:504-533`). Play Protect categorizes non-store apps downloading and installing executable packages as Droppers.
2. **Dynamic Code Loading (DCL / Backdoor Heuristic)**:  
   The engine implements dynamic updating of the `yt-dlp` Python package (`ytdlp_update.py:412-474`). On Android (Chaquopy), the app downloads a Python wheel (`.whl`) from PyPI over the network, unpacks `.py` files into the private app storage directory (`filesDir/ytdlp`), and on boot dynamically injects that path to the front of `sys.path` via `sys.path.insert(0, str(shadow))` (`ytdlp_update.py:171-175`, `__main__.py:203-207`). Executing dynamically downloaded code outside the signed APK package is a primary Play Protect DCL flag.
3. **Execution of Downloaded Native Binaries (`tools.py`)**:  
   The bundled Python engine ships `tools.py:25-51, 115-164`, which exposes `POST /tools/ffmpeg` (`api.py:679-685`). This endpoint downloads a standalone Linux ELF binary from GitHub (`ffmpeg-static`), saves it into app data, marks it executable with `os.chmod(tmp_bin, stat.S_IRWXU)`, and prepares to execute it via `cut.py:48-50`. Even though Android SELinux / W^X prevents executing binaries from writable storage on API 29+, the presence of binary-downloading and `chmod +x` routines triggers static malware signatures.
4. **Disguised Executable ELF Binaries in `jniLibs` (`libffmpeg.so`, `libffprobe.so`)**:  
   `scripts/build_ffmpeg_android.sh:11-20` compiles static ELF executables (type `ET_EXEC`) and renames them to `libffmpeg.so` and `libffprobe.so`. The app enables `useLegacyPackaging = true` (`build.gradle:64`) to force extraction into `nativeLibraryDir`, where `SuravidlApp.kt:174-183` runs `Os.chmod` to grant `0755` permissions, allowing Python (`cut.py:41`, `jobs.py:325`) to invoke them as external CLI processes. Play Protect heuristics identify disguised ELF executables in `lib/` as evasive payload bundling.
5. **WebView JavaScript Bridges on Untrusted Remote Content**:  
   `BrowserActivity.kt:156` attaches an `@JavascriptInterface` bridge (`SuravidlSniff`) to a general-purpose browser that visits arbitrary external URLs, while `MainActivity.kt:90` attaches `HostBridge` exposing package installer launches and file provider handoffs. Play Protect heuristic scanners penalize the exposure of native interfaces inside WebViews.
6. **Local Loopback Daemon & Cleartext Communication**:  
   The app runs an embedded Python HTTP server (Uvicorn) on `127.0.0.1:8787` (`EngineService.kt:120-124`) inside a foreground service, with cleartext traffic explicitly enabled for loopback in `network_security_config.xml:9-12`. While legitimate for Chaquopy, background proxies and local daemons are frequent vectors for ad-fraud or proxy botnets.
7. **Self-Signed Sideloaded Build with Low Certificate Reputation**:  
   The APK is self-signed via a repository-local keystore (`build.gradle:31-49`), not backed by Google Play Signing or an established enterprise certificate reputation. Sideloading an update that combines sensitive permissions (`REQUEST_INSTALL_PACKAGES`, `WAKE_LOCK`, `FOREGROUND_SERVICE_DATA_SYNC`) without developer reputation triggers client-side and cloud-assisted warning prompts.

### Alleged vs. Actually Present Behaviours

| Heuristic Allegation | Present in Code? | Malicious or Intended? | Operational Reality |
|---|---|---|---|
| **Malicious Dropper / Trojan** | **No** (False Positive) | Intended Design | Legitimate self-updater (v0.41.0 "the courier"). Downloads official GitHub releases, verifies SHA256 against release manifest, validates filename against traversal, and requests user confirmation via Android's package installer. |
| **Dynamic Code Loading (DCL)** | **Yes** (True Positive) | Intended Design | True DCL: Downloads pure-Python wheels from PyPI, unpacks to `filesDir/ytdlp`, and dynamically imports via `sys.path.insert(0, ...)`. While intended for extractor compatibility, it fulfills the strict technical definition of DCL. |
| **Native Binary Dropping** | **Yes** (True Positive) | Intended Design (Desktop leak) | `tools.py` contains active download and `chmod +x` routines for standalone `ffmpeg` ELFs. On Android, this code is dead/broken (glibc vs bionic, W^X violations), but its inclusion in the APK trips static heuristic analyzers. |
| **Binary Disguise & Evasion** | **Yes** (True Positive) | Workaround Design | Standalone static CLIs are packaged as `.so` files to force extraction into `nativeLibraryDir` for `exec()` capability on Android 10+. This mimics malware evasion techniques. |
| **Adware / Traffic Interception** | **No** (False Positive) | Intended Design | `obfuscated.py` uses XOR decryption and a local HTTP proxy to decode HLS streams disguised as `.png`/`.webp` images by streaming providers. It does not hijack system traffic. |
| **Privilege Escalation via WebView** | **No** (False Positive) | Intended Design | Bridge calls are validated; `MainActivity` requires token match before loading, and `BrowserActivity` scopes `SniffBridge` to stream detection. |

---

## 2. Findings Table

The findings below are split between **REAL Vulnerabilities** (logic flaws, security bugs, or improper access controls) and **Expected Design Disliked by Play Protect** (intentional features that match PHA detection heuristics).

| ID | Category | Severity | File:Line | Description | Concrete Fix |
|---|---|---|---|---|---|
| **V-01** | Real Vulnerability | **High** | `android/app/src/main/java/com/suravidl/app/NavGuard.kt:54-64` | `siteKey()` splits on dot and takes last 2 labels (`parts.takeLast(2)`), ignoring multi-part ccTLDs (`.co.uk`, `.com.br`). Allows arbitrary off-site redirects between distinct domains sharing a ccTLD. | Use a Public Suffix List (PSL) lookup or maintain an explicit list of multi-part TLDs. |
| **V-02** | Real Vulnerability | **Medium** | `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:91, 950` | `sniffEnforced` disables token validation when `DOCUMENT_START_SCRIPT` is unsupported, allowing untrusted pages to call `SuravidlSniff.report` and spoof candidates. | Enforce session token validation unconditionally, or reject script-driven reports if document-start injection is unavailable. |
| **V-03** | Real Vulnerability | **Medium** | `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:963`, `SniffScript.kt:146-154` | `SniffScript` reads untrusted `window.__pk` from global scope and submits it to `pk()` with the valid token `__T`, allowing hostile pages to poison stream decryption keys. | Restrict `pk` extraction to verified player frames or validate key formats and provenance before binding to handoff. |
| **V-04** | Real Vulnerability | **Low** | `src/suravidl_engine/tools.py:40-50, 115-164`, `api.py:679` | `POST /tools/ffmpeg` lacks Android environment guards; executing it on Android downloads an incompatible Linux ELF and attempts `chmod +x` in writable app storage. | Guard `POST /tools/ffmpeg` in `api.py` with `if running_platform() == "android": raise HTTPException(501)`. |
| **V-05** | Real Vulnerability | **Low** | `android/app/src/main/java/com/suravidl/app/SuravidlApp.kt:29, 37` | `LogStore.mediaDir()` writes crash stack traces and diagnostic logs to shared `Android/media/${pkg}/logs`, exposing diagnostic details to other apps. | Confine all diagnostic and exception logs strictly to `ctx.getExternalFilesDir(null)` or `ctx.filesDir`. |
| **V-06** | Real Vulnerability | **Low** | `android/app/src/main/java/com/suravidl/app/MainActivity.kt:541-585` | `handOffFile()` passes arbitrary file paths to `FileProvider.getUriForFile()` without validating that the target resides within the designated downloads directory. | Enforce canonical path checking to ensure `File(path)` is inside `context.getExternalFilesDir(Environment.DIRECTORY_MOVIES)` or `filesDir/suravidl`. |
| **D-01** | Heuristic Trigger | **High** | `android/app/src/main/AndroidManifest.xml:7`, `src/suravidl_engine/updater.py:389-438` | `REQUEST_INSTALL_PACKAGES` permission combined with background APK downloading triggers Play Protect Dropper / Downloader heuristic. | Drop in-app APK installation; direct user to GitHub release page or delegate updates to Obtainium / F-Droid. |
| **D-02** | Heuristic Trigger | **High** | `src/suravidl_engine/ytdlp_update.py:171-175, 412-474` | Dynamic Code Loading (DCL): Downloads `.whl` from PyPI and injects writable storage path into `sys.path`. Directly violates Android anti-DCL rules. | Disable dynamic wheel updating on Android; ship yt-dlp updates exclusively through complete APK updates. |
| **D-03** | Heuristic Trigger | **Medium** | `android/app/src/main/java/com/suravidl/app/SuravidlApp.kt:147-183`, `android/app/build.gradle:64` | Native executable disguise: Bundling static ELF executables as `libffmpeg.so` / `libffprobe.so` and executing them via `useLegacyPackaging` and `chmod`. | Replace CLI subprocess execution with standard JNI shared libraries (e.g. FFmpegKit / Mobile-FFmpeg). |
| **D-04** | Heuristic Trigger | **Medium** | `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:156`, `MainActivity.kt:90` | Exporting `@JavascriptInterface` bridges (`HostBridge`, `SniffBridge`) to WebView components. | Replace `@JavascriptInterface` on the in-app browser with `WebViewCompat.addWebMessageListener` and isolated origins. |
| **D-05** | Heuristic Trigger | **Medium** | `android/app/src/main/java/com/suravidl/app/EngineService.kt:120, 166` | Persistent loopback HTTP daemon on port 8787 paired with a 6-hour partial wake lock. | Replace 6-hour static wake lock with dynamic lock held only during active network transfers; consider UNIX domain sockets. |
| **D-06** | Heuristic Trigger | **Low** | `src/suravidl_engine/obfuscated.py:69-98, 171-226` | XOR-decryption routines, image segment disguise handling, and local HTTP proxying trigger static deobfuscation heuristic signatures. | Refactor XOR decoding into an explicit HLS stream parser filter without local HTTP proxy rebinding. |
| **D-07** | Heuristic Trigger | **Low** | `android/app/build.gradle:31-49` | Self-signed release certificate without developer reputation on sideloaded updates. | Establish signing key longevity, publish APK hashes on a domain with verified web reputation, or distribute via trusted alternative stores. |

---

## 3. Deep Dive: REAL Vulnerabilities

### Finding V-01: Multi-Part ccTLD Bypass in `NavGuard.sameSite()` Allows Arbitrary Off-Site Top-Level Redirects
- **Severity**: High (CVSS 7.4: `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:N/I:H/A:N`)
- **File & Line**: `android/app/src/main/java/com/suravidl/app/NavGuard.kt:54-64`
- **What is wrong**:  
  `NavGuard` enforces the in-app browser's bounce policy to prevent malicious streaming sites from redirecting users to pop-up or phishing farms. Lines 54-59 extract the registrable domain:
  ```kotlin
  fun siteKey(url: String?): String {
      val h = host(url) ?: return ""
      val parts = h.split('.').filter { it.isNotEmpty() }
      if (parts.size <= 2) return parts.joinToString(".")
      return parts.takeLast(2).joinToString(".")
  }
  ```
  Line 61 then evaluates whether two URLs are on the same site:
  ```kotlin
  fun sameSite(a: String?, b: String?): Boolean {
      val ka = siteKey(a)
      return ka.isNotEmpty() && ka == siteKey(b)
  }
  ```
- **Why it matters**:  
  By taking only the last 2 dotted labels, any domain under a two-part public suffix (e.g. `co.uk`, `com.au`, `co.jp`, `github.io`, `pages.dev`) computes `siteKey` as the public suffix itself (e.g. `co.uk`). If a user opens a video on `legitimate-site.co.uk`, an ad script or malicious hop redirecting to `attacker-controlled.co.uk` evaluates `siteKey("https://attacker-controlled.co.uk") == "co.uk"`. `NavGuard.blockReason` returns `null` (hop allowed), and the browser replaces the page without user consent or note display.
- **Concrete Fix**:  
  Implement a lightweight public suffix matcher or check against common multi-part suffixes:
  ```kotlin
  private val MULTI_PART_SUFFIXES = setOf("co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "net.au", "co.jp", "com.br")

  fun siteKey(url: String?): String {
      val h = host(url) ?: return ""
      val parts = h.split('.').filter { it.isNotEmpty() }
      if (parts.size <= 2) return parts.joinToString(".")
      val lastTwo = parts.takeLast(2).joinToString(".")
      if (lastTwo in MULTI_PART_SUFFIXES && parts.size >= 3) {
          return parts.takeLast(3).joinToString(".")
      }
      return lastTwo
  }
  ```

---

### Finding V-02: `BrowserActivity` Disables SniffBridge Token Enforcement on Older WebViews
- **Severity**: Medium (CVSS 5.3: `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`)
- **File & Line**: `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:91, 950`
- **What is wrong**:  
  `BrowserActivity` attempts to prevent hostile web pages from calling `window.SuravidlSniff.report(...)` by requiring a per-session UUID token:
  ```kotlin
  private val sniffEnforced =
      WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)
  ...
  @android.webkit.JavascriptInterface
  fun report(url: String?, via: String?, frame: String?, token: String?) {
      if (sniffEnforced && token != sniffToken) return
      SniffLog.add(url ?: return, via ?: "hook", frame ?: "", false)
  }
  ```
- **Why it matters**:  
  If the device's System WebView does not support `DOCUMENT_START_SCRIPT` (or fails initialization), `sniffEnforced` is `false`. When `sniffEnforced == false`, `token != sniffToken` is skipped entirely. Any webpage loaded in the in-app browser can invoke `window.SuravidlSniff.report("https://malicious.payload/stream.m3u8", "player", location.href, null)`, flooding `SniffLog` with attacker-controlled URLs that are automatically probed via `classifyOne()` (`BrowserActivity.kt:778-794`).
- **Concrete Fix**:  
  Never disable token validation globally. If `DOCUMENT_START_SCRIPT` is unavailable, rely on `shouldInterceptRequest` network capture exclusively, or use `evaluateJavascript` to inject an encrypted handshake rather than accepting unauthenticated calls.

---

### Finding V-03: Global `window.__pk` Read Allows Hostile Pages to Inject Arbitrary Decryption Keys
- **Severity**: Medium (CVSS 4.3: `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:L/A:N`)
- **File & Line**: `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:963-968`, `SniffScript.kt:146-154`
- **What is wrong**:  
  In `SniffScript.kt`, the injected script periodically polls `window.__pk`:
  ```javascript
  function pk() {
    try {
      var v = window.__pk;
      if (typeof v === 'string' && v.length >= 16 && v.length <= 512 && v !== window.__svPkSent) {
        window.__svPkSent = v;
        try { if (B.pk) B.pk(v, location.href, __T); } catch (e) {}
      }
    } catch (e) {}
  }
  ```
  `SniffScript` reads this untrusted global string and forwards it to `B.pk(v, location.href, __T)` using the privileged session token `__T`.
- **Why it matters**:  
  Any page visited in `BrowserActivity` can execute `window.__pk = "A".repeat(32)`. The injected script reads it and forwards it with the valid session token. This sets `BrowserActivity.sniffPk = v` (`BrowserActivity.kt:967`), which rides directly on the next handoff (`BrowserActivity.kt:809`), corrupting legitimate download parameters or directing the engine to invoke XOR decryption routines on unrelated streams.
- **Concrete Fix**:  
  Do not scrape arbitrary global variables. Restrict key extraction to specific verified origins, or extract keys directly from the WebAssembly export table within the isolated frame scope rather than trusting `window.__pk`.

---

### Finding V-04: Unrestricted Engine Endpoint Exposes Invalid Linux ELF Binary Download on Android
- **Severity**: Low (CVSS 3.3: `CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:L/A:N`)
- **File & Line**: `src/suravidl_engine/tools.py:40-50, 115-164`, `src/suravidl_engine/api.py:679-685`
- **What is wrong**:  
  `api.py` exposes `POST /tools/ffmpeg`, calling `tools.start_download()`. `tools.py` matches platform strings via `platform_key()`: on Android arm64, `sys.platform` is `"linux"` and machine is `"arm64"`, resolving to `"linux-arm64"` (`TOOLS[("linux", "arm64")]`). It proceeds to download `ffmpeg-linux-arm64.gz` from GitHub into `Path.home() / ".suravidl" / "tools" / "ffmpeg"`, runs `chmod 0700`, and sets up execution.
- **Why it matters**:  
  On Android, the bundled `libffmpeg.so` inside `nativeLibraryDir` is already provisioned by `SuravidlApp.kt:147`. Running `tools.py` on Android attempts to download a glibc-linked binary that will fail to link against Bionic libc and will trigger an immediate SELinux `W^X` violation on modern Android. Furthermore, retaining binary-downloading and executable `chmod` code inside the APK's Python source tree directly trips Play Protect's native binary dropper heuristics.
- **Concrete Fix**:  
  In `api.py:679`, disable `/tools/ffmpeg` endpoints when running under Android:
  ```python
  @app.post("/tools/ffmpeg")
  def ffmpeg_fetch(_mgr: JobManager = Depends(require_auth)):
      if os.environ.get("SURAVIDL_ANDROID") == "1":
          raise HTTPException(status_code=501, detail="ffmpeg is bundled in the Android app package")
      from . import tools
      return tools.start_download()
  ```

---

### Finding V-05: Stack Traces and Diagnostic Logs Exposed to World-Readable Shared Storage
- **Severity**: Low (CVSS 3.3: `CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`)
- **File & Line**: `android/app/src/main/java/com/suravidl/app/SuravidlApp.kt:27-38`
- **What is wrong**:  
  `LogStore.write()` writes error logs, crash details, and uncaught exceptions to `Environment.getExternalStorageDirectory() + "/Android/media/" + ctx.packageName + "/logs"`.
- **Why it matters**:  
  While `Android/data` is protected by scoped storage access restrictions on Android 11+, `Android/media` is accessible to file managers and third-party gallery/media applications without special permissions. Uncaught exception stack traces (`SuravidlApp.kt:128`) contain internal file paths, thread names, and potentially sensitive URLs or tokens from in-flight operations.
- **Concrete Fix**:  
  Confine diagnostic logging strictly to `ctx.getExternalFilesDir(null)` or internal `ctx.filesDir`. Provide an explicit in-app "Share Logs" button using `FileProvider` so logs are only exported with user consent.

---

### Finding V-06: `handOffFile()` Lacks Boundary Checks Against Configured Download Directory
- **Severity**: Low (CVSS 3.1: `CVSS:3.1/AV:L/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N`)
- **File & Line**: `android/app/src/main/java/com/suravidl/app/MainActivity.kt:541-585`
- **What is wrong**:  
  `HostBridge.openFile(path)` and `shareFile(path)` pass `path` directly to `handOffFile(path, share)`. Line 560 calls:
  ```kotlin
  val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", f)
  ```
- **Why it matters**:  
  While `FileProvider` ensures `f` falls within paths defined in `file_paths.xml`, `file_paths.xml` includes `<cache-path name="cache_updates" path="updates" />` and `<files-path name="internal_downloads" path="suravidl" />`. `handOffFile()` does not verify that `f` is restricted solely to the user's intended media downloads folder, permitting unintended URI grants to files residing in `cache/updates/`.
- **Concrete Fix**:  
  Validate that `f.canonicalPath` starts with the canonical path of the configured download directory before generating the `FileProvider` URI.

---

## 4. Deep Dive: Expected Design Disliked by Play Protect

These items represent intentional product features that are safe within the app's threat model, but directly trigger automated Play Protect PHA heuristics.

### Trigger D-01: `REQUEST_INSTALL_PACKAGES` and In-App APK Self-Updater
- **Files & Lines**: `android/app/src/main/AndroidManifest.xml:7`, `src/suravidl_engine/updater.py:389-438`, `android/app/src/main/java/com/suravidl/app/MainActivity.kt:504-533`
- **Why Play Protect dislikes it**:  
  Google Play Protect considers `REQUEST_INSTALL_PACKAGES` paired with background downloading of APK files (`updater.py:download_asset`) as a primary signature of the **Trojan-Dropper** or **Downloader** malware family. Play Protect warns users that apps requesting package installation authority may silently install malicious payloads.
- **Why it is not a vulnerability**:  
  The app is a sideloaded, open-source application not hosted on Google Play. Sideloaded apps must self-update to deliver security fixes and maintain compatibility with rapidly changing video sites. The updater downloads only from `https://github.com/LoLyeah/suravidl/releases/download/...`, verifies the binary's SHA256 against `version.json` (`updater.py:356`), validates file names with `UpdateInstallPolicy.safeName` (`UpdateInstallPolicy.kt:15`), and delegates the final installation to Android's native package installer (`MainActivity.kt:526`), requiring explicit user confirmation.
- **Mitigation to reduce signal**:  
  See Recommendation 1 in Section 5.

---

### Trigger D-02: Dynamic Code Loading (DCL) of Python Wheels via PyPI
- **Files & Lines**: `src/suravidl_engine/ytdlp_update.py:171-175, 412-474`, `src/suravidl_engine/__main__.py:203-207`
- **Why Play Protect dislikes it**:  
  Play Protect strictly forbids Dynamic Code Loading (DCL). Downloading executable bytecode or scripts from the internet into writable application storage and executing them at runtime allows an app to alter its behavior post-installation, bypassing Google's static and dynamic application vetting.
- **Why it is not a vulnerability**:  
  In packaged runtimes (Chaquopy on Android), `yt-dlp` cannot be updated via `pip`. Because streaming platforms update their player formats weekly, video downloaders break unless extractor code can be updated independently of full APK releases. `ytdlp_update.py` fetches only official `py3-none-any` wheels from `https://files.pythonhosted.org/`, verifies SHA256 against PyPI JSON, checks zip slip traversal (`ytdlp_update.py:387`), and activates the shadow copy only if verified.
- **Mitigation to reduce signal**:  
  See Recommendation 2 in Section 5.

---

### Trigger D-03: Packaging Static Native Executables as Disguised `.so` Libraries
- **Files & Lines**: `android/app/src/main/java/com/suravidl/app/SuravidlApp.kt:147-183`, `android/app/build.gradle:58-66`, `scripts/build_ffmpeg_android.sh:11-24`
- **Why Play Protect dislikes it**:  
  Since Android 10 (API 29), executing binaries from writable app storage is blocked by W^X SELinux policies. Sideloaded apps circumvent this by naming executable ELF binaries with a `lib*.so` prefix in `jniLibs` and forcing extraction via `useLegacyPackaging = true` (`extractNativeLibs = true`). Malware uses this identical technique to smuggle and execute root exploits, bots, or miners. Play Protect scanners inspect ELF headers in `lib/` and flag executables (`ET_EXEC`) masquerading as shared libraries (`ET_DYN`).
- **Why it is not a vulnerability**:  
  The bundled `libffmpeg.so` and `libffprobe.so` are legitimate media processing tools statically cross-compiled via the Android NDK (`scripts/build_ffmpeg_android.sh:72-106`). Network protocols are disabled (`--disable-everything --enable-protocol=file,pipe,data`), preventing outbound network sockets. They are executed solely to mux, transcode audio, and extract video metadata.
- **Mitigation to reduce signal**:  
  See Recommendation 4 in Section 5.

---

### Trigger D-04: Exposed `@JavascriptInterface` Bridges on WebViews
- **Files & Lines**: `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:156`, `android/app/src/main/java/com/suravidl/app/MainActivity.kt:90`
- **Why Play Protect dislikes it**:  
  Adding JavaScript interfaces via `addJavascriptInterface()` exposes Java/Kotlin objects to web scripts. When present on a WebView that navigates untrusted public internet domains (`BrowserActivity`), automated static analysis tools flag the app for potential bridge exploitation and cross-context script execution.
- **Why it is not a vulnerability**:  
  All exposed bridge methods are restricted to `@JavascriptInterface` annotations (preventing reflection attacks on Android 4.2+). `HostBridge` is mounted only in `MainActivity`, which binds strictly to `http://127.0.0.1:8787/` with token verification. `SniffBridge` in `BrowserActivity` exposes only stream capture reporting.
- **Mitigation to reduce signal**:  
  See Recommendation 3 in Section 5.

---

### Trigger D-05: Embedded Loopback HTTP Daemon and 6-Hour WakeLock
- **Files & Lines**: `android/app/src/main/java/com/suravidl/app/EngineService.kt:29, 120-124, 166`, `android/app/src/main/res/xml/network_security_config.xml:7-13`
- **Why Play Protect dislikes it**:  
  Background services that bind local TCP ports and hold partial wake locks for extended durations (up to 6 hours: `wakeLock?.acquire(6 * 60 * 60 * 1000L)`) match heuristic models for persistent botnet nodes, mining software, or proxy ware.
- **Why it is not a vulnerability**:  
  The Uvicorn daemon hosts the core application backend on loopback, protected by API tokens and page keys (`THREAT-MODEL.md:85-107`). The wake lock is required to prevent Android from sleeping the CPU during large multi-gigabyte video downloads.
- **Mitigation to reduce signal**:  
  See Recommendation 5 in Section 5.

---

## 5. Top 5 Changes to Minimize Play Protect Signals

Implementing these five architectural adjustments will systematically dismantle the primary heuristic triggers responsible for the "harmful app" flag without breaking core user functionality:

### 1. Remove `REQUEST_INSTALL_PACKAGES` and Delegate Updates to Browser / External Tools
- **Files**: `android/app/src/main/AndroidManifest.xml:7`, `android/app/src/main/java/com/suravidl/app/MainActivity.kt:463-533`, `src/suravidl_engine/updater.py:163-167`
- **Action**:  
  1. Delete `<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />` from `AndroidManifest.xml`.
  2. Remove `installApk` from `HostBridge`. When an update is detected, change the action to open the release URL in the system browser via `Intent.ACTION_VIEW` (`openUrl`), or integrate with user-managed updater apps like **Obtainium** by exporting standard release metadata.
- **Impact**: Completely eliminates Play Protect's **Dropper/Downloader** heuristic classification.

### 2. Disable Dynamic Wheel Code Loading on Android Build
- **Files**: `src/suravidl_engine/updater.py:123-134`, `src/suravidl_engine/ytdlp_update.py:177-245`, `src/suravidl_engine/api.py:635-644`
- **Action**:  
  1. In `updater.py:self_update()`, check if running on Android (`os.environ.get("SURAVIDL_ANDROID") == "1"`). If so, do not invoke `ytdlp_update.stage_update()`; return `{"ok": false, "bundled": true, "detail": "yt-dlp updates on Android are delivered via app releases"}`.
  2. Ensure `ytdlp_update.activate()` is a no-op on Android so `sys.path.insert(0, ...)` never executes from writable app directories.
- **Impact**: Completely eliminates Play Protect's **Dynamic Code Loading (DCL)** heuristic flag.

### 3. Strip Unused Desktop Tool Endpoints (`tools.py`) from Android Engine
- **Files**: `src/suravidl_engine/api.py:679-685`, `src/suravidl_engine/tools.py:1-195`
- **Action**:  
  1. Add an Android guard to `POST /tools/ffmpeg` and `POST /tools/ffmpeg/remove` returning HTTP 501.
  2. In `android/app/build.gradle:chaquopy`, exclude `suravidl_engine/tools.py` from packaging, or stub `tools.py` when building for Chaquopy.
- **Impact**: Eliminates the presence of native ELF download routines, `gzip` extraction, and `chmod +x` binary dropping signatures within the APK bundle.

### 4. Migrate BrowserActivity from `@JavascriptInterface` to `WebMessageListener`
- **Files**: `android/app/src/main/java/com/suravidl/app/BrowserActivity.kt:156, 941-969`, `android/app/src/main/java/com/suravidl/app/SniffScript.kt:45-54`
- **Action**:  
  1. Remove `webView.addJavascriptInterface(SniffBridge(), "SuravidlSniff")`.
  2. Replace with `WebViewCompat.addWebMessageListener(webView, "SuravidlSniff", setOf("*"), ...)` (`androidx.webkit:1.17.1` is already a project dependency).
  3. In `SniffScript.kt`, post message objects via `window.SuravidlSniff.postMessage(JSON.stringify({...}))`.
- **Impact**: Eliminates static detection of legacy JavaScript bridges exposed on open-web browsing contexts.

### 5. Transition Bundled CLIs to Real Shared Libraries or Pre-Compiled Native JNI
- **Files**: `scripts/build_ffmpeg_android.sh:72-125`, `android/app/build.gradle:58-66`, `android/app/src/main/java/com/suravidl/app/SuravidlApp.kt:174-183`
- **Action**:  
  1. Compile FFmpeg as actual shared libraries (`.so`, ELF type `ET_DYN`) with JNI wrapper interfaces rather than standalone executables (`ET_EXEC`).
  2. Alternatively, if CLI execution is retained, ensure the binary is compiled with `--enable-shared` and packaged cleanly without manual runtime `chmod` mutations, or set `extractNativeLibs = false` with page-aligned shared libraries compliant with Android 15's 16 KB page size standards.
- **Impact**: Eliminates Play Protect's binary disguise and executable extraction heuristics.
