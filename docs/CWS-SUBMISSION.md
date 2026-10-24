# Publishing suravidl to the Chrome Web Store

The extension ships in every release as **`suravidl-extension-chrome.zip`**
(manifest at the archive root — what the store expects). Everything below is
the first-publish runbook; the listing copy is copy-paste ready.

## 0. Before the dashboard

- A Google account with **2-Step Verification** on it (required for developers).
- **One-time US$5** developer registration fee (Chrome Web Store Developer
  Dashboard → Register). It is per account, not per extension.
- The zip: <https://github.com/LoLyeah/suravidl/releases/latest> →
  `suravidl-extension-chrome.zip`.
- A privacy policy URL: <https://github.com/LoLyeah/suravidl/blob/main/docs/PRIVACY.md>

## 1. Create the item

1. <https://chrome.google.com/webstore/devconsole> → **Add new item**.
2. Upload `suravidl-extension-chrome.zip`. The item is created in **Draft**
   (nothing is public yet) and gets its permanent extension ID.
3. The manifest version becomes the item version (currently **0.5.18**).

## 2. Store listing

- **Name**: `suravidl`
- **Summary** (≤132 chars):
  `Send videos from any page to your own suravidl engine — a self-hosted downloader that runs on your computer.`
- **Category**: Productivity
- **Language**: English
- **Description** (plain text, no markdown):

```
suravidl finds the video or audio playing on the page you are on and hands the one you pick to the suravidl engine running on your own computer.

There is no suravidl service. The engine is a small self-hosted app (desktop app, pip package or Android app — all free and open source) that does the actual downloading with yt-dlp: 1000+ supported sites, playlists, audio-only, subtitles, quality selection, a queue, and a history you can retry or rename.

How to use it:
1. Install and start the suravidl engine on your computer. It listens on http://127.0.0.1:8787 and prints an access token.
2. Paste that token into this extension's options page (and the engine address, if you changed it).
3. Play a video, click the toolbar icon, and pick it from the list. Streams the page keeps hidden behind a JavaScript player are found too — including ones with no file extension, on another host.

What it does not do: DRM. Widevine, FairPlay and Netflix-style encrypted streams are detected and reported, not downloaded.

The extension talks only to the engine on your own machine (127.0.0.1 by default). Nothing is sent to us: no account, no analytics, no telemetry.
```

- **Graphics**
  - Store icon: `icons/icon128.png` (already 128×128).
  - Screenshots: 1–5 at **1280×800** (or 640×400), PNG/JPEG. Ready to upload:
    `docs/cws/1-streams.png`, `docs/cws/2-single.png`, `docs/cws/3-engine.png`. Suggested
    frames: (a) popup with a detected stream list, (b) the fetched
    qualities for one stream, (c) options page with the token field.
  - Optional small promo tile: 440×280.

## 3. Privacy practices (this is where item reviews die)

**Single purpose** (one sentence):

```
Send the media playing on the current page to the user's own locally running suravidl engine.
```

**Permission justifications**

- `webRequest`:
```
Observes network requests on the active tab to detect media streams (HLS/DASH playlists, video/audio files) so the popup can list them. It never blocks or modifies a request.
```
- `host_permissions: <all_urls>`:
```
Media can be served from any host, and the sites a user visits cannot be enumerated in advance. The extension only reads request URLs, headers and content types of media requests on the tab the user is on; it does not read or modify page content or personal data.
```
- `storage`:
```
Stores the engine address and access token the user enters, plus the streams detected for each open tab (cleared when the tab closes).
```
- `contextMenus`:
```
Adds a "Send this page to suravidl" right-click entry.
```
- Content scripts (`pagefind.js`, `pk.js`):
```
pagefind.js detects media players and their sources in the page; pk.js runs in the page's own world to read the decode key a player keeps in memory, so playlists that are scrambled by the site can be handed to the local engine.
```

**Data usage** — declare exactly this:

- Authentication information: **yes** — the engine's local access token is
  stored; session headers/cookies for the stream the user picks are passed to
  the engine **on the same machine**.
- Website content / web history: **yes, processed locally** — media request
  URLs on the active tab; sent only to `127.0.0.1`.
- Sold to third parties: **no**. Used for purposes unrelated to the single
  purpose: **no**. Used for creditworthiness/lending: **no**.
- **Remote code: no** (MV3, no eval, no remote scripts — verified in the tree).

**Privacy policy URL**: `https://github.com/LoLyeah/suravidl/blob/main/docs/PRIVACY.md`

## 4. Distribution + submit

- Visibility: **Public**, all regions.
- **Submit for review.** Broad host permissions mean a human review: expect
  days, occasionally weeks. Nothing is public until it passes.
- Do **not** name specific sites (YouTube and friends) anywhere in the
  listing — a "download from <site>" claim invites a policy rejection. The
  copy above deliberately says "any page" and "your own engine".

## 5. After approval

- The item goes live at `https://chromewebstore.google.com/detail/<id>`.
- Updates: bump `extension/manifest.json` version, cut a release, then either
  upload the new zip by hand or automate it with the **Chrome Web Store API
  v1.1** (OAuth client + refresh token stored as repo secrets) — the same
  shape as `.github/workflows/amo.yml`.
- Keep the extension version and the engine version independent (they already
  are: 0.5.18 vs 0.47.10).
