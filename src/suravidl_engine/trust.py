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


def extra_path() -> Path:
    """CAs fetched by the AIA repair — kept apart from the merge's own output."""
    return bundle_path().with_name("extra-cas.pem")


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
    if extra_path().is_file():
        sources.append(extra_path())     # repaired chains survive the re-merge
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



# --- AIA repair: what browsers do that OpenSSL does not ---------------------
#
# cdnserver23.cloudmp4.to answers with its LEAF certificate only. OpenSSL says
# "unable to verify the first certificate" (21); Chrome fetches the issuer
# named in the certificate's Authority Information Access extension and plays.
# This is that repair, done once per host and cached in the bundle.

_AIA_OID = bytes.fromhex("06082B06010505070101")     # 1.3.6.1.5.5.7.1.1
_CA_ISSUERS_OID = bytes.fromhex("06082B06010505073002")  # 1.3.6.1.5.5.7.48.2


def _tlv(data: bytes, i: int) -> tuple[int, bytes, int]:
    """One DER element: (tag, value, next index)."""
    tag = data[i]
    i += 1
    ln = data[i]
    i += 1
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(data[i:i + n], "big")
        i += n
    return tag, data[i:i + ln], i + ln


def _children(body: bytes) -> list[tuple[int, bytes]]:
    out, i = [], 0
    while i < len(body):
        tag, val, i = _tlv(body, i)
        out.append((tag, val))
    return out


def aia_issuer_urls(leaf_der: bytes) -> list[str]:
    """The CA Issuers URLs inside a certificate (empty when it names none)."""
    try:
        tag, cert, _ = _tlv(leaf_der, 0)
        if tag != 0x30:
            return []
        tag, tbs, _ = _tlv(cert, 0)
        if tag != 0x30:
            return []
        parts = _children(tbs)
        # [3] EXPLICIT extensions is the last element of the TBSCertificate
        ext_wrapper = next((v for t, v in parts if t == 0xA3), None)
        if ext_wrapper is None:
            return []
        tag, ext_seq, _ = _tlv(ext_wrapper, 0)
        if tag != 0x30:
            return []
        urls: list[str] = []
        for tag, ext in _children(ext_seq):
            if tag != 0x30:
                continue
            fields = _children(ext)
            if not fields or fields[0][1] != _AIA_OID[2:]:
                continue
            value = next((v for t, v in fields if t == 0x04), None)
            if value is None:
                continue
            tag, access_seq, _ = _tlv(value, 0)
            if tag != 0x30:
                continue
            for tag, desc in _children(access_seq):
                if tag != 0x30:
                    continue
                d = _children(desc)
                if len(d) < 2 or d[0][1] != _CA_ISSUERS_OID[2:]:
                    continue
                uri_tag, uri = d[1]
                if uri_tag == 0x86:
                    urls.append(uri.decode("ascii", "replace"))
        return urls
    except (IndexError, ValueError):
        return []


_CA_BASIC_OID = bytes.fromhex("0603551D13")      # 2.5.29.19 basicConstraints


def is_ca_certificate(der: bytes) -> bool:
    """basicConstraints CA:TRUE. Only a CA may become a trust anchor: a
    server must not be able to get its own end-entity certificate trusted by
    naming it in an AIA extension."""
    try:
        tag, cert, _ = _tlv(der, 0)
        if tag != 0x30:
            return False
        tag, tbs, _ = _tlv(cert, 0)
        parts = _children(tbs)
        ext_wrapper = next((v for t, v in parts if t == 0xA3), None)
        if ext_wrapper is None:
            return False
        tag, ext_seq, _ = _tlv(ext_wrapper, 0)
        for tag, ext in _children(ext_seq):
            if tag != 0x30:
                continue
            fields = _children(ext)
            if not fields or fields[0][1] != _CA_BASIC_OID[2:]:
                continue
            value = next((v for t, v in fields if t == 0x04), None)
            if value is None:
                return False
            tag, seq, _ = _tlv(value, 0)
            for tag2, val2 in _children(seq):
                if tag2 == 0x01:               # the cA boolean
                    return bool(val2 and val2[0])
            return False
        return False
    except (IndexError, ValueError):
        return False


def _pem_to_der(pem: str) -> bytes | None:
    import base64

    try:
        body = pem.split("-----BEGIN CERTIFICATE-----")[1]
        body = body.split("-----END CERTIFICATE-----")[0]
        return base64.b64decode("".join(body.split()))
    except (IndexError, ValueError):
        return None


def _peer_leaf(host: str, port: int = 443) -> bytes | None:
    """The certificate the server actually sends, without verifying it."""
    import socket

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=15) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                return tls.getpeercert(binary_form=True)
    except OSError:
        return None


def _as_pem(blob: bytes) -> str | None:
    """DER certificate -> PEM. PEM passes through; PKCS#7 is skipped."""
    text = blob.decode("latin-1", "ignore")
    if "-----BEGIN CERTIFICATE-----" in text:
        return text if text.endswith("\n") else text + "\n"
    if not blob or blob[0] != 0x30:
        return None
    try:
        return ssl.DER_cert_to_PEM_cert(blob)
    except (ValueError, ssl.SSLError):
        return None


def repair_chain(url_or_host: str) -> bool:
    """Fetch the issuer a server forgot to send, add it, refresh the bundle.

    Returns True when at least one new CA was added (callers retry once).
    """
    import urllib.request

    host = url_or_host
    if "://" in host:
        from urllib.parse import urlsplit

        host = urlsplit(host).hostname or ""
    if not host:
        return False
    leaf = _peer_leaf(host)
    if not leaf:
        return False
    urls = aia_issuer_urls(leaf)
    if not urls:
        return False
    dest = extra_path()
    existing = ""
    try:
        existing = dest.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        existing = ""
    added = 0
    for url in urls[:3]:
        if not url.lower().startswith(("http://", "https://")):
            continue
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                blob = r.read(200_000)
        except Exception:  # noqa: BLE001 - a dead AIA must not break the job
            continue
        pem = _as_pem(blob)
        if not pem or pem.strip() in existing:
            continue
        der = _pem_to_der(pem)
        if der is None or not is_ca_certificate(der):
            continue        # an end-entity cert may never become a trust anchor
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "a", encoding="utf-8") as fh:
                fh.write(pem if pem.startswith("\n") else "\n" + pem)
        except OSError:
            return False
        existing += pem
        added += 1
    if not added:
        return False
    install()
    return True
