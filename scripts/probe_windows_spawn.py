"""Which Windows spawn mode actually runs a detached PowerShell? (CI probe)

The v0.45.9/v0.45.10 release smoke showed the app's chain spawn
(DETACHED_PROCESS | CREATE_NO_WINDOW) writes nothing at all on a GitHub
windows runner — the PowerShell either never starts or dies before its
first statement. The app's spawn needs a mode that works everywhere a
desktop might be (and the smoke, too). This probe spawns the same
PowerShell under each candidate mode, with a marker file as evidence,
and prints which ones actually execute.

Temporary: driven by .github/workflows/wsprobe.yml (workflow_dispatch).
"""
import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MARK = "Set-Content -LiteralPath {marker} -Value ('ran ' + (Get-Date).ToString('HH:mm:ss'))"


def encoded(script: str) -> list[str]:
    blob = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive",
            "-EncodedCommand", blob]


def plain(script: str) -> list[str]:
    return ["powershell.exe", "-NoProfile", "-NonInteractive",
            "-Command", script]


def swhide_kwargs():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return dict(startupinfo=si)


MODES = [
    ("detached+nowindow", dict(creationflags=0x00000008 | 0x08000000)),
    ("detached", dict(creationflags=0x00000008)),
    ("nowindow", dict(creationflags=0x08000000)),
    ("swhide", None),          # STARTUPINFO SW_HIDE, no creationflags
    ("plain", dict()),         # inherits our console
]


def main() -> int:
    if os.name != "nt":
        print("windows-only probe — skipped")
        return 0
    base = Path(tempfile.mkdtemp(prefix="spawnprobe-"))
    ran = 0
    for form, builder in (("enc", encoded), ("cmd", plain)):
        for name, kw in MODES:
            marker = base / f"{form}-{name}.txt"
            argv = builder(MARK.format(marker=marker))
            kwargs = swhide_kwargs() if (name == "swhide" and kw is None) else (kw or {})
            try:
                p = subprocess.Popen(argv, close_fds=True, **kwargs)
            except Exception as e:  # noqa: BLE001 — the probe reports everything
                print(f"{form} {name:18s} spawn raised: {e!r}")
                continue
            deadline = time.time() + 20
            while time.time() < deadline and not marker.exists():
                time.sleep(0.5)
            rc = p.poll()
            if marker.exists():
                ran += 1
                print(f"{form} {name:18s} -> {marker.read_text().strip()} (exit={rc})")
            else:
                print(f"{form} {name:18s} -> NOTHING (exit={rc})")
    print("probe:", "OK" if ran else "ALL MODES FAILED")
    return 0 if ran else 1


if __name__ == "__main__":
    sys.exit(main())
