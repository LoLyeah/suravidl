# What's next: four features, three waves

Owner's request (2026-10-10): all four suggestions, planned properly. This
is the order, what each round contains, and how each is proven. Working
names only — the real titles come at bump time.

Order rationale: the two small ones train the loop and ship this week;
the recorder is the flagship and deserves a quiet base; the follower is
last because it is the most "away-from-keyboard" feature and should be
built on everything the recorder taught about long-running jobs.

## Versioning: this campaign is the 0.46 arc

The second digit is the arc; every `x.y.0` opens a titled one (0.43.0
"the refresh", 0.44.0 "the phrasebook", 0.45.0 "the ledger") and the
`x.y.z` releases inside belong to it. 0.45.x was the ledger —
reliability, honest messages, migrations. These four features are new
capability, so the campaign opens **0.46** and the waves are 0.46.0 →
0.46.1 → 0.46.2.

**Why not 1.0:** 1.0 is a promise — that a 1.x.y update never breaks an
older extension, an older app, or an existing database. This project
moves its engine API, its schema and its companion contracts every week
(both were touched in this very arc), so 1.0 would be a boast, not a
fact. The gate for it: the recorder and the follower land, and the
API/schema/companion compat story is written into a policy (old
things keep working by rule, deprecations get a window). When that
policy exists, 1.0 is earned — not before.

## Ground rules (every wave)

- One tag = one release; extensions untouched unless they change.
- Suite green locally, then tag → release + AMO(guard) + android; APK
  checked byte-identical for the files the round touched.
- `docs/`  updated in the same round the behaviour lands. No promises
  ahead of the build.
- Field-test list handed over with each release; honest "not promised"
  entries updated when a limit is real (we write our refusals down).

## Wave 1 — v0.46.0 "the toolbox"  (bulk paste + diagnostics) — SHIPPED

Small, immediately felt, and they make every later wave faster to debug.

### 1a. Paste-many-at-once

Today the extension can queue several finds in one call (`/jobs/batch`),
but the app's own URL box takes one link. Someone sending nine links is
nine paste-probe-queue rounds.

- **UI**: the URL box accepts a multi-line paste. Each non-empty line is
  probed in the background, bounded (3 at a time, capped at 20 lines per
  paste), and becomes a mini-row: title · duration · host, or that
  line's own honest error in place (the TikTok-photo sentence, a 404,
  a sign-in wall — the existing per-link error mapping, one line each).
  Ticked rows queue best-quality via the existing batch route; tapping a
  row opens the normal single flow (full format list) for that link.
- **Engine**: no new endpoint — `/probe` per line plus the existing
  `/jobs/batch`; duplicate lines are collapsed before probing.
- **Android**: same page; the share sheet stays single-link (out of
  scope, and the OS delivers one at a time anyway).
- **Tests**: the line-splitting/dedupe/bounds helper (JS pins), per-line
  error mapping (a mixed paste: good, 404, TikTok-photo), and the batch
  endpoint's existing per-item `skipped` behaviour.
- **Risks**: 30 probes would hammer the engine → hard cap + bounded
  workers, said on screen ("showing the first 20").

### 1b. Diagnostics bundle

Two weeks of field debugging went through screenshots. This turns a bug
report into one paste.

- **Engine**: `GET /diagnostics` (auth): engine version, yt-dlp version,
  python, platform, the ffmpeg probe summary (which encoders are
  present/absent — mov_text, webp, aac), settings with every secret
  redacted, the `/logs` tail (~200 lines), and a compact last-jobs
  summary. **The token must never appear — a test asserts its absence
  through the whole payload.**
- **UI**: Settings → **Copy diagnostics** (clipboard, with a textarea
  fallback and a "save .txt" for viewers where the WebView clipboard
  needs a gesture).
- **Tests**: redaction (the token string absent), the shape, the ffmpeg
  fields, and that `/logs` output is what it claims.
- **Risks**: none real; the redaction test is the whole game.

## Wave 2 — v0.46.1 "the recorder"  (live streams, first-class) — SHIPPED

Half of this exists: `live_from_start` is a setting the downloader
already honours, and the probe card already reads `is_live`. What is
missing is the house around it — live jobs still look like downloads
that never finish, and a "stop" must never eat the recording.

- **Probe**: a live result shows `● LIVE` and offers **Record** (from
  now) or **Record from the start** (the setting still decides the
  default). End-of-stream URLs are unaffected.
- **Job card**: a pulsing `REC`, elapsed time and bytes, **no fake
  percentage** (there is no total), and **Stop & keep** as the primary
  control. Cancel on a live job finalizes the file already on disk and
  marks it `recorded (stopped)`; the partial is never deleted by the
  cancel path.
- **Engine**: a `live` flag on jobs (DB column; the per-boot column
  alignment law applies). The stall watchdog **exempts live jobs** — a
  quiet moment is not a wedge; a light "still live?" check replaces the
  kill. `live_from_start` keeps working; a live job never runs the
  post-download fixers mid-stream.
- **Android**: the foreground service already carries downloads
  (dataSync); add the one-line warnings a phone deserves at record time
  (long recordings use storage; keep the app un-optimized).
- **Tests**: a fixture live server (a playlist that appends a segment
  every couple of seconds) records, stops, and leaves a non-empty
  file; the watchdog exemption; from-now vs from-start opts.
- **Risks**: site reality — YouTube/Twitch lives need the extractors'
  own logins occasionally, TikTok lives are often unsupported by
  yt-dlp, and the probe will say so in place rather than pretend.
  Storage: the size is on the card the whole time; stop is always one
  tap.

## Wave 3 — v0.46.2 "the follower"  (watch list) — SHIPPED

Turn suravidl from a tool you visit into one that works for you: follow
a playlist or channel, grab what's new, skip what you already have.

- **Engine**: a `follows` table (url, label, cadence, per-follow preset,
  auto-queue, last_checked, last_error) and a checker daemon (jittered
  interval, a cap per check, a per-host minimum gap). Jobs gain a
  `video_id` column (schema + alignment law) — the dedupe key: skip
  anything already completed, retry nothing on its own, never re-grab.
- **UI**: **☆ Follow** appears on probe cards for playlists/channels;
  a Follows panel lists them (cadence, last check, "check now",
  remove), and a new grab carries a quiet `watch list` tag on its card.
- **Android honesty**: the engine runs while the app does — checks
  happen when you open the app (catch-up) plus the manual button. Said
  plainly in the panel; no background illusion.
- **Tests**: a fixture playlist that changes between checks (new entry
  → exactly one queued; same entry again → skipped); the cap; a failing
  check records `last_error` without spamming the queue.
- **Risks**: per-site rate limits (jitter + the gap + the cap are the
  mitigation); runaway growth (auto-queue is per-follow and visible on
  the panel).

## Not planned, on purpose

- DRM, anything hosted/public, cross-device sync (the engine stays
  loopback-only — the standing security decision).
- Image/gallery downloads (the TikTok slideshow answer is the message,
  the sniffer is the tool).
- iOS.

## What the owner does

- Wave 1: try a 5+ link paste of nonsense and real links; open Copy
  diagnostics once and paste it somewhere to see the size.
- Wave 2: record a real live (YouTube and Twitch first; TikTok lives we
  try and let it say no honestly), stop one mid-way and confirm the
  file plays.
- Wave 3: follow one playlist you actually use for a couple of days.
