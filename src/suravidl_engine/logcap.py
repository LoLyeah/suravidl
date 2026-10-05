"""A bounded, in-memory capture of yt-dlp's own log lines (v0.44.x audit).

The verbose switch asked people to turn on a log they could never read: the
engine ran yt-dlp with no logger, so the output went to a console nobody sees
(the desktop shell has no console at all). This keeps the last lines of
whatever yt-dlp said, for the Log card in the app.

Nothing touches disk, the buffer dies with the process, and every entry only
exists behind the engine's own token — same wall as the rest of the API.
Wired once, centrally, in `curated_settings_opts`: any YoutubeDL the engine
builds with verbose on logs here, jobs and probes alike.
"""
import threading
from collections import deque

_LOCK = threading.Lock()
_LINES: deque = deque(maxlen=500)
_MAX_LINE = 500          # one pathological line must not eat the buffer


def _push(msg: object) -> None:
    try:
        text = str(msg)
    except Exception:  # noqa: BLE001 - logging must never raise into yt-dlp
        return
    for raw in text.splitlines() or [""]:
        line = raw.rstrip()
        if len(line) > _MAX_LINE:
            line = line[:_MAX_LINE] + "…"
        with _LOCK:
            _LINES.append(line)


class CaptureLogger:
    """yt-dlp's logger protocol — debug/info/warning/error, string in."""

    def debug(self, msg):
        _push(msg)

    def info(self, msg):
        _push(msg)

    def warning(self, msg):
        _push("WARNING: " + str(msg))

    def error(self, msg):
        _push("ERROR: " + str(msg))


def logger() -> CaptureLogger:
    return CaptureLogger()


def lines() -> list[str]:
    with _LOCK:
        return list(_LINES)


def clear() -> None:
    with _LOCK:
        _LINES.clear()
