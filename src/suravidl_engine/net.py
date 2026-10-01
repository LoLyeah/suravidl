"""TLS trust for the engine's own HTTP calls, wherever the app runs.

This module exists because of what a frozen macOS bundle *is*: its Python has
no discoverable OpenSSL store — the compiled-in paths do not exist on macOS,
and Python never consults the Keychain — so every stdlib `urlopen` dies with
`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. The app's
update check was the first casualty ("could not check for updates"); the
direct-media probes were next in line. yt-dlp never noticed because it loads
certifi's bundle itself — the fix is to do the same, the same way.

Neither Linux (system store) nor Windows needed it, but both keep working:
certifi is *added* to the platform's store, never substituted for it.
"""
from __future__ import annotations

import ssl


def ssl_context() -> ssl.SSLContext:
    """A default TLS context with certifi's CA list added when available.

    `create_default_context()` keeps whatever the platform offers — system
    and corporate stores included — and certifi's bundle is layered on top,
    so builds that ship no discoverable store can still verify real
    certificates.
    """
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - absent certifi must not break TLS
        pass
    return ctx
