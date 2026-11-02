"""Remove command: delete the resources, groups and Remote Networks a file names, after showing the list and asking to be told the count."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from tgcli.backup import MAX_PROBLEMS_SHOWN, BackupError, _tenant_of, collect, write_backup
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands import _common
from tgcli.commands._common import get_client, require_session
from tgcli.commands.importing import MAX_LISTED
from tgcli.removal import BLOCKED, ERROR, KINDS, NOT_RUN, REMOVE, REMOVED, SKIP, LoadError, READ_KEYS, apply_plan, build_plan, counts, kind_of, load_targets
from tgcli.textio import check_writable

REPORT_COLUMNS = ("kind", "name", "status", "detail", "reason", "error", "id", "source")
FAILED = (ERROR, NOT_RUN)


def _echo_row(row) -> None:
    text = row.error or row.reason or row.detail
    typer.echo(f"  {row.status:<13}{row.kind:<15}{row.name}  ({text})")


def _write_report(path: Path, rows: list) -> None:
    import csv

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(REPORT_COLUMNS)
        for row in rows:
            writer.writerow([row.kind, row.name, row.status, row.detail, row.reason, row.error, row.id, row.source])


def _total(rows: list) -> str:
    done = counts(rows)
    return ", ".join(f"{done[k]} {k}{'' if done[k] == 1 else 's'}" for k in KINDS if k in done)


def remove(
    path: Path = typer.Argument(..., help="A file naming what to remove: CSV or JSON with a kind (resource / group / network) and an id and/or a name per line, or a plain list of ids or names with --kind."),
    kind: Optional[str] = typer.Option(None, "--kind", help="resource, group or network: the kind of every line that does not give its own (a plain list, or a CSV or JSON without a kind)."),
    execute: bool = typer.Option(False, "--execute", help="Remove them, after showing the list and asking you to type how many. Without this flag only the list is shown."),
    no_snapshot: bool = typer.Option(False, "--no-snapshot", help="With --execute: do not write the safety snapshot of the tenant first."),
    snapshot_dir: Optional[Path] = typer.Option(None, "--snapshot-dir", help="Where the safety snapshot goes (must not exist). Default: ./twingate-preremove-<tenant>-<UTC timestamp>."),
    report: Optional[str] = typer.Option(None, "--report", help="Path to write the CSV report."),
) -> None:
    """Remove the resources, groups and Remote Networks a file names (shows the list; nothing is removed without --execute and a typed confirmation).

    Each line must match exactly one object, by id or by exact name (a resource can be narrowed by network and address columns); a
    line that matches several, or whose id has another name, blocks the whole run. Synced Groups are never removed. A Remote Network
    is only removed when all of its resources are in the file too, and never while it has Connectors or Gateways. A line that matches
    nothing is reported as not found and skipped, so a run that stopped half way can be run again. With --execute the list is shown
    with what depends on each object, and you must type the number of objects to confirm; there is no --yes, and with no terminal
    to ask on the command refuses. A snapshot of the tenant is written first: `tgcli restore <snapshot> --execute` puts the
    removed objects back (resources and groups come back with new IDs).
    """
    default_kind = None
    if kind:
        default_kind = kind_of(kind)
        if default_kind not in KINDS:
            typer.echo(f"Error: --kind {kind!r} should be resource, group or network. Nothing was changed.", err=True)
            raise typer.Exit(1)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = Path(report) if report else Path(f"remove_report_{stamp}.csv")
    try:
        check_writable(report_path)
    except OSError as exc:
        typer.echo(f"Error: cannot write the report to {report_path}: {exc.strerror}. Nothing was changed.", err=True)
        raise typer.Exit(1)
    try:
        targets = load_targets(path, default_kind)
    except LoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    client = get_client()
    tenant = _tenant_of(client)
    snapshot_path = snapshot_dir or Path(f"twingate-preremove-{tenant}-{stamp}")
    if execute and not no_snapshot and snapshot_path.exists():
        typer.echo(f"Error: {snapshot_path} already exists; choose another --snapshot-dir. Nothing was changed.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Read {len(targets)} line(s) from {path.name}.")
    try:
        # What is read here is the plan and, with --execute, also the snapshot written before anything is removed.
        collected = collect(client, progress=lambda message: typer.echo(message, err=True), keys=READ_KEYS)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except (TwingateAPIError, BackupError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if collected.problems:
        typer.echo(f"{'Error' if execute else 'Warning'}: the tenant could not be read completely ({len(collected.problems)} problem(s)), so the list may be wrong:", err=True)
        for problem in collected.problems[:MAX_PROBLEMS_SHOWN]:
            typer.echo(f"  - {problem}", err=True)
        if execute:
            typer.echo("Nothing was removed. Run it again (the tenant may have been changing while it was read).", err=True)
            raise typer.Exit(1)

    rows = build_plan(targets, collected.items)
    for row in rows:
        row.status = {REMOVE: "to-remove", SKIP: "not-found", BLOCKED: "blocked"}[row.action]
    typer.echo(f"\n{'*** DRY RUN: nothing will be removed. Re-run with --execute to remove them. ***' if not execute else 'What will be removed:'}\n")
    for row in rows[:MAX_LISTED]:
        _echo_row(row)
    if len(rows) > MAX_LISTED:
        typer.echo(f"  ... and {len(rows) - MAX_LISTED} more (see the report)")
    blocked = [r for r in rows if r.action == BLOCKED]
    skipped = [r for r in rows if r.action == SKIP]
    typer.echo(f"\nSummary: {_total(rows) or 'nothing'} to remove; {len(skipped)} not found; {len(blocked)} blocked.")

    if not execute:
        _finish(report_path, rows)
        if blocked:
            typer.echo(f"\n{len(blocked)} line(s) are blocked, so with --execute nothing would be removed until they are fixed.", err=True)
            raise typer.Exit(1)
        return

    if blocked:
        _finish(report_path, rows)
        typer.echo(f"\n{len(blocked)} line(s) are blocked. Nothing was removed: fix the file (or take those lines out) and run it again.", err=True)
        raise typer.Exit(1)
    total = sum(counts(rows).values())
    if not total:
        _finish(report_path, rows)
        typer.echo("\nNothing to remove.")
        return
    if not _common._at_a_terminal():
        _finish(report_path, rows)
        typer.echo("\nError: refusing to remove anything without a typed confirmation: there is no terminal to ask on, and remove has no --yes. Nothing was removed.", err=True)
        raise typer.Exit(1)
    answer = typer.prompt(f"\nThis will permanently remove {_total(rows)} from {tenant}. Type {total} to confirm", default="", show_default=False, err=True)
    if answer.strip() != str(total):
        _finish(report_path, rows)
        typer.echo("Nothing was removed.", err=True)
        raise typer.Exit(1)

    if not no_snapshot:
        try:
            result = write_backup(collected, snapshot_path, session=require_session(), tenant=tenant)
        except BackupError as exc:
            typer.echo(f"Error: {exc} Nothing was removed.", err=True)
            raise typer.Exit(1)
        typer.echo(f"Safety snapshot of the tenant as it was read: {result.path}")
        typer.echo(f"  To put the removed objects back: tgcli restore {result.path} --execute")
    typer.echo("\nRemoving...")
    apply_plan(client, rows, progress=lambda row: None)
    typer.echo("")
    for row in rows[:MAX_LISTED]:
        _echo_row(row)
    removed = [r for r in rows if r.status == REMOVED]
    failed = [r for r in rows if r.status in FAILED]
    typer.echo(f"\nRemoved {_total(removed) or 'nothing'}; {len(failed)} failed.")
    _finish(report_path, rows)
    if failed:
        typer.echo(f"\n{len(failed)} row(s) failed or were not attempted. Run the same command again to finish.", err=True)
        raise typer.Exit(1)


def _finish(report_path: Path, rows: list) -> None:
    try:
        _write_report(report_path, rows)
    except OSError as exc:
        typer.echo(f"\nError: the report could not be written to {report_path}: {exc.strerror}. The summary above is all there is.", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nReport written to: {report_path}")
