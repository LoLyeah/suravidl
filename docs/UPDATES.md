# Updates

suravidl updates itself without a release-page trip on Windows, macOS and
Android; every other platform keeps a one-click path to the release.

## The feed

Each release carries a small `version.json` (plus `SHA256SUMS.txt`), written by
`scripts/generate_release_manifest.py` over the release assets:

- The app reads it through `releases/latest/download/version.json` — a CDN
  redirect, not the REST API, so the anonymous 60-requests/hour API limit
  never applies; the API remains the fallback for releases that predate the
  manifest.
- Download URLs inside the manifest are pinned to their own tag, so the sha256
  it carries always describes the bytes that URL serves.
- The APK is built by the android workflow and attached after the release is
  created; the attach step folds it into `version.json` and `SHA256SUMS.txt`
  (re-uploaded with `--clobber`), so the manifest on a release always
  describes the complete release.
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
- **macOS**: the app downloads `suravidl-macos-arm64.zip` (the very bundle the
  dmg carries), verifies it, and — on "Restart & Install" — swaps the app bundle
  in place and reopens it. Two shapes cannot self-update and get words instead:
  a copy still running from the mounted dmg (drag it to Applications first) and
  a folder the user cannot write. The app is unsigned (no Apple Developer ID),
  so first installs keep the right-click → Open dance; updates after that are
  frictionless because the app's own download carries no quarantine flag.
- **Linux**: the check reports the new version and opens the release page; the
  AppImage flow stays manual.

## Verifying by hand

    curl -L https://github.com/LoLyeah/suravidl/releases/latest/download/version.json

Compare the `sha256` fields against `SHA256SUMS.txt` on the release page.
Downloads are verified against these hashes before anything is spawned
(installer) or handed to the system installer (APK).
## Cleanup after an update (v0.42.1)

The downloaded update file never lingers once it is spent:

- **Windows**: the upgrade chain deletes the staged setup the moment the
  installer exits — before the new version comes back up.
- **macOS**: the swap script deletes the zip the moment the new bundle is
  in place.
- **Android**: the staged APK sits in the app's cache only until the next
  launch; there is no way to run a cleanup during the system install, so
  the app sweeps it (along with anything an interrupted session left) on
  every start.
- All shells: any staged file from a previous engine session is an orphan
  by definition — the staging state lives in memory — so every boot and
  every fresh download sweeps the update cache first.
