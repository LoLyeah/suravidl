#!/usr/bin/env bash
# Build a static, single-file ffmpeg CLI for Android (post-processing only).
#
# Usage: scripts/build_ffmpeg_android.sh <abi> <target-triple>
#   e.g. scripts/build_ffmpeg_android.sh arm64-v8a aarch64-linux-android
#        scripts/build_ffmpeg_android.sh x86_64 x86_64-linux-android
#
# Env: NDK=/path/to/android-ndk  (work dir = CWD)
# Output: out/<abi>/ffmpeg
#
# Why static: the APK ships jniLibs entries that must be a single executable
# file (Android 10+ forbids exec from the app data dir; files extracted from
# jniLibs into nativeLibraryDir are executable). No shared libs => no SONAME
# juggling, no LD_LIBRARY_PATH.
#
# Scope: local post-processing (audio extraction, remux/merge, thumbnails,
# subtitle/metadata embedding). Network protocols are deliberately excluded —
# yt-dlp downloads natively; ffmpeg here never talks to the network.
set -euo pipefail

ABI="$1"
TARGET="$2"
FFMPEG_VERSION="${FFMPEG_VERSION:-8.1.3}"
LAME_VERSION="${LAME_VERSION:-3.100}"
API=24

TC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
CC="$TC/${TARGET}${API}-clang"
CXX="$TC/${TARGET}${API}-clang++"
SYSROOT="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot"

case "$ABI" in
  arm64-v8a) ARCH=aarch64; CPU=armv8-a ;;
  x86_64)    ARCH=x86_64;  CPU=x86-64  ;;
  *) echo "unknown abi: $ABI" >&2; exit 2 ;;
esac

mkdir -p build out/"$ABI"
cd build

# ---- lame (MP3 encoder; ffmpeg has no native one) --------------------------
if [ ! -f lame-$LAME_VERSION/configure ]; then
  curl -fsSLo lame.tar.gz \
    "https://downloads.sourceforge.net/project/lame/lame/$LAME_VERSION/lame-$LAME_VERSION.tar.gz"
  tar xzf lame.tar.gz
fi
(
  cd lame-$LAME_VERSION
  ./configure --host="$TARGET" --prefix="$PWD/../lame-out" \
    --disable-shared --enable-static --disable-frontend \
    CC="$CC" CXX="$CXX" AR="$TC/llvm-ar" RANLIB="$TC/llvm-ranlib"
  make -j"$(nproc)"
  make install
)

# ---- ffmpeg ----------------------------------------------------------------
if [ ! -f ffmpeg-$FFMPEG_VERSION/configure ]; then
  curl -fsSLo ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz"
  tar xf ffmpeg.tar.xz
fi
cd ffmpeg-$FFMPEG_VERSION
./configure \
  --target-os=android --arch="$ARCH" --cpu="$CPU" \
  --enable-cross-compile --sysroot="$SYSROOT" \
  --cc="$CC" --cxx="$CXX" --ar="$TC/llvm-ar" --ranlib="$TC/llvm-ranlib" \
  --nm="$TC/llvm-nm" --strip="$TC/llvm-strip" --pkg-config=false \
  --enable-static --disable-shared --enable-pic \
  --disable-doc --disable-htmlpages --disable-manpages \
  --disable-podpages --disable-txtpages \
  --disable-debug \
  --disable-ffplay --enable-ffprobe \
  --disable-everything \
  --enable-avfilter --enable-swresample --enable-swscale \
  --enable-protocol=file,pipe,data \
  --enable-demuxer=mov,matroska,webm,ogg,mp3,aac,flac,wav,mpegts,image2,concat,webvtt,srt \
  --enable-muxer=ipod,mov,mp4,matroska,webm,ogg,opus,mp3,adts,flac,wav,mpegts,image2,mjpeg,webvtt,srt \
  --enable-decoder=aac,aac_latm,mp3,flac,alac,vorbis,opus,pcm_s16le,pcm_s16be,pcm_s24le,pcm_u8,\
h264,hevc,vp8,vp9,av1,mjpeg,png,webvtt,srt,subrip \
  --enable-encoder=aac,alac,flac,libmp3lame,mjpeg,png,webvtt,srt,mov_text \
  --enable-parser=aac,ac3,flac,mpegaudio,opus,vorbis,h264,hevc,vp8,vp9,av1,mjpeg,png \
  --enable-filter=aresample,anull,anullsrc,atrim,format,copy,null,scale,concat \
  --enable-bsf=aac_adtstoasc,h264_mp4toannexb,hevc_mp4toannexb,vp9_superframe \
  --enable-libmp3lame \
  --extra-cflags="-O2 -I$PWD/../lame-out/include" \
  --extra-ldflags="-L$PWD/../lame-out/lib -Wl,-z,max-page-size=16384" \
  --extra-libs="-lm"

make -j"$(nproc)"
"$TC/llvm-strip" ffmpeg
"$TC/llvm-strip" ffprobe
cp ffmpeg "../../out/$ABI/ffmpeg"
cp ffprobe "../../out/$ABI/ffprobe"

echo "--- built:"
file "../../out/$ABI/ffmpeg" "../../out/$ABI/ffprobe"
echo "--- 16 KB LOAD alignment (must be 0x4000):"
readelf -lW ffmpeg | awk '/LOAD/{print $NF}' | sort -u
readelf -lW ffprobe | awk '/LOAD/{print $NF}' | sort -u
echo "--- ffmpeg can still see ffprobe next to it:"
../../out/$ABI/ffprobe -version 2>&1 | head -1 || true
echo "--- version (from configure):"
grep -m1 "version" config.log 2>/dev/null | head -1 || true
strings -a ffmpeg 2>/dev/null | grep -m1 "ffmpeg version" || echo "(version string not greppable, fine)"
