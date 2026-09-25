# suravidl — threat model (cookies & stored data)

Scope: what suravidl stores, where, and what an attacker would need to read
it. Written for the Android app, which is the platform where "at rest"
actually matters; the desktop/extension side is noted where it differs.

## What is stored

| item | where (Android) | at rest | while running |
| --- | --- | --- | --- |
| `cookies.txt` import | `filesDir/cookies.enc` | **AES-256-GCM ciphertext**; key never leaves the Android Keystore (non-exportable) | decrypted to `filesDir/cookies.session.txt` (owner-only `0600`) so yt-dlp can read it |
| job history | `~/.suravidl/jobs.db` (SQLite) | cookie values are **never** written; rows that carried a `Cookie` header store `<redacted>` | — |
| settings | `~/.suravidl/settings.json` | never contains cookie *values* (only a path, or `<redacted>`) | — |
| engine token | `~/.suravidl/token` | `0600`, directory `0700` | in memory; the Android app keeps it in its private `SharedPreferences` |
| downloads | `filesDir/…` | as downloaded | — |

The Keystore key is created on first import (`suravidl-cookies-v1`) with
`PURPOSE_ENCRYPT | PURPOSE_DECRYPT`, GCM, no user-authentication requirement.
It is destroyed by "clear data"/uninstall and unusable after a factory reset —
the ciphertext is worthless elsewhere.

## What this protects against

- **Backup / sync leaks.** `filesDir` is not backed up to Google by default
  for this app, but cloud sync tools, `adb backup` on older devices, or a
  copied app folder now yield only ciphertext.
- **Another app reading our storage on a shared-storage mount** (SD-card
  installs, "move to SD" setups): ciphertext again.
- **Casual inspection** of the phone's filesystem with a file manager: the
  cookie value is not greppable anywhere in the app directory.

## What it does NOT protect against

- A **rooted device or a live memory dump** while the app runs: the session
  file exists in the clear during a run (unavoidable — yt-dlp needs a
  Netscape cookie file), and the Keystore key can be used by anyone who can
  run code as this app.
- **Screen recording / clipboard** after the user copies a path or shares a
  file — outside our control.
- Anything the **remote site** does with the cookies (that is the point of
  having them).
- **DRM/Widevine** content: out of scope entirely; suravidl refuses it.

## Lifecycle rules (why a readable copy exists at all)

1. On import the SAF-picked file is read once, encrypted, and the plaintext
   copy is discarded — the picked file itself stays wherever the user chose
   it (we cannot delete another app's file).
2. On engine start the vault is unlocked **only** into
   `cookies.session.txt`, owner-readable only; a stale session file from a
   crash is deleted first.
3. On "Quit completely", on "Delete stored cookies", and on every app start
   the session file is removed.
4. A `cookies.txt` left by an older version is encrypted at first start
   (`migrateLegacy`) and the plaintext file deleted.
5. The engine records only `<redacted>` in its database and API payloads, and
   scrubs pre-existing rows at startup (`VACUUM`).

## Reporting

Security issues: open an issue at github.com/LoLyeah/suravidl or contact the
maintainer. Please do not include real cookies or tokens in reports.
