"""Import command: create Remote Networks, groups (with members) and resources (with group access) from a file."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client
from tgcli.importer.apply import DRY_RUN_STATUS, apply_plan, write_count
from tgcli.importer.load import LoadError, load
from tgcli.importer.plan import BLOCKED, build_plan
from tgcli.importer.report import write_report
from tgcli.importer.state import fetch_state
from tgcli.textio import check_writable

MAX_LISTED = 200  # rows echoed to the terminal; the report always has all of them
KIND_ORDER = ("remote network", "group", "resource", "device")
FAILED = ("error", "blocked", "not-run")
RATE_LIMIT_PER_MINUTE = 20  # typical write limit (see Rate Limiting in the README); only used to warn about big imports


def _echo_row(row) -> None:
    extra = f"  [{len(row.warnings)} warning(s)]" if row.warnings else ""
    reason = row.error or row.detail
    typer.echo(f"  {row.status:<13}{row.kind:<15}{row.name}  ({reason}){extra}")


def _summary(rows: list) -> None:
    typer.echo("\nSummary")
    for kind in KIND_ORDER:
        mine = [r for r in rows if r.kind == kind]
        if not mine:
            continue
        counts: dict = {}
        for row in mine:
            counts[row.status] = counts.get(row.status, 0) + 1
        typer.echo(f"  {kind + 's':<17}" + ", ".join(f"{n} {status}" for status, n in sorted(counts.items())))
    warned = sum(len(r.warnings) for r in rows)
    if warned:
        typer.echo(f"  {warned} warning(s): something in the file was left out of a row (see the report).")


def _removals(rows: list) -> None:
    members = sum(len(r.remove_member_ids) for r in rows)
    access = sum(len(r.remove_access_ids) for r in rows)
    if members or access:
        typer.echo(f"--prune would REMOVE {members} group member(s) and {access} resource access grant(s) that the file does not list.")


def import_(
    path: Path = typer.Argument(..., help="A folder (a `tgcli backup`, or files named remote-networks / groups / resources / devices, .json or .csv) or one such file."),
    execute: bool = typer.Option(False, "--execute", help="Apply the changes. Without this flag, only a dry run is performed."),
    report: Optional[str] = typer.Option(None, "--report", help="Path to write the CSV report."),
    sync: bool = typer.Option(False, "--sync", help="Also change what already exists to match what the file states (resource settings, per-group access settings, a group's Security Policy). A blank CSV cell or a missing JSON key states nothing and is left alone; settings are only set, never cleared."),
    prune: bool = typer.Option(False, "--prune", help="With --sync: also REMOVE group members, resource access and tags that the file leaves out, for the groups and resources whose members, access or tags the file lists. Never deletes a group, resource or network."),
) -> None:
    """Create Remote Networks, groups with members, resources with group and service account access, and set device trust, from a file (dry run by default).

    Anything that already exists is left as it is and only added to (missing members, missing access) unless --sync is given; Synced Groups are never touched, and service accounts must already exist. Group members are matched by email, groups, service accounts and Remote Networks by exact name, resources by name, Remote Network and address together, and devices by serial number (devices.csv sets trust on devices that have already registered).
    """
    if prune and not sync:
        typer.echo("Error: --prune removes things, so it only works together with --sync. Nothing was changed.", err=True)
        raise typer.Exit(1)
    try:
        specs = load(path)
    except LoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    # Checked now, before anything is read from or written to the tenant, so a bad path cannot fail after the changes.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = Path(report) if report else Path(f"import_report_{stamp}.csv")
    try:
        check_writable(report_path)
    except OSError as exc:
        typer.echo(f"Error: cannot write the report to {report_path}: {exc.strerror}. Nothing was changed.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Read {', '.join(specs.files)}.")
    if specs.ignored:
        typer.echo(f"Not imported (not supported yet): {', '.join(specs.ignored)}.")

    client = get_client()
    try:
        state = fetch_state(client, specs, progress=lambda message: typer.echo(message, err=True), sync=sync)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    rows = build_plan(specs, state, sync, prune)

    if execute:
        typer.echo("\nApplying...")
        apply_plan(client, rows, progress=lambda row: None)
    else:
        for row in rows:
            row.status = DRY_RUN_STATUS[row.action]
        typer.echo("\n*** DRY RUN: nothing will be created or changed. Re-run with --execute to apply. ***")
        _removals(rows)
        writes = write_count(rows)
        if writes > RATE_LIMIT_PER_MINUTE:
            typer.echo(
                f"Applying would make {writes} write requests. The API typically allows about {RATE_LIMIT_PER_MINUTE} a minute, "
                "so the run will pause when it is rate limited; if it gives up part way, run the same command again to finish."
            )

    shown = [r for r in rows if r.status != "exists"]
    typer.echo("")
    for row in shown[:MAX_LISTED]:
        _echo_row(row)
    if len(shown) > MAX_LISTED:
        typer.echo(f"  ... and {len(shown) - MAX_LISTED} more (see the report)")
    _summary(rows)

    try:
        write_report(report_path, rows)
    except OSError as exc:
        typer.echo(f"\nError: the report could not be written to {report_path}: {exc.strerror}. The summary above is all there is.", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nReport written to: {report_path}")

    failed = [r for r in rows if r.status in FAILED]
    if failed:
        typer.echo(f"\n{len(failed)} row(s) {'failed or were blocked' if execute else 'are blocked and would not be imported'}.", err=True)
        raise typer.Exit(1)
