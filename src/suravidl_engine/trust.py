"""TLS trust that matches the device's browser (v0.47.19).

A field report: a page played fine in Chrome on the phone, while suravidl
failed on the same media URL with a certificate error. That is the signature
of two different trust stores: Chrome (and Android's media stack) verify
against the **system** CA store, while the Python engine verifies against
**certifi's** bundle, which ships a subset of the world's CAs. A host chaining
to a CA that is in the system store but not in certifi — common with regional
and CDN-issued roots — therefore plays in the browser and fails in the app.

`install()` merges certifi's bundle with the platform store into one file and
points everything that can be pointed at it: SSL_CERT_FILE, REQUESTS_CA_BUNDLE,
CURL_CA_BUNDLE, and `certifi.where()` itself (urllib3 and yt-dlp ask certifi
directly, so the env vars alone would miss them).

Nothing here loosens verification: the merged file is the *union* of two trust
stores, never a bypass. The escape hatch for a genuinely bad certificate stays
where it was — the per-job "retry without certificate check".
"""
from __future__ import annotations

import os
import ssl
import tempfile
from pathlib import Path

# Where each platform keeps its PEM trust anchors.
_SYSTEM_DIRS = (
    "/system/etc/security/cacerts",      # Android (one hashed .0 file per CA)
    "/etc/ssl/certs",                    # Debian/Ubuntu
    "/etc/pki/tls/certs",                # Fedora/RHEL
    "/usr/local/share/certs",            # FreeBSD
)
_SYSTEM_FILES = (
    "/etc/ssl/cert.pem",                 # macOS, Alpine
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
)

_MARKER = "# suravidl merged trust"


def _certifi_path() -> Path | None:
    try:
        import certifi

        return Path(certifi.where())
    except Exception:  # noqa: BLE001
        return None


def bundle_path() -> Path:
    """Where the merged bundle lives (next to the app's own state)."""
    override = os.environ.get("SURAVIDL_CA_BUNDLE", "").strip()
    if override:
        return Path(override)
    home = Path(os.environ.get("SURAVIDL_HOME", "") or (Path.home() / ".suravidl"))
    return home / "ca-bundle.pem"


def _pem_blocks(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    blocks, current = [], []
    for line in text.splitlines(keepends=True):
        if line.startswith("-----BEGIN CERTIFICATE-----"):
            current = [line]
        elif current:
            current.append(line)
            if line.startswith("-----END CERTIFICATE-----"):
                blocks.append("".join(current))
                current = []
    return blocks


def system_bundles() -> list[Path]:
    """Every PEM store this platform offers, in a stable order."""
    found: list[Path] = []
    for name in _SYSTEM_FILES:
        p = Path(name)
        if p.is_file():
            found.append(p)
    for name in _SYSTEM_DIRS:
        d = Path(name)
        if not d.is_dir():
            continue
        try:
            found.extend(sorted(p for p in d.iterdir()
                                if p.is_file() and p.suffix in (".0", ".pem", ".crt")))
        except OSError:
            continue
    return found


def merged_bundle(target: Path | None = None) -> Path:
    """certifi ∪ platform store, written to `target`. Returns the path.

    Deduplicated by the PEM body, certifi first (its order is stable and
    already tested), then whatever the platform adds.
    """
    dest = target or bundle_path()
    seen: set[int] = set()
    out: list[str] = [_MARKER + " — certifi + this platform's CA store\n"]
    sources: list[Path] = []
    base = _certifi_path()          # one hook, so tests can swap the bundle
    if base is not None:
        sources.append(base)
    sources.extend(system_bundles())
    for src in sources:
        for block in _pem_blocks(src):
            key = hash(block.strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(block if block.endswith("\n") else block + "\n")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_text("".join(out), encoding="utf-8")
        os.replace(tmp, dest)
    except OSError:
        return dest if dest.is_file() else Path()
    return dest


def install() -> Path:
    """Merge, export, and make certifi point at the result. Idempotent."""
    dest = merged_bundle()
    if not dest or not dest.is_file():
        return Path()
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        os.environ[var] = str(dest)
    try:
        import certifi

        certifi.where = lambda: str(dest)  # urllib3 and yt-dlp ask this
    except Exception:  # noqa: BLE001 - absent certifi is not fatal
        pass
    return dest


def context() -> ssl.SSLContext:
    """A default context that trusts both stores (see net.ssl_context)."""
    ctx = ssl.create_default_context()
    for cafile in (bundle_path(), _certifi_path()):
        if cafile and cafile.is_file():
            try:
                ctx.load_verify_locations(cafile=str(cafile))
            except (ssl.SSLError, OSError):
                continue
    return ctx

