"""Generic validators shared across commands."""

from __future__ import annotations


def parse_bool_string(value: str) -> bool:
    """Parse a string as a boolean value.

    Accepts 'true'/'false' (case-insensitive).
    Raises ValueError for unrecognised strings.
    """
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    raise ValueError(
        f"Invalid boolean value '{value}'. Expected 'true' or 'false'."
    )
