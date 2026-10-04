#!/bin/bash
# suravidl's macOS self-update swap (v0.42.0 "the crossing").
#
# Called detached by the app as it quits:
#   bash macos_swap.sh suravidl-apply <app-bundle> <update-zip> <app-pid>
#
# It waits for the old process to die, extracts the new bundle BESIDE the
# old one (same filesystem — the swap below is a rename, and renames never
# cross devices), then swaps by rename: a running bundle can be renamed,
# deleting its files mid-run is what breaks. Any failure rolls the old
# bundle back and still reopens it — the user must never be left with
# nothing to launch.
set -u
APP="$2"
ZIP="$3"
PID="$4"
DIR="$(dirname "$APP")"
BASE="$(basename "$APP")"

relaunch() {
  # the CI dry-run stops before the app comes back up
  [ -n "${SURAVIDL_APPLY_DRYRUN:-}" ] && return 0
  open "$1"
}

# 1) wait for the app to exit (bounded: 90s), then a breath for its locks
for _ in $(seq 1 180); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.5
done
sleep 1

# 2) extract the new bundle beside the old one
#    mktemp, not a PID-named directory (v0.43.3 audit follow-up): a
#    predictable name in the install directory is a symlink-planting
#    target for a local program; mktemp creates it 0700 and will not
#    reuse an existing path.
STAGE="$(mktemp -d "$DIR/.suravidl-update.XXXXXX")" || { relaunch "$APP"; exit 1; }
if ! ditto -x -k "$ZIP" "$STAGE"; then
  rm -rf "$STAGE"; relaunch "$APP"; exit 1
fi
NEW="$STAGE/$BASE"
[ -d "$NEW" ] || NEW="$(find "$STAGE" -maxdepth 1 -name '*.app' | head -1)"
if [ ! -d "$NEW" ]; then
  rm -rf "$STAGE"; relaunch "$APP"; exit 1
fi
# the zip was sha256-verified against the update manifest before this
# script ran — its bytes are the release's bytes. The quarantine bit only
# rides browser downloads, not the app's own fetches; the strip is belt
# for odd carriers so a stray bit cannot prompt Gatekeeper on a bundle
# the manifest already vouches for.
xattr -dr com.apple.quarantine "$NEW" 2>/dev/null

# 3) swap by rename; roll back on any failure
OLD="$(mktemp -d "$DIR/.suravidl-old.XXXXXX")" || { rm -rf "$STAGE"; relaunch "$APP"; exit 1; }
rm -rf "$OLD"   # the placeholder goes — the rename below needs the name free
if ! mv "$APP" "$OLD"; then
  rm -rf "$STAGE"; relaunch "$APP"; exit 1
fi
if mv "$NEW" "$APP"; then
  rm -rf "$OLD"
  # the carrier is spent once the swap lands (v0.42.1): the old app is
  # gone and the new one runs from where it should — the zip goes too
  rm -f "$ZIP"
else
  mv "$OLD" "$APP"    # nothing lost: the version they had comes back
fi
rm -rf "$STAGE"

# 4) come back up
relaunch "$APP"
exit 0
