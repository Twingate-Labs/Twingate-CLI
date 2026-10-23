"""Validators for user-related fields."""

from __future__ import annotations

import typer

# What each role can do, as the Twingate API describes it. VALID_ROLES, the --role help text and the
# README all come from this one place, so a role added to the API only needs adding here.
ROLE_DESCRIPTIONS = {
    "ADMIN": "Full access to the Admin Console",
    "SUPPORT": "Read-only access to the Admin Console",
    "DEVOPS": "Full access to the Network tab, read-only access to the rest of the Admin Console",
    "INTERNET_SECURITY": "Full access to the Internet Security tab, read-only access to the rest of the Admin Console",
    "HELPDESK": "Read-only Admin Console access with MFA reset and device verification",
    "ACCESS_REVIEWER": "Access to Resource requests only",
    "BILLING": "Access to Billing functions only",
    "MEMBER": "No access to the Admin Console",
}
VALID_ROLES = tuple(ROLE_DESCRIPTIONS)
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
