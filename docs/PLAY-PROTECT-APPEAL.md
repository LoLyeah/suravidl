# Play Protect: what the block is, and how to appeal it

This page exists because Play Protect shows **"Harmful app blocked — installing
this app may put your device at risk"** when installing a sideloaded suravidl
update. It is written against Google's own developer guidance:
<https://developers.google.com/android/play-protect/warning-dev-guidance>

## What Google says this prompt means

The guidance's "Harmful App Blocked" section says, verbatim:

> The application has been identified as a Potentially Harmful Application and
> fits into a malware category or mobile unwanted software category.

and adds: *"Details vary by violation depending on the type of malware or mobile
unwanted software detected."* Google does not publish the rule weights, so no
one outside Google can tell you which specific signal crossed the line. What we
*can* do is check every recommendation on that page against this app — which is
what the checklist below is.

Two things it is **not**:

- It is **not** the "App blocked to protect your device" prompt. That one is
  automatic and only fires for internet-sideloaded apps declaring
  `RECEIVE_SMS`, `READ_SMS`, `NOTIFICATION_LISTENER` or `ACCESSIBILITY`.
  suravidl declares none of them.
- It is **not** the "built for an older Android" warning. That fires only when
  `targetSdkVersion` is more than two releases behind the device; suravidl
  targets API 35 (one behind Android 16), and `compileSdk`/`targetSdk` are
  bumped every cycle.

## The page's recommendations, checked

| Google's recommendation | suravidl |
|---|---|
| Follow developer guidelines / best practices | Foreground service with the `dataSync` type, scoped storage, `FileProvider` only, cleartext off except loopback (`network_security_config.xml`), backups exclude the token/db (`data_extraction_rules.xml`) |
| APIs and permissions used as intended | 6 permissions, each mapped in [SECURITY.md](SECURITY.md): INTERNET, FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC, POST_NOTIFICATIONS, WAKE_LOCK, REQUEST_INSTALL_PACKAGES |
| Minimum permissions | no storage permissions at all (scoped dirs only), no contacts/camera/mic/location/SMS/accessibility |
| Responsible privacy and security | no ads, no analytics, no telemetry, no cloud; cookies in a Keystore-encrypted vault; loopback API token-gated |
| Free of malicious code and risky SDKs | GPLv3 source, built by public CI; dependencies are AndroidX, Chaquopy, and four pure-Python packages (yt-dlp, fastapi, pydantic, uvicorn). The raw audit is in `audits/play-protect-2026-10.md` |
| **Valid standard APK/ZIP headers** | verified, see below |
| Target the latest API level | `targetSdk 35` — one behind Android 16; no compatibility warning applies |

### The ZIP-header check, on the released APK

Play Protect cares about this because packers have historically hidden code in
ZIP parser differentials (mismatched local/central headers, odd compression
methods, prepended data). The v0.47.14 release APK was audited directly:

```
entries=505  duplicates=0  compression={deflate: 247, stored: 258}
zipfile.testzip() = clean
EOCD is the last record (comment length 0, file ends exactly there)
first local header at byte 0 (nothing prepended)
```

The release job also runs `apksigner verify --print-certs` and
`zipalign -c -P 16 -v 4`, so signature integrity, alignment and the 16 KB page
rule are checked on every build.

## Filing the appeal

Google's page offers this form for exactly this case:
<https://support.google.com/googleplay/android-developer/contact/protectappeals>

Before filing, `SECURITY.md` should be current, and the build submitted should
be the newest release. The text below is written to be pasted in as-is; it
claims nothing the code does not do.

> **App:** suravidl (`com.suravidl.app`), open source at
> https://github.com/LoLyeah/suravidl, distributed as signed APKs from GitHub
> releases (not through Play).
>
> **What it is:** a personal video/audio downloader. It runs yt-dlp locally
> under Chaquopy, muxes with a bundled ffmpeg, and serves a loopback UI.
>
> **Why the flagged behaviours exist:**
> 1. `REQUEST_INSTALL_PACKAGES` + in-app updates. Off-store users need security
>    fixes. Updates come from the project's GitHub releases over HTTPS, are
>    checked against the SHA-256 in `version.json`, and since v0.47.14 the
>    downloaded APK's signing certificate must match the installed app's
>    (`ApkTrust.kt`) before Android's own installer is even invoked. The app
>    cannot install anything silently — the system package installer always
>    asks.
> 2. yt-dlp wheel updates (dynamic code loading). Stream extractors change
>    weekly; an APK release per extractor fix is not practical. The engine
>    downloads `py3-none-any` wheels from PyPI, verifies the SHA-256 against
>    PyPI's metadata, enforces an 80 MB cap and zip-slip checks, and only then
>    puts the verified copy on `sys.path`. No native code is downloaded.
> 3. ffmpeg/ffprobe as `lib*.so`. Since Android 10 the platform refuses to
>    `exec` from app-writable storage, so a static ffmpeg must live in
>    `nativeLibraryDir` under a `lib*.so` name. It is compiled from upstream
>    FFmpeg with `--disable-everything --enable-protocol=file,pipe,data` — it
>    has no network protocols at all.
> 4. Loopback daemon. The engine binds `127.0.0.1` only; every route needs a
>    per-process token, and cleartext is disabled system-wide except loopback.
>
> **Verification available to a reviewer:** source, the public GitHub Actions
> workflow that builds and signs every APK, `SHA256SUMS.txt` per release, and
> the release certificate
> `SHA-256 4A:03:C1:E5:52:61:12:03:EB:38:54:B1:9F:03:D4:1C:26:2E:5E:43:48:28:E0:04:39:97:9A:3A:DB:47:AF:DF`
> (`apksigner verify --print-certs`).
>
> We are not claiming the app avoids these patterns — it uses them deliberately
> and describes them publicly in `docs/SECURITY.md`. We are asking for review of
> whether an open-source, non-commercial downloader that verifies every byte it
> executes should be classified as Potentially Harmful.

## What would actually end the warning

Honest list, in order of certainty:

1. **Distribution through Google Play** — the warning is about sideloading;
   Play-signed installs do not get it. Play policy, however, restricts
   downloader apps and forbids dynamic code loading, so this app as built would
   not pass review without dropping the wheel updater and the self-installer.
2. **An accepted appeal** — possible, not guaranteed; Google can decline.
3. **Removing the patterns**: dropping `REQUEST_INSTALL_PACKAGES` (no in-app
   updates) and the yt-dlp wheel updater (extractors only change with APK
   releases). That is a product decision, not a bug fix, and it would leave the
   `lib*.so` and self-signed-sideload signals in place.

Removing the desktop ffmpeg *fetcher* from the APK (v0.47.15) does not change
any of this: Play Protect's scanner reads the manifest, `classes.dex` and ELF
headers, not Python assets.
