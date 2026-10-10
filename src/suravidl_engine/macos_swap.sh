#!/bin/bash
# suravidl's macOS self-update swap (v0.42.0 "the crossing"; the relaunch
# hardened in v0.46.3 "the comeback").
#
# Called detached by the app as it quits:
#   bash macos_swap.sh suravidl-apply <app-bundle> <update-zip> <app-pid>
#
# It waits for the old process to die — and ENDS it if the window is gone
# but the process lingers, because a lingering window-less process is
# exactly what a plain `open` activates instead of launching fresh (the
# field's "update and restart just shuts down", user report 2026-10-10).
# Then it extracts the new bundle BESIDE the old one (same filesystem —
# the swap below is a rename, and renames never cross devices), and swaps
# by rename: a running bundle can be renamed, deleting its files mid-run
# is what breaks. Any failure rolls the old bundle back and still reopens
# it — the user must never be left with nothing to launch.
#
# The relaunch is the one leg no CI dry-run can ride (the dry-run stops
# before the app comes back up) — and it used to fail in total silence.
# Now every attempt is logged (~/Library/Logs/suravidl-update.log), the
# reopen forces a FRESH instance (`open -n`), and a direct-exec fallback
# covers LaunchServices saying no. Silence was the real bug.
set -u
APP="$2"
ZIP="$3"
PID="$4"
DIR="$(dirname "$APP")"
BASE="$(basename "$APP")"
EXEC="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' \
        "$APP/Contents/Info.plist" 2>/dev/null || basename "$APP" .app)"
LOG="${SURAVIDL_UPDATE_LOG:-$HOME/Library/Logs/suravidl-update.log}"
WAIT_TICKS="${SURAVIDL_APPLY_WAIT_TICKS:-180}"   # CI shrinks this

say() {
  { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; } >>"$LOG" 2>/dev/null || true
}

alive() {
  # kill -0 lies about a zombie: a just-killed process whose parent has not
  # reaped it still answers signals (macOS's bash 3.2 reaps lazily — this
  # made the CI linger check fail on a process that was already dead).
  # A zombie is dead for our purposes; so is a vanished pid.
  st="$(ps -p "$1" -o stat= 2>/dev/null)" || return 1
  case "$st" in Z*) return 1 ;; *) return 0 ;; esac
}

relaunch() {
  # the CI dry-run stops before the app comes back up
  [ -n "${SURAVIDL_APPLY_DRYRUN:-}" ] && return 0
  # open -n: force a new instance. A plain open can activate a stale,
  # window-less registration — the user sees nothing come back.
  if open -n "$1" 2>>"$LOG"; then
    say "relaunch: open -n ok -> $1"
    return 0
  fi
  # LaunchServices said no; exec the inside directly — a GUI app spawned
  # from a user-session script still gets the Aqua session.
  INNER="$1/Contents/MacOS/$EXEC"
  if [ -x "$INNER" ]; then
    nohup "$INNER" >/dev/null 2>&1 &
    say "relaunch: open -n failed; inner executable spawned -> $INNER"
    return 0
  fi
  say "relaunch: FAILED both ways — the app is at $1"
  return 1
}

# 1) wait for the app to exit (bounded), then a breath for its locks
for _ in $(seq 1 "$WAIT_TICKS"); do
  alive "$PID" || break
  sleep 0.5
done
if alive "$PID"; then
  # Still here: the window is gone (the app destroys it before spawning
  # us) but the process lingers. End it — politely, then firmly — or the
  # reopen lands on a dead instance. Guarded: only when the pid still IS
  # the app's executable (never a recycled pid).
  case "$(ps -p "$PID" -o comm= 2>/dev/null)" in
    *"$EXEC"*)
      say "the old process lingered; ending it (pid $PID)"
      kill -TERM "$PID" 2>/dev/null
      for _ in $(seq 1 10); do
        alive "$PID" || break
        sleep 0.5
      done
      kill -KILL "$PID" 2>/dev/null
      ;;
    *) say "pid $PID lingers but is not the app any more; leaving it" ;;
  esac
fi
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
say "swap done; relaunching $APP"
relaunch "$APP"
exit 0
