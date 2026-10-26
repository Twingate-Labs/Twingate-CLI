"""Text files and output streams that behave the same on Windows as elsewhere.

Python opens files and redirected output with the system's legacy code page on Windows (cp1252 and friends), so a name in
Greek, Cyrillic, Chinese or an emoji can crash a command, sometimes after it has already changed something. Windows
PowerShell 5.1 also writes `>` redirection as UTF-16, and `Out-File -Encoding utf8` adds a byte order mark.
"""

from __future__ import annotations

import codecs
import os
import sys
from pathlib import Path


class TextFileError(Exception):
    """A file is not text this tool can read."""


# The 32-bit marks must come before the 16-bit ones: a UTF-32 little-endian mark starts with the UTF-16 one.
_BYTE_ORDER_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def decode_text(data: bytes) -> str:
    """Text from bytes: UTF-8 (with or without a byte order mark), or UTF-16 / UTF-32 when the file starts with their mark."""
    for mark, encoding in _BYTE_ORDER_MARKS:
        if data.startswith(mark):
            return data.decode(encoding)
    return data.decode("utf-8")


def read_text(path: "str | os.PathLike[str]") -> str:
    """Read a text file whatever editor or shell saved it. OSError (missing, unreadable) is passed on unchanged."""
    try:
        return decode_text(Path(path).read_bytes())
    except UnicodeDecodeError as exc:
        raise TextFileError(f"{path} is not valid UTF-8 text. Save it as UTF-8 and try again.") from exc


def ensure_utf8_output() -> None:
    """Write UTF-8 to stdout and stderr even when they are redirected and the system encoding is something narrower.

    Anything that still cannot be encoded is written as an escape sequence rather than raising.
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "").replace("_", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass


def check_writable(path: "str | os.PathLike[str]") -> None:
    """Raise OSError now if ``path`` cannot be written, so a command fails before it changes anything, not after.

    An existing file is left as it is; a file that did not exist is not left behind.
    """
    target = Path(path)
    existed = target.exists()
    with open(target, "a"):
        pass
    if not existed:
        target.unlink()
