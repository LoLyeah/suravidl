# Antigravity UI + Android review — 2026-09-26

Scope asked for: the UI and the Android section, plus "the android minimum
allowed to install the app". A worker (`agy`) read the repo read-only and
produced 12 findings; every one was then reproduced here against the real code
before anything was changed. Two claims did not survive that, and they are
recorded as such.

Verdict legend: **confirmed** = reproduced, fixed · **hardened** = not
reproducible as a bug, but the fix is cheap and honest · **rejected** = wrong.

| # | Finding | Verdict | What was actually true |
|---|---------|---------|------------------------|
| 1 | `NotificationChannel` created unguarded in `EngineService` | **confirmed — fatal** | The class is API 26+ and resolves when the line runs, so on Android 7.0/7.1 (declared floor, `minSdk 24`) the service died with `NoClassDefFoundError` before Python started: the app installed and did nothing. Guarded with `SDK_INT >= 26`. |
| 2 | Gallery-import retry spins a full re-copy every 2 s forever | **confirmed** | `existing` counts *files*, not copies, and on API<29 `importToGallery` returns null by design — so `imported \|\| existing == 0` was never true and every finished job re-ran each tick, writing a log line each time. Now: no copy possible → remember immediately; a real failure gets 5 tries, one log line, then a `import-gave-up` entry. |
| 3 | `ACTION_SEND` share can throw `SecurityException` (no `clipData`) | **hardened** | The platform's `Intent.migrateExtraStreamToClipData()` copies `EXTRA_STREAM` into `clipData` on the way out, so the grant normally survives — the failure is not reproducible by reasoning and no device here can prove it either way. `clipData = ClipData.newRawUri(...)` is now set explicitly anyway, with a test pinning it. |
| 4 | In-app seeking broken where starlette is old (`FileResponse` + `Range`) | **confirmed by reproduction** | Android pins `fastapi==0.99.1` → starlette 0.27, whose `FileResponse` ignores `Range`: a scratch venv with 0.27.0 answered `206`-worthy requests with **200 + the whole body and no `Content-Range`**. The v0.22.0 test passed only because the desktop venv has starlette 1.7. Range is now implemented in `api.py` (206/416/`Accept-Ranges`, suffix + open-ended forms) and four tests pin it, including one that fails if the file is ever handed back to `FileResponse`. |
| 5 | A pending shared link is lost on rotation/process death | **confirmed** | It lived only in a field. Now saved in `onSaveInstanceState` and restored before `pendingSharedUrl` is consumed (a fresh intent still wins). |
| 6 | The "whole video" clip button is inert | **confirmed** | `ovClipClear` shipped with no listener. Wired: clears both times and updates the count chip. |
| 7 | Failed rows show two Retry buttons | **confirmed** | The error line carries one and the actions row added another. The actions row now offers only "Edit & retry"; `cancelled` rows (no error line) keep their Retry. |
| 8 | The "cannot reach the engine" banner never leaves | **confirmed** | It was only removed on the non-empty path, so after one outage it stayed over an empty queue forever. Cleared on every successful poll. |
| 9 | Batch: bare links dropped, cap invisible | **confirmed** | The UI regex demanded a scheme while the engine accepts a bare host, so a paste of bare links produced no batch. Bare hosts now count, and >20 shows "only 20 fit in one batch" with the button disabled. |
| 10 | Toasts sit on top of the mobile tab bar | **confirmed** | `#toasts` was 22px from the bottom, over the fixed bar — taps meant for a tab hit the toast. On ≤899px it now sits above the bar and spans the width. |
| 11 | "No log recorded" while a log is on disk | **confirmed** | `write` falls back to the app-private dir; `readAll` only read the media dir. It now reads both, newest first. |
| 12 | A11y: unnamed inputs, unannounced modals, 28px touch targets | **confirmed** | `aria-label` on the five unlabelled inputs, `role="dialog" aria-modal="true"` on both modals, and `.btn`/`.ghost-sm` get 44px minimum on coarse pointers. |

## Extra: the install floor

- `minSdk 24` (Android 7.0) is exactly **Chaquopy's own floor** for Python 3.11
  (chaquo.com: "minSdk must be at least 24"), so it is not an arbitrary choice.
- The APK ships `arm64-v8a` + `x86_64` only: **64-bit devices**. An
  `armeabi-v7a` build would nearly double the APK for hardware that stopped
  shipping years ago.
- The review suggested raising the floor to 29 to dodge findings 1–2. That was
  **rejected** — with both fixed, Android 7.0 genuinely works; only the
  Gallery/Music copy and the plain-file-manager log need Android 10+ (no
  scoped storage below it), which the README now states.
- One more floor hazard the review hinted at: the UI is modern JS and Android 7
  shipped a 2016 WebView. The app now reads the WebView's engine version and,
  below Chrome 80, shows "update Android System WebView" instead of a blank
  page.
- No API-24 emulator job was added: the system image's WebView is from 2016 and
  cannot run the UI at all, so it would fail for a reason that is not ours.
  CI covers 30 and 36; the floor is guarded in code and pinned by tests.

## Not changed (and why)

- **Queue reordering** — not in this review's scope (deferred since v0.22.0:
  it would replace the one-thread-per-job model).
- The `ShareTarget` "second share while the UI is up" path still has no test of
  its own; finding 5 made that path cheaper to get right, not tested.
