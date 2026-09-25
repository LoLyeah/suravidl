#!/usr/bin/env bash
# Build static, single-file ffmpeg + ffprobe CLIs for Android.
#
# Usage: scripts/build_ffmpeg_android.sh <abi> <target-triple>
#   e.g. scripts/build_ffmpeg_android.sh arm64-v8a aarch64-linux-android
#        scripts/build_ffmpeg_android.sh x86_64 x86_64-linux-android
#
# Env: NDK=/path/to/android-ndk  (work dir = CWD)
# Output: out/<abi>/ffmpeg, out/<abi>/ffprobe
#
# Why static: the APK ships jniLibs entries that must be a single executable
# file (Android 10+ forbids exec from the app data dir; files extracted from
# jniLibs into nativeLibraryDir are executable). No shared libs => no SONAME
# juggling, no LD_LIBRARY_PATH.
#
# Why two builds: ffmpeg writes (muxers, encoders, filters), ffprobe only
# reads. Its own configure keeps the write-path code out of the APK. yt-dlp
# finds ffprobe next to the ffmpeg it is handed (it substitutes the program
# name in that path, so libffprobe.so beside libffmpeg.so just works).
#
# Scope: local post-processing (audio extraction, remux/merge, thumbnails,
# subtitle/metadata embedding) and stream inspection. Network protocols are
# deliberately excluded — yt-dlp downloads natively; these never open a socket.
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
) 2>&1 | tail -5

# ---- source ----------------------------------------------------------------
if [ ! -f ffmpeg-$FFMPEG_VERSION/configure ]; then
  curl -fsSLo ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz"
  tar xf ffmpeg.tar.xz
fi
cd ffmpeg-$FFMPEG_VERSION
OUT="$(cd ../../out/$ABI && pwd)"
LAME="$(cd ../lame-out && pwd)"

# Every crossing flag both builds share. Each build gets its own directory so
# the two configurations never share a config.h.
common_flags=(
  "--target-os=android" "--arch=$ARCH" "--cpu=$CPU"
  "--enable-cross-compile" "--sysroot=$SYSROOT"
  "--cc=$CC" "--cxx=$CXX" "--ar=$TC/llvm-ar" "--ranlib=$TC/llvm-ranlib"
  "--nm=$TC/llvm-nm" "--strip=$TC/llvm-strip" "--pkg-config=false"
  "--enable-static" "--disable-shared" "--enable-pic"
  "--disable-doc" "--disable-htmlpages" "--disable-manpages"
  "--disable-podpages" "--disable-txtpages" "--disable-debug"
  "--disable-everything" "--enable-protocol=file,pipe,data"
)

# The containers/parsers the downloader meets: what sites serve (mov/mp4,
# matroska/webm, ogg/opus, mp3, aac, flac, wav, mpegts, HLS pieces, images,
# webvtt/srt subtitles).
formats=(
  "--enable-demuxer=mov,matroska,webm,ogg,mp3,aac,flac,wav,mpegts,image2,concat,webvtt,srt"
  "--enable-parser=aac,ac3,flac,mpegaudio,opus,vorbis,h264,hevc,vp8,vp9,av1,mjpeg,png"
)

# ---- ffmpeg: the read + write half ----------------------------------------
mkdir -p b-ffmpeg
(
  cd b-ffmpeg
  ../configure "${common_flags[@]}" "${formats[@]}" \
    --disable-ffplay --disable-ffprobe \
    --enable-avfilter --enable-swresample --enable-swscale \
    --enable-muxer=ipod,mov,mp4,matroska,webm,ogg,opus,mp3,adts,flac,wav,mpegts,image2,mjpeg,webvtt,srt \
    --enable-decoder=aac,aac_latm,mp3,flac,alac,vorbis,opus,pcm_s16le,pcm_s16be,pcm_s24le,pcm_u8,h264,hevc,vp8,vp9,av1,mjpeg,png,webvtt,srt,subrip \
    --enable-encoder=aac,alac,flac,libmp3lame,mjpeg,png,webvtt,srt,mov_text \
    --enable-filter=aresample,anull,anullsrc,atrim,format,copy,null,scale,concat \
    --enable-bsf=aac_adtstoasc,h264_mp4toannexb,hevc_mp4toannexb,vp9_superframe \
    --enable-libmp3lame \
    --extra-cflags="-O2 -I$LAME/include" \
    --extra-ldflags="-L$LAME/lib -Wl,-z,max-page-size=16384" \
    --extra-libs="-lm"
  make -j"$(nproc)" ffmpeg
  "$TC/llvm-strip" ffmpeg
  cp ffmpeg "$OUT/ffmpeg"
)

# ---- ffprobe: the read-only half ------------------------------------------
mkdir -p b-ffprobe
(
  cd b-ffprobe
  ../configure "${common_flags[@]}" "${formats[@]}" \
    --disable-ffmpeg --disable-ffplay --enable-ffprobe \
    --extra-cflags="-O2" \
    --extra-ldflags="-Wl,-z,max-page-size=16384" \
    --extra-libs="-lm"
  make -j"$(nproc)" ffprobe
  "$TC/llvm-strip" ffprobe
  cp ffprobe "$OUT/ffprobe"
)

echo "--- built:"
file "$OUT/ffmpeg" "$OUT/ffprobe"
ls -l "$OUT/ffmpeg" "$OUT/ffprobe"
echo "--- 16 KB LOAD alignment (must be 0x4000):"
readelf -lW "$OUT/ffmpeg" | awk '/LOAD/{print $NF}' | sort -u
readelf -lW "$OUT/ffprobe" | awk '/LOAD/{print $NF}' | sort -u

# ---- what the runner can check ---------------------------------------------
# The binaries are Android ELF (interpreter /system/bin/linker64), so they
# cannot be executed here — behaviour is proven on-device by the instrumentation
# test FfmpegBinaryTest (runs both binaries, probes a file ffmpeg wrote, and
# asserts yt-dlp resolves ffprobe from the ffmpeg path it is handed).
echo "--- sanity: target ISA, alignment and the slim ffprobe"
readelf -h "$OUT/ffmpeg"  | awk -F: '/Machine/{print "ffmpeg  machine:" $2}'
readelf -h "$OUT/ffprobe" | awk -F: '/Machine/{print "ffprobe machine:" $2}'
pp_size=$(stat -c%s "$OUT/ffprobe")
ff_size=$(stat -c%s "$OUT/ffmpeg")
echo "ffmpeg  $ff_size bytes"
echo "ffprobe $pp_size bytes"
[ "$pp_size" -lt "$((ff_size / 2))" ] || {
  echo "ffprobe is no longer slim (${pp_size}B vs ffmpeg ${ff_size}B) — did" >&2
  echo "the probe-only configure lose its --disable flags?" >&2
  exit 1
}
"$TC/llvm-strings" "$OUT/ffprobe" | grep -m1 -q "ffprobe version" \
  || { echo "no ffprobe version string in the binary" >&2; exit 1; }
"$TC/llvm-strings" "$OUT/ffmpeg" | grep -m1 "ffmpeg version" || true
