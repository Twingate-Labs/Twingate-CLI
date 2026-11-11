"""Certificate authority files supplied to `tgcli import --ca-files`, and the fingerprints they have.

A backup never holds the certificate or public key of a Certificate Authority, only its name and fingerprint, so another
tenant's copy can only be made from the file itself. A file is only ever used for the CA whose fingerprint it has: the
fingerprint is worked out here from the file's own bytes, so a wrong or look-alike file is never sent to the API.

Only public material is read. A file that holds a private key is refused outright, and its contents are never kept.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tgcli.textio import TextFileError, read_text

X509, SSH = "x509", "ssh"
MAX_BYTES = 256 * 1024  # a certificate or public key is a few KB; anything bigger is not one
_CERTIFICATE = re.compile(r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", re.S)
_KEY_TYPE = re.compile(r"^(ssh-[a-z0-9]+|ecdsa-sha2-\S+|sk-\S+)\s+([A-Za-z0-9+/=]+)", re.M)


@dataclass
class CaFile:
    path: str  # as given, for messages
    kind: str  # "x509" or "ssh"
    content: str  # exactly what the API is sent
    fingerprints: frozenset  # every form the fingerprint may be written in, normalised


@dataclass
class CaFiles:
    files: list = field(default_factory=list)
    problems: list = field(default_factory=list)  # files that were looked at but cannot be used, with the reason

    def match(self, fingerprint: Optional[str], kind: Optional[str] = None) -> list:
        wanted = normalize(fingerprint)
        if not wanted:
            return []
        return [f for f in self.files if wanted in f.fingerprints and (kind is None or f.kind == kind)]


def normalize(fingerprint: Optional[str]) -> str:
    """A fingerprint in one comparable form, whichever way it is written (``SHA256:...``, ``AB:CD:...``, plain hex or base64).

    Hex is made lowercase and loses its colons; base64 keeps its case but loses its padding and prefix.
    """
    text = (fingerprint or "").strip()
    text = re.sub(r"^(sha-?\d+|md5)\s*[:=]\s*", "", text, flags=re.I)
    if re.fullmatch(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2})+", text) or re.fullmatch(r"[0-9A-Fa-f]{32,}", text):
        return text.replace(":", "").lower()
    return text.rstrip("=")


def _hex(digest: bytes) -> str:
    return digest.hex()


def _b64(digest: bytes) -> str:
    return base64.b64encode(digest).decode().rstrip("=")


def _x509_fingerprints(der: bytes) -> frozenset:
    return frozenset({_hex(hashlib.sha256(der).digest()), _hex(hashlib.sha1(der).digest()), _b64(hashlib.sha256(der).digest())})  # noqa: S324


def _ssh_fingerprints(blob: bytes) -> frozenset:
    return frozenset({_b64(hashlib.sha256(blob).digest()), _hex(hashlib.sha256(blob).digest()), _hex(hashlib.md5(blob).digest())})  # noqa: S324


def read_one(path: Path) -> tuple:
    """(CaFile or None, problem or None) for one file."""
    try:
        if path.stat().st_size > MAX_BYTES:
            return None, "is too big to be a certificate or a public key"
        # A file saved on Windows carries CRLF line endings; the content sent
        # to the API must read the same whatever platform saved the file.
        text = read_text(path).replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, TextFileError) as exc:
        return None, f"cannot be read: {exc}"
    if "PRIVATE KEY" in text:
        return None, "holds a private key, which is never read or sent anywhere; give the certificate or the public key"
    cert = _CERTIFICATE.search(text)
    if cert:
        try:
            der = base64.b64decode("".join(cert.group(1).split()), validate=True)
        except (binascii.Error, ValueError):
            return None, "has a certificate that is not valid PEM"
        return CaFile(str(path), X509, text.strip(), _x509_fingerprints(der)), None
    key = _KEY_TYPE.search(text)
    if key:
        try:
            blob = base64.b64decode(key.group(2), validate=True)
        except (binascii.Error, ValueError):
            return None, "has an SSH public key that is not valid base64"
        return CaFile(str(path), SSH, text.strip(), _ssh_fingerprints(blob)), None
    return None, "is neither a PEM certificate nor an SSH public key"


def read_ca_files(path: Path) -> CaFiles:
    """The usable files at ``path`` (one file, or every file directly inside a folder)."""
    found = CaFiles()
    if path.is_dir():
        candidates = sorted(p for p in path.iterdir() if p.is_file() and not p.name.startswith("."))
    else:
        candidates = [path]
    for candidate in candidates:
        ca_file, problem = read_one(candidate)
        if ca_file:
            found.files.append(ca_file)
        elif path.is_file() or problem.startswith("holds a private key"):
            found.problems.append(f"{candidate.name} {problem}")
        # a folder may hold other things beside the certificates; those are not worth a line
    return found
