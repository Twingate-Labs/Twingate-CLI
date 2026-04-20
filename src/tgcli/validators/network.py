"""Validators for remote-network fields."""

from __future__ import annotations

import typer

VALID_LOCATIONS = ("AWS", "AZURE", "GOOGLE_CLOUD", "ON_PREMISE", "OTHER")


def validate_rn_location(location: str) -> str:
    """Validate and normalise a remote-network location string.

    Raises typer.BadParameter if the value is not a recognised location.
    """
    normalised = location.upper()
    if normalised not in VALID_LOCATIONS:
        raise typer.BadParameter(
            f"Invalid location '{location}'. "
            f"Valid options: {', '.join(VALID_LOCATIONS)}"
        )
    return normalised
