"""Shared helpers used by all command modules."""

from __future__ import annotations

import typer

from tgcli.client.client import TwingateClient
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.main import state
from tgcli.output.formatter import OutputFormatter
from tgcli.pagination import NestedLists, PaginationError, complete_nested_lists, strip_markers
from tgcli.resolve import Kind, ResolveError, resolve

from typing import Any, Callable
import pandas as pd

MAX_NESTED_WARNINGS = 5


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


def execute_query(client: TwingateClient, query: str, variables: dict | None) -> dict:
    """Execute a single GraphQL request, exiting with a friendly message on API/auth errors."""
    try:
        return client.execute(query, variables)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)


def complete_or_exit(client: TwingateClient, nodes: list[dict], nested: NestedLists) -> None:
    """Fill in nested lists the API cut off at 50 items, in place. Count mismatches only warn; failures exit.

    For a write's echo (``nested.at`` set) the change has already been made, so a failure here must not look
    like the write failed: it warns, drops the markers and leaves the first page the API returned.
    """
    try:
        problems = complete_nested_lists(client, nodes, nested)
    except (TwingateAuthError, TwingateAPIError, PaginationError) as exc:
        if nested.at:
            strip_markers(nodes, nested)
            typer.echo(
                f"Warning: the change was made, but the rest of the lists could not be read back ({exc}); "
                "the lists shown may be incomplete.",
                err=True,
            )
            return
        if isinstance(exc, TwingateAuthError):
            typer.echo(f"Authentication error: {exc}", err=True)
        elif isinstance(exc, TwingateAPIError):
            typer.echo(f"API error: {exc}", err=True)
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    for problem in problems[:MAX_NESTED_WARNINGS]:
        typer.echo(f"Warning: {problem}", err=True)
    if len(problems) > MAX_NESTED_WARNINGS:
        typer.echo(f"Warning: ... and {len(problems) - MAX_NESTED_WARNINGS} more", err=True)


def write_refused(result: dict | None) -> str | None:
    """The API's reason when a mutation in ``result`` answered ``ok: false``, otherwise None."""
    for value in ((result or {}).get("data") or {}).values():
        if isinstance(value, dict) and value.get("ok") is False:
            return str(value.get("error") or "the API refused the change")
    return None


def run_query(
    client: TwingateClient,
    query: str,
    variables: dict | None,
    transformer: Callable[..., pd.DataFrame],
    nested: NestedLists | None = None,
    exit_on_refusal: bool = True,
) -> dict:
    """Execute a single GraphQL query, print formatted output and return the response.

    ``nested`` completes nested lists on the object at ``data[nested.parent]`` (the API returns at most 50 per page).
    A write the API refuses (``ok: false``) is still printed, then the command exits 1 with the reason on stderr, so a
    script can tell a refused change from a made one. A caller that makes several writes passes ``exit_on_refusal=False``
    and decides for itself with :func:`write_refused`.
    """
    result = execute_query(client, query, variables)
    if nested is not None:
        node: Any = (result or {}).get("data")
        for key in nested.at or (nested.parent,):
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict):  # a missing object, or a write that reported ok: false, has nothing to complete
            complete_or_exit(client, [node], nested)
    OutputFormatter.print_output(result, state.output_format, transformer)
    refusal = write_refused(result)
    if refusal is not None and exit_on_refusal:
        typer.echo(f"Error: {refusal}", err=True)
        raise typer.Exit(1)
    return result


def fetch_paginated(
    client: TwingateClient,
    query: str,
    data_key: str,
    extra_vars: dict | None = None,
    filter_fn: Callable[[dict], bool] | None = None,
    nested: NestedLists | None = None,
) -> list[list[dict]]:
    """Execute a paginated list query and return all pages of edges.

    If provided, ``filter_fn`` is applied to each item's ``node`` dict and
    only nodes for which it returns True are kept. ``nested`` completes nested lists
    that did not fit in the first page (the API returns at most 50 items per page).
    """
    def make_vars(cursor: str) -> dict:
        v = {"cursor": cursor}
        if extra_vars:
            v.update(extra_vars)
        return v

    try:
        pages = client.paginate(query, make_vars, data_key)
        if filter_fn is not None:
            pages = [[edge for edge in page if filter_fn(edge["node"])] for page in pages]
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    if nested is not None:
        complete_or_exit(client, [edge["node"] for page in pages for edge in page if edge["node"]], nested)
    return pages


def run_paginated(
    client: TwingateClient,
    query: str,
    data_key: str,
    transformer: Callable[..., pd.DataFrame],
    extra_vars: dict | None = None,
    filter_fn: Callable[[dict], bool] | None = None,
    nested: NestedLists | None = None,
) -> None:
    """Execute a paginated list query and print formatted output.

    ``filter_fn`` is applied before output formatting, so it affects JSON,
    CSV, and DF output alike.
    """
    pages = fetch_paginated(client, query, data_key, extra_vars, filter_fn, nested)
    OutputFormatter.print_output(pages, state.output_format, transformer)


def split_values(occurrences: list[str] | None) -> list[str]:
    """Every value from an option that may be repeated and may also be comma-separated (-g A,B -g C)."""
    return [value for occurrence in occurrences or [] for value in split_ids(occurrence)]


def resolve_many_or_exit(client: TwingateClient, *requests: tuple[Kind, list[str]]) -> list[list[str]]:
    """IDs for several lists of values that may be IDs or exact names, one result per (kind, values) request.

    Every name that cannot be resolved, across all kinds, is reported in one go and the command exits 1, so nothing
    is written and the user can fix everything at once.
    """
    results: list[list[str]] = []
    problems: list[str] = []
    try:
        for kind, values in requests:
            try:
                results.append(resolve(client, kind, values))
            except ResolveError as exc:
                problems.extend(exc.problems)
                results.append([])
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except (TwingateAPIError, PaginationError) as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    if problems:
        for problem in problems:
            typer.echo(f"Error: {problem}", err=True)
        raise typer.Exit(1)
    return results


def resolve_or_exit(client: TwingateClient, kind: Kind, values: list[str]) -> list[str]:
    return resolve_many_or_exit(client, (kind, values))[0]


def split_ids(csv: str) -> list[str]:
    """Split a comma-separated ID string into a list, filtering blanks."""
    return [i.strip() for i in csv.split(",") if i.strip()]
