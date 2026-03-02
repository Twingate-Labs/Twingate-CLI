"""Validators for user-related fields."""

from __future__ import annotations

import typer

VALID_ROLES = ("ADMIN", "DEVOPS", "SUPPORT", "MEMBER")
VALID_STATES = ("DISABLED", "ACTIVE")


def validate_user_role(role: str) -> str:
    """Validate and normalise a user role string.

    Raises typer.BadParameter if the value is not a recognised role.
    """
    normalised = role.upper()
    if normalised not in VALID_ROLES:
        raise typer.BadParameter(
            f"Invalid role '{role}'. Valid options: {', '.join(VALID_ROLES)}"
        )
    return normalised


def validate_user_state(state: str) -> str:
    """Validate and normalise a user state string.

    Raises typer.BadParameter if the value is not a recognised state.
    """
    normalised = state.upper()
    if normalised not in VALID_STATES:
        raise typer.BadParameter(
            f"Invalid state '{state}'. Valid options: {', '.join(VALID_STATES)}"
        )
    return normalised
