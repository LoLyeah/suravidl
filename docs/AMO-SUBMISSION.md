# Publishing the Firefox add-on on addons.mozilla.org

**Status:** submitted 2026-09-26 — `suravidl 0.5.2` is in review. The version's
own page (where the review state shows):
<https://addons.mozilla.org/en-US/developers/addon/suravidl/versions/6516441>

The Firefox build is Manifest V2, which is fine: Mozilla still supports MV2
alongside MV3 and has said so repeatedly (their Add-ons Policies update of June
2025 is explicit — "developers are not required to adopt Manifest V3").

Submission is automated in `.github/workflows/amo.yml`; what is left is the
account side, which only you can do.

## What only you can do (about five minutes)

1. **Have a Mozilla account and accept the developer agreement.** Sign in at
   <https://addons.mozilla.org> and open the Developer Hub. The first time you
   submit, AMO asks you to accept the Firefox Add-on Distribution Agreement.

2. **Create AMO API credentials.** In the Developer Hub go to
   **API Keys → Generate new credentials**. It shows two values:
   - **JWT issuer** — this is the API key.
   - **JWT secret** — shown **once**; copy it before leaving the page.
   These can be revoked and regenerated at any time, so they are safer to
   handle than a password.

3. **Put them in the repository as secrets** (this is what the workflow reads —
   it also keeps the secret out of any chat): GitHub → the repository →
   **Settings → Secrets and variables → Actions → New repository secret**:
   - `AMO_JWT_ISSUER`
   - `AMO_JWT_SECRET`

4. **Decide the licence.** AMO refuses a listing without one, and the repo
   currently has none. `docs/amo-metadata.json` is filled in with **MIT**;
   change `version.license` (and drop a `LICENSE` file in the repository) if
   you would rather have `MPL-2.0`, `Apache-2.0`, `GPL-3.0-only` or another
   slug from AMO's list.

## What happens then

```
Actions → amo → Run workflow        # first submission, no tag needed
```

or simply push a `v*` tag, which submits the extension version in the manifest
for review as part of the release.

The workflow assembles the package exactly like the release job does
(`extension/*` plus `extension/firefox/manifest.json`, minus the test harness),
lints it with Mozilla's own linter, and runs:

```
web-ext sign --channel listed --amo-metadata docs/amo-metadata.json …
```

**What that command does, honestly:** it uploads the version, Mozilla runs its
validator, and the version then sits in **"awaiting review"**. The CLI waits a
few minutes for a signature and then gives up — the upload was already done at
that point, so the workflow treats that timeout as success-with-a-notice, and
the log prints the version's own page on AMO:

```
https://addons.mozilla.org/en-US/developers/addon/suravidl/versions/<id>
```

That page is where the review state lives. Re-running for a version AMO already
has is reported as "nothing to do" rather than a failure: every release tag
submits the extension version whether or not the extension changed.

Watching the process:

- Developer Hub → your add-on → **Manage → Status & Versions** shows the
  version and its review state.
- Review for a new add-on with `<all_urls>` is done by a human, usually within
  a few days for a small extension. `docs/amo-metadata.json` carries
  `approval_notes` that explain how to test it against the engine, which is the
  usual reason a companion extension gets rejected — reviewers cannot see a
  video play without the downloader running locally.
- If a reviewer asks for anything, the answer can go in the same `approval_notes`
  field; re-running the workflow submits a new version.

## Updates

Every later version goes through the same path: bump the version in **both**
`extension/manifest.json` and `extension/firefox/manifest.json` (a test enforces
that they match), then tag. AMO requires a version higher than the one already
published, so the next release is enough — no manual re-listing.

## What is in the submission

- `docs/amo-metadata.json` — summary, description, categories
  (`download-management`, `photos-music-videos`), homepage, support URL, privacy
  policy, licence, and the reviewer notes.
- `docs/PRIVACY.md` — the privacy policy URL AMO asks for.
- The packaged files — `extension/*` with the MV2 manifest; no test harness, no
  build step, no minification (nothing to declare as generated code, and nothing
  for the reviewer to unpack).
