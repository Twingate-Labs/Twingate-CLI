"""Validators for protocol-related fields (TCP/UDP policies and port ranges)."""

from __future__ import annotations

import json

import typer

VALID_POLICIES = ("ALLOW_ALL", "RESTRICTED")


def validate_protocol_policy(policy: str) -> str:
    """Validate and normalise a protocol policy string.

    Raises typer.BadParameter if the value is not a recognised policy.
    """
    normalised = policy.upper()
    if normalised not in VALID_POLICIES:
        raise typer.BadParameter(
            f"Invalid policy '{policy}'. Valid options: {', '.join(VALID_POLICIES)}"
        )
    return normalised


def validate_port_range(ranges: str) -> list[dict]:
    """Parse and validate a port-range string.

    Accepts a JSON list of [start, end] pairs, e.g. ``[[22,22],[443,446]]``.
    Separators ``;``, ``:`` and ``-`` are normalised to commas before parsing.

    Returns a list of ``{"start": int, "end": int}`` dicts.
    Raises typer.BadParameter on any validation failure.
    """
    processed = (
        ranges.replace(";", ",")
        .replace(":", ",")
        .replace("-", ",")
        .replace(",,", ",")
    )

    try:
        parsed = json.loads(processed)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid port range format: {exc}") from exc

    # Empty list is valid (means "no ports")
    if not parsed:
        return []

    if not isinstance(parsed, list):
        raise typer.BadParameter("Port ranges must be a JSON list.")

    final: list[dict] = []
    for item in parsed:
        if not isinstance(item, list) or len(item) != 2:
            raise typer.BadParameter(
                "Each port range must be a list of exactly two integers [start, end]."
            )
        start, end = int(item[0]), int(item[1])
        if not (1 <= start <= 65535) or not (1 <= end <= 65535):
            raise typer.BadParameter("Port numbers must be between 1 and 65535.")
        if start > end:
            raise typer.BadParameter(
                f"Start port ({start}) must be less than or equal to end port ({end})."
            )
        final.append({"start": start, "end": end})

    return final


def validate_range_with_policy(port_range: list[dict], policy: str) -> None:
    """Ensure that ALLOW_ALL policy is not combined with a non-empty port range.

    Raises typer.BadParameter if the combination is invalid.
    """
    if policy.upper() == "ALLOW_ALL" and port_range:
        raise typer.BadParameter(
            f"ALLOW_ALL policy is not compatible with a non-empty port range "
            f"{port_range}. Use RESTRICTED instead."
        )
