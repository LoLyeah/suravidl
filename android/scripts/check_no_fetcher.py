"""Fail when the release APK still carries the desktop-only ffmpeg fetcher.

v0.47.15 "the spare": the phone's ffmpeg already ships in nativeLibraryDir, so
`src/suravidl_engine/tools.py` is staged out of the Android build (Chaquopy has
no per-file exclude). This is the artifact-level proof: the Chaquopy archive in
the APK must contain the engine and must not contain the fetcher.

usage: python3 android/scripts/check_no_fetcher.py [path/to/app-release.apk]
"""
from __future__ import annotations

import io
import sys
import zipfile

DEFAULT_APK = "android/app/build/outputs/apk/release/app-release.apk"

# strings that only the fetcher carries (a URL constant survives into a .pyc
# even where sources are compiled)
MARKERS = (
    b"def start_download",
    b"ffmpeg-static/releases/download",
    b"/tools/ffmpeg/remove",
)


def engine_entries(apk: str):
    """(name, bytes) for everything the APK holds from the engine."""
    with zipfile.ZipFile(apk) as z:
        for name in z.namelist():
            if not name.startswith("assets/chaquopy/"):
                continue
            data = z.read(name)
            yield name, data
            if name.endswith(".imy"):
                try:
                    inner = zipfile.ZipFile(io.BytesIO(data))
                except zipfile.BadZipFile:
                    continue
                for member in inner.namelist():
                    if "suravidl_engine" in member:
                        yield f"{name}!{member}", inner.read(member)


def main() -> int:
    apk = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_APK
    names, hits = [], []
    for name, data in engine_entries(apk):
        names.append(name)
        for marker in MARKERS:
            if marker in data:
                hits.append((name, marker.decode("utf-8", "replace")))
    if not any("suravidl_engine" in n for n in names):
        print("the engine is not in the APK at all — the staging task broke")
        return 2
    if hits:
        for name, marker in hits:
            print(f"FETCHER IN APK: {name} :: {marker}")
        return 1
    print(f"no fetcher in the APK ({len(names)} engine entries checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
