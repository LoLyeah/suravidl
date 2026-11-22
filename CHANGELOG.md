# Changelog

Every tagged release, newest first. Entries are the notes the app shows
after an update, followed by the commits that landed since the tag before.

## v0.49.15 — 2026-11-22

- The app and the browser extension now check each other: an out-of-date copy says so on the spot and names which side to update, instead of failing one download at a time.
- A failed download offers Support info on its own row — versions and the last few failures, no token, cookies or links — and Settings → Advanced copies the same block.
- A download with no sound is caught from the file itself: one retry through the page when that can fix it, and a plain sentence on the card when it cannot.
- A job that cannot fit is refused before it starts, with the free space in the message, and a file shorter than its source says so.
