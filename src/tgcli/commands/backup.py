"""Backup command: save the tenant's current objects (groups, users, resources, devices, policies and more)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from tgcli.backup_diff import DiffError, compare, load_backup, render, to_dict
from tgcli.backup import (
    MAX_PROBLEMS_SHOWN,
    BackupError,
    _tenant_of,
    collect,
    default_output_path,
    write_backup,
)
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client, require_session
from tgcli.queries.backup import ENTITIES


app = typer.Typer(invoke_without_command=True)


@app.callback()
def backup(
    ctx: typer.Context,
    output: str = typer.Option(
        "", "-o", "--output",
        help="Directory to create (must not exist). Default: ./twingate-backup-<tenant>-<UTC timestamp>.",
    ),
) -> None:
    """Back up the tenant's groups, users, resources, devices, policies and more as JSON files.

    Read-only. Writes one JSON file per type (groups, users, resources, connectors, remote networks, devices, service accounts with their keys' metadata, security policies, DNS filtering profiles, gateways, certificate authorities) plus a manifest with counts and checksums. Secrets (connector tokens, service account keys) are never included. The files contain user emails and device details: on macOS and Linux they are created readable by you only; on Windows they inherit the folder's permissions, so choose a private folder.

    To compare two backups, run `tgcli backup diff <first> <second>`.
    """
    if ctx.invoked_subcommand is not None:
        return
    client = get_client()
    out_dir = Path(output) if output else default_output_path(client)
    try:
        collected = collect(client, progress=lambda message: typer.echo(message, err=True))
        result = write_backup(collected, out_dir, session=require_session(), tenant=_tenant_of(client))
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    except BackupError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Backup written to {result.path}")
    for entity in ENTITIES:
        if entity.key in result.counts:
            typer.echo(f"  {entity.label:<26}{result.counts[entity.key]:>6}")
        else:
            typer.echo(f"  {entity.label:<26}{'NOT READ':>8}")
    if result.problems:
        typer.echo(
            f"\nWarning: {len(result.problems)} problem(s), so this backup could not be fully verified. "
            "Data may have changed while it ran, or a type could not be read; run it again.",
            err=True,
        )
        for problem in result.problems[:MAX_PROBLEMS_SHOWN]:
            typer.echo(f"  - {problem}", err=True)
        if len(result.problems) > MAX_PROBLEMS_SHOWN:
            typer.echo(f"  ... and {len(result.problems) - MAX_PROBLEMS_SHOWN} more (see manifest.json)", err=True)
        raise typer.Exit(1)
    typer.echo("Verified: every count matches the API.")


@app.command("diff")
def diff(
    first: Path = typer.Argument(..., help="The older backup folder."),
    second: Path = typer.Argument(..., help="The newer backup folder."),
    json_output: bool = typer.Option(False, "--json", help="Print the comparison as JSON instead of text."),
    include_volatile: bool = typer.Option(
        False, "--include-volatile",
        help="Also compare fields that change on their own: updatedAt, a connector's last heartbeat, a device's last login.",
    ),
    exit_code: bool = typer.Option(False, "--exit-code", help="Exit 1 when the backups differ (0 when they match)."),
) -> None:
    """Show what was added, removed or changed between two backups of the same tenant.

    Works on the folders `tgcli backup` wrote, offline: no session and no API calls. Objects are matched by ID, and lists
    inside them (a group's members, a resource's access, tags) are matched the same way, so a reordering is not a
    change. Fields that change on their own are left out unless you pass --include-volatile.

    Exit codes: 0 when the comparison ran (or, with --exit-code, when the backups match); 1 with --exit-code when they
    differ; 2 when the folders cannot be compared.
    """
    try:
        result = compare(load_backup(first), load_backup(second), include_volatile=include_volatile)
    except DiffError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2)
    for warning in result.warnings:
        typer.echo(f"Warning: {warning}", err=True)
    if json_output:
        typer.echo(json.dumps(to_dict(result), indent=2, ensure_ascii=False))
    else:
        typer.echo(render(result))
    if exit_code and result.differences:
        raise typer.Exit(1)
