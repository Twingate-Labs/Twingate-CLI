"""Backup command: save the tenant's current groups, users, resources, connectors and remote networks."""

from __future__ import annotations

from pathlib import Path

import typer

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


def backup(
    output: str = typer.Option(
        "", "-o", "--output",
        help="Directory to create (must not exist). Default: ./twingate-backup-<tenant>-<UTC timestamp>.",
    ),
) -> None:
    """Back up the tenant's groups, users, resources, connectors and remote networks as JSON files.

    Read-only. Writes one JSON file per type plus a manifest with counts and checksums. Secrets (connector tokens, service account keys) are never included. The files contain user emails: on macOS and Linux they are created readable by you only; on Windows they inherit the folder's permissions, so choose a private folder.
    """
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
        typer.echo(f"  {entity.label:<16}{result.counts[entity.key]:>6}")
    if result.problems:
        typer.echo(
            f"\nWarning: {len(result.problems)} count mismatch(es), so this backup could not be fully verified. "
            "Data may have changed while it ran; run it again.",
            err=True,
        )
        for problem in result.problems[:MAX_PROBLEMS_SHOWN]:
            typer.echo(f"  - {problem}", err=True)
        if len(result.problems) > MAX_PROBLEMS_SHOWN:
            typer.echo(f"  ... and {len(result.problems) - MAX_PROBLEMS_SHOWN} more (see manifest.json)", err=True)
        raise typer.Exit(1)
    typer.echo("Verified: every count matches the API.")
