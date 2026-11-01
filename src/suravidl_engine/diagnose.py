"""Why did that URL fail? — a layer-by-layer probe (v0.47.21).

A failed job says "the site never answered in time", which is true and
useless: it can mean the name does not resolve, the port is blocked, the TLS
handshake is refused, or the server accepted the connection and then stalled.
Those need different actions from the user, so on failure the engine walks the
same path the download would and reports the first layer that broke.

Nothing here is a bypass: it connects, reads no content, and never disables
verification. It only names what happened.
"""
from __future__ import annotations

import socket
import ssl
import time
from urllib.parse import urlsplit


def _host_port(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return host, port


def explain(url: str, timeout: float = 6.0) -> str:
    """One plain sentence about the first layer that failed, or ""."""
    host, port = _host_port(url)
    if not host:
        return ""
    # 1. the name
    t0 = time.time()
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return f"{host} does not resolve from this network ({e.strerror or e})"
    addrs = sorted({i[4][0] for i in infos})
    dns_ms = int((time.time() - t0) * 1000)
    # 2. the connection
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            tcp_ms = int((time.time() - t0) * 1000)
            # 3. the handshake (only where it applies)
            if port == 443 or url.startswith("https://"):
                # the engine's own trust (merged store + repaired chains), not
                # a bare default context — otherwise the probe reports a
                # certificate problem the download path no longer has
                from .trust import context as trust_context

                ctx = trust_context()
                try:
                    with ctx.wrap_socket(raw, server_hostname=host):
                        return ""
                except ssl.SSLCertVerificationError as e:
                    return (f"{host} answered, but its certificate did not verify"
                            f" ({e.verify_message or e.reason})")
                except (ssl.SSLError, OSError) as e:
                    return f"{host} answered, but the TLS handshake failed ({e})"
            return ""
    except socket.timeout:
        return (f"{host} ({addrs[0] if addrs else '?'}) accepted no connection within"
                f" {int(timeout)}s — the network or the host is blocking it")
    except OSError as e:
        return (f"{host} ({addrs[0] if addrs else '?'}) refused the connection"
                f" ({e.strerror or e})")


def note_for(url: str) -> str:
    """What the row shows under a failed download, or "" when all is well."""
    verdict = explain(url)
    if not verdict:
        return ""
    return f"diagnosis: {verdict}"
