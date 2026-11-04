"""Certificate and public key text for tests. The certificate is only base64 of some bytes: the importer fingerprints bytes, it does not parse X.509."""

from __future__ import annotations

import base64
import hashlib


def der(seed: str) -> bytes:
    return hashlib.sha256(f"der-{seed}".encode()).digest() * 4


def pem(seed: str) -> str:
    body = base64.b64encode(der(seed)).decode()
    lines = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
    return f"-----BEGIN CERTIFICATE-----\n{lines}\n-----END CERTIFICATE-----\n"


def x509_fingerprint(seed: str) -> str:
    """What a tenant reports for the certificate ``pem(seed)``: SHA-256 of its DER bytes, as lowercase hex."""
    return hashlib.sha256(der(seed)).hexdigest()


def blob(seed: str) -> bytes:
    return b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + hashlib.sha256(f"key-{seed}".encode()).digest()


def ssh_key(seed: str, comment: str = "ca@example") -> str:
    return f"ssh-ed25519 {base64.b64encode(blob(seed)).decode()} {comment}\n"


def ssh_fingerprint(seed: str) -> str:
    """What `ssh-keygen -l` prints for the key ``ssh_key(seed)``."""
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob(seed)).digest()).decode().rstrip("=")


def api_fingerprint(kind: str, content: str) -> str:
    """The fingerprint the fake API reports for what it is sent."""
    from tgcli.importer.cafiles import read_one
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as folder:
        path = pathlib.Path(folder) / "ca"
        path.write_text(content)
        found, problem = read_one(path)
    assert found, problem
    if kind == "x509":
        return sorted(f for f in found.fingerprints if len(f) == 64 and all(c in "0123456789abcdef" for c in f))[0]
    return "SHA256:" + next(f for f in found.fingerprints if len(f) == 43)
