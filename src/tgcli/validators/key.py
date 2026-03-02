"""Validators for service-account key fields."""

from __future__ import annotations

import typer

_MIN_EXPIRATION = 0
_MAX_EXPIRATION = 365


def validate_key_expiration(expiration: int) -> int:
    """Validate a key expiration value (0–365 days).

    Raises typer.BadParameter if the value is out of range.
    """
    if expiration < _MIN_EXPIRATION or expiration > _MAX_EXPIRATION:
        raise typer.BadParameter(
            f"Expiration must be between {_MIN_EXPIRATION} and {_MAX_EXPIRATION} days."
        )
    return expiration
