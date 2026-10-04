#!/usr/bin/env bash
# Build a Linux AppImage from a PyInstaller one-file binary. Usage:
#   scripts/build_appimage.sh <binary> <out.AppImage>
set -euo pipefail
BIN="${1:?usage: build_appimage.sh <binary> <out.AppImage>}"
OUT="$(realpath -m "${2:?usage: build_appimage.sh <binary> <out.AppImage>}")"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

APPDIR="$WORK/suravidl.AppDir"
mkdir -p "$APPDIR/usr/bin"
cp "$BIN" "$APPDIR/usr/bin/suravidl"
chmod +x "$APPDIR/usr/bin/suravidl"

cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/sh
exec "$APPDIR/usr/bin/suravidl" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/suravidl.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=suravidl
Comment=Universal web video downloader
Exec=suravidl
Icon=suravidl
Terminal=false
Categories=AudioVideo;Network;
EOF

# icon in AppDir root (AppImage convention) + hicolor dir
cp "$ROOT/assets/logo.png" "$APPDIR/suravidl.png"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$ROOT/assets/logo.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/suravidl.png"

# fetch appimagetool — versioned, digest-checked (v0.43.2 audit): the old
# `continuous` tag is a moving release asset, and the old fallback mirror
# was never verified at all. Bump TOOL_VERSION + TOOL_SHA256 together, in
# one commit, to upgrade.
TOOL_VERSION=1.9.1
TOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
TOOL="$WORK/appimagetool"
curl -fsSL -o "$TOOL" \
  "https://github.com/AppImage/appimagetool/releases/download/${TOOL_VERSION}/appimagetool-x86_64.AppImage"
echo "${TOOL_SHA256}  ${TOOL}" | sha256sum -c -
chmod +x "$TOOL"

ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT" >/dev/null 2>&1 \
  || ARCH=x86_64 "$TOOL" "$APPDIR" "$OUT"

echo "built: $OUT"
