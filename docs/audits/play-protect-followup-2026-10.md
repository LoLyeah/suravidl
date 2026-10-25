# Play Protect Audit Follow-Up: On-Demand FFmpeg Fetcher & Desktop Assets

## 1. Is `tools.py` a Plausible Contributor to the "Harmful App" Verdict?

**Plain answer: No.** The on-demand ffmpeg fetcher (`src/suravidl_engine/tools.py`), its API routes (`src/suravidl_engine/api.py:672-698`), and the Settings row (`src/suravidl_engine/web/index.html:542-550`, `src/suravidl_engine/web/app.js:3087-3143`) are **not** plausible contributors to the Play Protect warning.

### What the Scanner Actually Sees
* **Unexecuted asset file:** The scan runs at installation time before the app or engine runs. In Chaquopy, Python code is packaged as an asset archive or extracted directory (`assets/chaquopy/`, configured via `android/app/build.gradle:52-56` and `extractPackages("suravidl_engine")` at line 74). Play Protect's Android scanner evaluates Dalvik/ART DEX bytecode (`classes.dex`), `AndroidManifest.xml`, and native ELF headers in `lib/`. It does not execute Python, trace FastAPI endpoint decorators (`@app.post("/tools/ffmpeg")`), or evaluate frontend DOM event handlers in `app.js`.
* **Clean URLs and checksums:** While static scanners inspect strings in archive entries for known malware C2 URLs or blacklisted hashes, `tools.py:26-50` downloads official builds from `github.com/eugeneware/ffmpeg-static` and checks public SHA-256 digests. Neither the domain nor the binary hashes match any known malware signature.
* **Proof from v0.47.14:** In v0.47.14, the engine added `tools.on_android()` returning HTTP 501 (`api.py:684-689`) and hid the UI field on Android (`app.js:3090`). However, `tools.py` is still packaged byte-for-byte in the APK. If `tools.py` had triggered a static signature, runtime 501 guards would have had zero effect on the binary bytes scanned.
* **The real trigger:** The prompt **"Harmful app blocked / This app may be harmful"** is Google Play Protect's cloud heuristic for sideloaded APKs lacking developer reputation (`build.gradle:31-49`), requesting `REQUEST_INSTALL_PACKAGES` (`AndroidManifest.xml:7`), bundling disguised static `ET_EXEC` ELF binaries in `jniLibs` (`libffmpeg.so`, `libffprobe.so` extracted via `build.gradle:64` and `chmod`'d in `SuravidlApp.kt:174-183`), and performing Dynamic Code Loading (DCL) of PyPI wheels (`ytdlp_update.py:171-175, 412-474`). The timing with v0.47.13 was a temporal correlation, not causation.

---

## 2. Cleanest Mechanism to Keep `tools.py` Out of the APK with Chaquopy 3.11

### Chaquopy Capability Verification
**Chaquopy 3.11 (plugin version 17.0.0) has NO `exclude` option.**
* The Chaquopy Gradle DSL (`android/app/build.gradle:69-84`) provides no file-filtering or exclusion directive.
* `extractPackages("suravidl_engine")` (`build.gradle:74`) only controls which packaged modules are extracted from zip assets to disk at runtime; it does not exclude files from the build.
* `sourceSets { main { python.srcDir '../../src' } }` (`build.gradle:52-56`) blindly includes all files in the specified directory.

### Cleanest Mechanism: Gradle `Sync` Staging Task
Because Chaquopy lacks an exclude DSL, the cleanest mechanism is a standard Gradle `Sync` task in `android/app/build.gradle` that stages a filtered copy of `../../src` into the build directory, excluding `tools.py`, and points Chaquopy's `python.srcDir` to that staged directory.

### Exact Changes Required

1. **`android/app/build.gradle`** (lines 52–56):
   Replace the direct `python.srcDir '../../src'` with a staging task:
   ```groovy
   def stagePython = tasks.register('stagePython', Sync) {
       from '../../src'
       into layout.buildDirectory.dir('staged-python')
       exclude 'suravidl_engine/tools.py'
   }

   android {
       sourceSets {
           main {
               python.srcDir stagePython.map { it.destinationDir }
           }
       }
   }
   ```

2. **`src/suravidl_engine/api.py`** (lines 672–698):
   Guard `from . import tools` with `try ... except ImportError` to return a 501 or static status dict rather than throwing an unhandled `500 Internal Server Error` if the endpoint is called on Android:
   ```python
   @app.get("/tools/ffmpeg")
   def ffmpeg_status(_mgr: JobManager = Depends(require_auth)):
       try:
           from . import tools
           return tools.status()
       except ImportError:
           return {"platform": "android", "supported": True, "installed": True,
                   "note": "ffmpeg ships inside the Android app", "download": {}}
   ```
   *(Note: `src/suravidl_engine/cut.py:46-52` already catches `Exception` when importing `tools`, so it requires no changes).*

---

## 3. Desktop-Only Assets Shipped in the APK & Impact on Verdict

### Audit of Desktop-Only Code in the APK
`android/app/build.gradle:54` bundles the entire `src/suravidl_engine` directory into the APK. The following desktop-specific components end up in the APK:

1. **`pystray`:**
   * Referenced in `src/suravidl_engine/__main__.py:852` (`_make_tray_icon`) and `line 1269` (`_make_dock_menu`).
   * **Runtime behavior:** Both are function-local deferred imports inside methods only called by `main()`. On Android, `EngineService.kt:121-123` imports `suravidl_engine.__main__` and calls `start_server()`, never `main()`. `pystray` is never imported at runtime on Android.
2. **`pywebview`:**
   * Referenced in `src/suravidl_engine/__main__.py:298` (`_load_webview`) and lines 305–715 (`_try_window`, `_find_webview_view`, window listeners).
   * **Runtime behavior:** Deferred inside helper functions invoked exclusively by `main()`. Never executed on Android.
3. **`tkinter`:**
   * **Not present:** There are zero occurrences or imports of `tkinter` in `src/suravidl_engine` or anywhere in the repo.
4. **Desktop Updater Applier & Scripts:**
   * `src/suravidl_engine/__main__.py:1432-1520` (`_make_apply_update_action`): Spawns Windows silent updates via PowerShell (`_CREATE_NO_WINDOW`, line 1465) or macOS bundle-swap scripts (`subprocess.Popen`, line 1496). Only passed into `start_server` via `desktop_actions` from `main()`. On Android, `EngineService.kt:123` passes `null` for `desktop_actions`, causing `api.py:713-716` to safely return `{"ok": False, "reason": "this build has no installer applier"}`.
   * `src/suravidl_engine/updater.py:442-536`: Contains `macos_apply_command`, `_windows_apply_command`, `app_bundle_from`, and `macos_apply_refusal`.
   * `src/suravidl_engine/macos_swap.sh`: A 192-line macOS bash script in `src/suravidl_engine/macos_swap.sh:1-192` packaged into the APK.

### Would Removing Them Change the Verdict?
**No.**
* Google Play Protect does not scan for unused desktop GUI libraries (`pystray`, `pywebview`) or extraneous shell scripts (`macos_swap.sh`) within Python assets.
* Play Protect evaluates Android-specific high-risk indicators:
  1. `REQUEST_INSTALL_PACKAGES` permission in `AndroidManifest.xml:7` + in-app APK installation in `MainActivity.kt:504-533`.
  2. Executable ELF binaries packaged as shared libraries (`libffmpeg.so`, `libffprobe.so` being `ET_EXEC`) in `jniLibs` (`build.gradle:64`, `SuravidlApp.kt:174-183`).
  3. Dynamic Code Loading (DCL) of `.whl` files from PyPI into writable app storage (`ytdlp_update.py:171-175, 412-474`).
  4. Sideloaded APK signed with an untrusted, self-signed developer certificate (`build.gradle:31-49`).
* Removing desktop Python imports or scripts leaves every single one of those four Android PHA triggers active. As documented in `docs/SECURITY.md:98-100`, the Play Protect warning remains until the app is distributed via Google Play or the high-risk Android dropper/DCL behaviors are redesigned.
