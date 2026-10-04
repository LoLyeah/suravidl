# Updates

suravidl updates itself without a release-page trip on Windows and Android;
every other platform keeps a one-click path to the release.

## The feed

Each release carries a small `version.json` (plus `SHA256SUMS.txt`), written by
`scripts/generate_release_manifest.py` over the release assets:

- The app reads it through `releases/latest/download/version.json` — a CDN
  redirect, not the REST API, so the anonymous 60-requests/hour API limit
  never applies; the API remains the fallback for releases that predate the
  manifest.
- Download URLs inside the manifest are pinned to their own tag, so the sha256
  it carries always describes the bytes that URL serves.
- Privacy: one plain HTTPS GET. No query parameters, no cookies, no
  identifiers, no telemetry. A failed check is reported once, never retried in
  a loop.

## What happens on each platform

- **Windows**: the app downloads `suravidl-windows-x64-setup.exe` into its
  cache, verifies the checksum, and — on the user's "Restart & Install" —
  spawns the installer silently (`/SILENT /SP- /NORESTART /CLOSEAPPLICATIONS`)
  and exits so the files can be replaced; the installer finishes and the app
  comes back up. Nothing installs before that tap.
- **Android**: the app downloads `app-release.apk`, verifies it, and hands it
  to the system package installer through a FileProvider. Android shows its own
  single "do you want to update this app?" confirmation — a fully silent
  install is impossible for apps installed outside an MDM/root context, and
  that is by Android's design. The signing keystore is unchanged, so updates
  land in place and app data survives.
- **macOS / Linux**: the check reports the new version and opens the release
  page; the dmg / AppImage flows stay manual.

## Verifying by hand

    curl -L https://github.com/LoLyeah/suravidl/releases/latest/download/version.json

Compare the `sha256` fields against `SHA256SUMS.txt` on the release page.
Downloads are verified against these hashes before anything is spawned
(installer) or handed to the system installer (APK).
