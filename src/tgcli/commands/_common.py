"""Shared helpers used by all command modules."""

from __future__ import annotations

import typer

from tgcli.client.client import TwingateClient
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.main import state
from tgcli.output.formatter import OutputFormatter

from typing import Any, Callable
import pandas as pd


def require_session() -> str:
    """Return the active session name or exit with a user-friendly error."""
    session = state.session
    if not session:
        typer.echo(
            "Error: No session name provided. "
            "Use the global -s/--session flag or run 'tgcli auth login' first.",
            err=True,
        )
        raise typer.Exit(1)
    return session


def get_client() -> TwingateClient:
    """Return a TwingateClient for the current session."""
    return TwingateClient(require_session())


def run_query(
    client: TwingateClient,
    query: str,
    variables: dict | None,
    transformer: Callable[..., pd.DataFrame],
) -> None:
    """Execute a single GraphQL query and print formatted output."""
    try:
        result = client.execute(query, variables)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    OutputFormatter.print_output(result, state.output_format, transformer)


def run_paginated(
    client: TwingateClient,
    query: str,
    data_key: str,
    transformer: Callable[..., pd.DataFrame],
    extra_vars: dict | None = None,
) -> None:
    """Execute a paginated list query and print formatted output."""
    def make_vars(cursor: str) -> dict:
        v = {"cursor": cursor}
        if extra_vars:
            v.update(extra_vars)
        return v

    try:
        pages = client.paginate(query, make_vars, data_key)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    OutputFormatter.print_output(pages, state.output_format, transformer)


def split_ids(csv: str) -> list[str]:
    """Split a comma-separated ID string into a list, filtering blanks."""
    return [i.strip() for i in csv.split(",") if i.strip()]
