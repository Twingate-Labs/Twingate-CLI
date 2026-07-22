"""Generic validators shared across commands."""

from __future__ import annotations

import typer


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


VALID_ROUTING_MODES = ("THROUGH_TWINGATE", "BYPASS_TWINGATE")


def validate_routing_mode(value: str) -> str:
    """Validate and normalise a Resource routing mode string.

    Raises typer.BadParameter if the value is not a recognised routing mode.
    """
    normalised = value.upper()
    if normalised not in VALID_ROUTING_MODES:
        raise typer.BadParameter(
            f"Invalid routing mode '{value}'. Valid options: {', '.join(VALID_ROUTING_MODES)}"
        )
    return normalised
