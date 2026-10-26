# Security, and why Play Protect calls this app "harmful"

Play Protect scanned an update of the Android app and showed **"this app may be
harmful"**. That is a warning about a *pattern*, not a finding of malware — and
this page says exactly which pattern, what was checked, what changed, and how to
verify a download yourself.

## What Play Protect is reacting to

Play Protect flags behaviour, not intent. This app legitimately contains several
things that, together, look like a dropper:

- it is **sideloaded and self-signed** (no Play distribution, no developer
  reputation attached to the certificate);
- it asks for **`REQUEST_INSTALL_PACKAGES`** because it can install its own
  updates;
- it **downloads code at runtime**: a `yt-dlp` wheel from PyPI, and (on desktop)
  a static ffmpeg binary;
- the APK ships **native executables named `lib*.so`** so Android will extract
  them somewhere they can be run — the standard workaround for "no `exec()` from
  app storage" since Android 10, and also the standard malware trick;
- it runs a **loopback HTTP daemon** and exposes **JavaScript bridges** to a
  WebView.

Every one of those is deliberate, documented below, and needed for the product.
None of them is hidden.

## The audit (October 2026)

An independent audit of the Android app and the parts of the engine the APK
ships was run against the tagged tree (Gemini via Antigravity, read-only clone),
and **every finding was re-checked by hand** before anything was changed. Six
were real; seven were "design that Play Protect dislikes".

Fixed in **0.47.14 "the seal"**:

| Finding | What was wrong | Fix |
|---|---|---|
| Update APK had no identity check | The sha256 pin comes from the same channel as the file; a hijacked release feed could hand over a different app | The installer now reads the APK's signing certificate and **refuses anything not signed by this app's key** (`ApkTrust.kt`), plus package-name match |
| Same-site check collapsed two-part suffixes | `video.co.uk` and `ads.co.uk` both became `co.uk`, so an ad hop between them counted as staying on the site | `NavGuard` now knows the multi-part suffixes and hosting domains that matter (`co.uk`, `com.au`, `github.io`, …) |
| ffmpeg download reachable on Android | Android reports `linux`, so the fetch would have downloaded a glibc build that can never run under bionic, and left it behind | Android gets its own platform key; `POST /tools/ffmpeg` answers **501** there; the Settings row is hidden on the phone |
| Hand-off took any path | `FileProvider`'s scope also covers `cache/updates` (the downloaded APK) | `PathGuard` checks the canonical path: only the download folders may leave the app |

**0.47.15 "the spare"** went one step further: the APK no longer carries the
ffmpeg *fetcher* at all. The phone's ffmpeg already ships inside the app, so
`tools.py` was desktop-only; the Android build stages the engine without it and
the release job asserts its absence in the built APK (0.47.16 fixed that
guard's first version, which searched for an API route every build carries and
so stopped the phone's own 0.47.15 APK from being published). Be clear about what this
does and does not buy: Play Protect's scanner reads the manifest, `classes.dex`
and the ELF headers — not Python assets — so this is removing dead code, not
silencing the warning. The warning's causes are the four items listed below.

Checked and left as designed (with the reason):

- **`window.__pk` scraping** — the key comes from the page's own player. A page
  that plants a fake key only breaks its own download; it cannot reach another
  job, another site, or any file.
- **Sniff token enforcement** — where the WebView cannot inject a token into
  every frame, the bridge accepts token-less reports (documented in
  `docs/THREAT-MODEL.md`). A hostile page gains "the engine probes a URL it
  chose", which the page could already make the device fetch itself.
- **Logs in `Android/media/<pkg>/logs`** — deliberately world-readable so a file
  manager can reach them without adb; URLs and tokens are kept in the
  app-private copy or reduced to a host name (`v0.21.1` audit).

Still by design, and still flagged by Play Protect:

- the **in-app updater** (`REQUEST_INSTALL_PACKAGES`) — Android itself shows the
  install prompt; the app cannot install anything silently;
- **yt-dlp wheel updates** on Android (dynamic code loading) — without them,
  extractors go stale between app releases;
- the **bundled ffmpeg as `libffmpeg.so`** — it is a static CLI, not a library,
  and has to live somewhere executable.

If the warning matters more than one-tap updates, the updater can be dropped in
a later release (updates would then be "download from the release page, open the
file"). That is a product decision, not a bug fix.

## Dependencies that carry a C decoder

`Brotli`/`brotlicffi` are not dependencies of this app and are not in either
build (the frozen bundle's own import report lists them as missing optional
imports of yt-dlp; the APK's Chaquopy archive contains no brotli entries). The
engine asks for gzip/deflate only and never decodes a Brotli stream itself.

One path does carry a Brotli decoder: **curl_cffi**, which is bundled for the
impersonation feature and statically links both libcurl and Brotli. The
decoder before Brotli 1.2.1 carries **CVE-2026-111497** ("Node2Shell", an
out-of-bounds write when decoding a crafted stream). Since the version inside
a wheel cannot be read from the outside, the build and the developer setup
require `curl_cffi>=0.17.0` — the first line released after the fix — and
impersonation stays opt-in. The Android build has no curl_cffi at all.

## Verify your own download

1. Compare the file with `SHA256SUMS.txt` from the same release:

   macOS / Linux:
   ```
   shasum -a 256 app-release.apk
   ```
   Windows (PowerShell):
   ```
   Get-FileHash .\app-release.apk -Algorithm SHA256
   ```

2. Check that the APK is signed by this project's key. The certificate of the
   current release key is:

   ```
   subject : C=NL, O=LoLyeah, OU=suravidl, CN=suravidl
   valid   : Sep 24 2026 – Feb 9 2054
   SHA-256 : 4A:03:C1:E5:52:61:12:03:EB:38:54:B1:9F:03:D4:1C:26:2E:5E:43:48:28:E0:04:39:97:9A:3A:DB:47:AF:DF
   ```

   With Android build-tools installed:
   ```
   apksigner verify --print-certs app-release.apk
   ```

3. If you believe the classification is wrong and want it re-reviewed, the
   appeal path and the text to submit are in
   [PLAY-PROTECT-APPEAL.md](PLAY-PROTECT-APPEAL.md).

4. Install. If Play Protect still warns, use **More details → Install anyway**
   *after* steps 1 and 2 match. The warning will stay until the app is
   distributed through Play — that is Play Protect's rule for sideloaded apps
   that can install and download code, not something an update can switch off.

## Reporting a problem

Open an issue at <https://github.com/LoLyeah/suravidl/issues> with the version,
the platform, and what happened. Please do not attach logs containing private or
tokenised URLs.
