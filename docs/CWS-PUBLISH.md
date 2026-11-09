# Publishing the Chrome extension from the command line

The store item is `akllhdboeienonojebagehplgigjfkep`. Updates go up through the
**Chrome Web Store API v2** with an OAuth refresh token, so no browser and no
dashboard clicking is needed after the one-time setup below.

**Each upload must carry a higher `version` in `extension/manifest.json`.**
`scripts/cws_publish.py` refuses a version the store already has; `--bump patch`
raises it for you (the bump is a real edit — commit it).

Review is Google's: the script uploads and *submits*, and the store publishes
when the review passes. Nothing in this repo can skip that.

## One-time setup (5 minutes, in the browser)

Do this signed in as the account that owns the item.

1. **Enable the API.** <https://console.cloud.google.com/> → create a project
   (any name, e.g. `suravidl-cws`) → search "Chrome Web Store API" → **Enable**.

2. **OAuth consent screen.** APIs & Services → OAuth consent screen →
   **External** → fill App name, user support email, developer email → Save.
   Skip the Scopes screen. Then, on the consent screen page, click
   **Publish app** → confirm.

   This step matters: while the app is in *Testing*, Google issues refresh
   tokens that **expire after 7 days**, so a scheduled publish would break
   weekly. The `chromewebstore` scope is not sensitive, so publishing the app
   needs no Google verification.

3. **OAuth client.** Credentials → **Create credentials** → **OAuth client ID**
   → Application type **Web application** → Authorized redirect URI:

   ```
   https://developers.google.com/oauthplayground
   ```

   Copy the **Client ID** and **Client secret**.

4. **Refresh token.** Open <https://developers.google.com/oauthplayground>,
   click the gear (top right) → *Use your own OAuth credentials* → paste the
   client ID and secret. In "Input your own scopes" paste:

   ```
   https://www.googleapis.com/auth/chromewebstore
   ```

   → **Authorize APIs** → sign in with the owning account → **Exchange
   authorization code for tokens** → copy the **Refresh token**.

5. **Publisher ID.** In the Developer Dashboard (<https://chrome.google.com/webstore/devconsole>)
   → **Publisher → Settings** → copy the **Publisher ID**.

## Where the five values live

Local (this machine, used by me):

```bash
mkdir -p ~/.config/suravidl
cat > ~/.config/suravidl/cws.json <<'JSON'
{"client_id": "…", "client_secret": "…", "refresh_token": "…",
 "publisher_id": "…", "item_id": "akllhdboeienonojebagehplgigjfkep"}
JSON
chmod 600 ~/.config/suravidl/cws.json
```

CI: the same five as repository secrets — `CWS_CLIENT_ID`, `CWS_CLIENT_SECRET`,
`CWS_REFRESH_TOKEN`, `CWS_PUBLISHER_ID`, `CWS_ITEM_ID`. Without them
`.github/workflows/extension-publish.yml` skips itself with a notice.

The script prefers environment variables over the file, so CI and a local run
share one code path.

## Everyday use

```bash
python3 scripts/cws_publish.py --check          # published version, review state
python3 scripts/cws_publish.py --bump patch     # 0.5.20 → 0.5.21, upload, submit
python3 scripts/cws_publish.py --zip dist/suravidl-extension-chrome.zip
python3 scripts/cws_publish.py --no-publish     # upload a draft only
```

Exit codes: `0` done, `2` refused (version already published — bump it), `1`
failure. A refused run is the normal signal that the manifest needs a bump.

## What review does to a release

An upload is submitted for review and published when it passes; **it is not
live the moment the script returns**. `--check` reports `submitted` and
`published` separately for exactly that reason. Items are published with the
visibility already set in the dashboard — if the visibility was changed there,
the API refuses to publish until it has been published once by hand.
