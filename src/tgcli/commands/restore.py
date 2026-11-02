"""Restore command: put a tenant back the way one of its own backups says it was (dry run by default)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

from tgcli.backup import MAX_PROBLEMS_SHOWN, BackupError, _tenant_of, collect, write_backup
from tgcli.backup_diff import DiffError, load_backup
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client, require_session
from tgcli.commands.importing import FAILED, MAX_LISTED, RATE_LIMIT_PER_MINUTE, _echo_row, _removals, _summary
from tgcli.importer.apply import DRY_RUN_STATUS, apply_plan, write_count
from tgcli.importer.plan import CREATE, SKIP, UPDATE
from tgcli.importer.report import write_report
from tgcli.restore import READ_KEYS, build_plan
from tgcli.textio import check_writable

OLD_BACKUP_DAYS = 30
ONLY_KINDS = {"network": "remote network", "group": "group", "resource": "resource"}


def _age(created: str) -> Optional[int]:
    try:
        when = datetime.fromisoformat(created)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - (when if when.tzinfo else when.replace(tzinfo=timezone.utc))).days


def _select(rows: list, selectors: List[str]) -> None:
    """Leave only the rows ``--only`` names to be applied (the others become skipped). Exits when a selector is not understood or matches nothing."""
    chosen: list = []
    for selector in selectors:
        kind, _, value = selector.partition(":")
        if kind not in ONLY_KINDS or not value:
            typer.echo(f"Error: --only {selector!r} should look like group:<name or id>, resource:<name or id> or network:<name or id>. Nothing was changed.", err=True)
            raise typer.Exit(1)
        hits = [r for r in rows if r.kind == ONLY_KINDS[kind] and value in (r.name, r.backup_id, r.existing_id)]
        if not hits:
            typer.echo(f"Error: --only {selector!r} matches nothing in the backup. Nothing was changed.", err=True)
            raise typer.Exit(1)
        chosen.extend(hits)
    keep = {id(r) for r in chosen}
    for row in rows:
        if id(row) not in keep and row.action in (CREATE, UPDATE):
            row.action, row.detail = SKIP, "not selected with --only"


def restore(
    path: Path = typer.Argument(..., help="A backup folder written by `tgcli backup` for THIS tenant."),
    execute: bool = typer.Option(False, "--execute", help="Apply the changes. Without this flag, only a dry run is performed."),
    prune: bool = typer.Option(False, "--prune", help="Also REMOVE group members, resource access and tags that the backup does not have, from the groups and resources it does have. Never deletes an object."),
    only: Optional[List[str]] = typer.Option(None, "--only", help="Restore only this: group:<name or id>, resource:<name or id> or network:<name or id>. Repeat for several."),
    no_snapshot: bool = typer.Option(False, "--no-snapshot", help="With --execute: do not write the safety snapshot of the tenant first."),
    snapshot_dir: Optional[Path] = typer.Option(None, "--snapshot-dir", help="Where the safety snapshot goes (must not exist). Default: ./twingate-prerestore-<tenant>-<UTC timestamp>."),
    report: Optional[str] = typer.Option(None, "--report", help="Path to write the CSV report."),
    force_tenant: bool = typer.Option(False, "--force-tenant", help="Restore even though the backup is of a tenant with a different name than this session's."),
) -> None:
    """Put remote networks, groups and resources back the way a backup of this tenant had them (dry run by default).

    Repairs damage to the SAME tenant (to copy one tenant into another, use `tgcli import`). Objects are matched by ID, so a
    renamed group is renamed back and a moved or edited resource is put back; an object that was deleted is created again,
    and its access is given back to the groups. Nothing is ever deleted: what was created after the backup is left alone, and
    --prune only takes members, access and tags that the backup does not have out of objects it does have. Synced Groups
    are never touched. With --execute, a snapshot of the tenant as it is now is written first, so that a restore can be undone
    by restoring from it. A type the backup does not hold, or that restore does not cover yet (users, connectors, devices,
    service accounts, policies, DNS profiles, gateways, certificate authorities), is named in the output.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = Path(report) if report else Path(f"restore_report_{stamp}.csv")
    try:
        check_writable(report_path)
    except OSError as exc:
        typer.echo(f"Error: cannot write the report to {report_path}: {exc.strerror}. Nothing was changed.", err=True)
        raise typer.Exit(1)
    try:
        backup = load_backup(path)
    except DiffError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    for warning in backup.warnings:
        typer.echo(f"Warning: {warning}", err=True)
    if backup.changed_files and execute:
        typer.echo("Error: the backup does not match its own checksums, so it will not be restored from. Nothing was changed.", err=True)
        raise typer.Exit(1)

    client = get_client()
    tenant = _tenant_of(client)
    if backup.tenant != tenant and not force_tenant:
        typer.echo(
            f"Error: this backup is of tenant '{backup.tenant}' but the session is '{tenant}'. IDs differ between tenants, so a restore "
            "would match nothing; use `tgcli import` to copy one tenant into another (or --force-tenant if the tenant was renamed). Nothing was changed.",
            err=True,
        )
        raise typer.Exit(1)
    age = _age(backup.created)
    when = f"made {backup.created}" + (f" ({age} days ago)" if age is not None else "")
    typer.echo(f"Restoring from the backup of {backup.tenant} {when}.")
    if age is not None and age > OLD_BACKUP_DAYS:
        typer.echo(f"Warning: this backup is {age} days old; everything that changed since then is in the plan below.", err=True)

    snapshot_path = snapshot_dir or Path(f"twingate-prerestore-{tenant}-{stamp}")
    if execute and not no_snapshot and snapshot_path.exists():
        typer.echo(f"Error: {snapshot_path} already exists; choose another --snapshot-dir. Nothing was changed.", err=True)
        raise typer.Exit(1)
    try:
        # A restore that is going to write reads everything, because what it reads is also the snapshot it writes first.
        collected = collect(client, progress=lambda message: typer.echo(message, err=True), keys=None if execute else READ_KEYS)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except (TwingateAPIError, BackupError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    if collected.problems:
        label = "Error" if execute else "Warning"
        typer.echo(f"{label}: the tenant could not be read completely ({len(collected.problems)} problem(s)), so the plan may be wrong:", err=True)
        for problem in collected.problems[:MAX_PROBLEMS_SHOWN]:
            typer.echo(f"  - {problem}", err=True)
        if execute:
            typer.echo("Nothing was changed. Run it again (the tenant may have been changing while it was read).", err=True)
            raise typer.Exit(1)

    if execute and not no_snapshot:
        try:
            result = write_backup(collected, snapshot_path, session=require_session(), tenant=tenant)
        except BackupError as exc:
            typer.echo(f"Error: {exc} Nothing was changed.", err=True)
            raise typer.Exit(1)
        typer.echo(f"Safety snapshot of the tenant as it is now: {result.path}")
        typer.echo(f"  To undo this restore: tgcli restore {result.path} --execute")

    plan = build_plan(backup, collected.items, prune=prune)
    rows = plan.rows
    if only:
        _select(rows, only)

    if execute:
        typer.echo("\nApplying...")
        apply_plan(client, rows, progress=lambda row: None)
    else:
        for row in rows:
            row.status = DRY_RUN_STATUS[row.action]
        typer.echo("\n*** DRY RUN: nothing will be changed. Re-run with --execute to apply. ***")
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
    if not shown:
        typer.echo("Nothing differs from the backup in what restore covers.")
    _summary(rows, source="backup")
    after = [f"{n} {label}" for label, n in plan.created_after.items() if n]
    if after:
        typer.echo(f"Created since the backup, and left alone (restore never deletes): {', '.join(after)}.")
    for sentence in plan.left_alone:
        typer.echo(f"Not touched: {sentence}.")
    if plan.not_compared:
        typer.echo(f"Not compared: {'; '.join(plan.not_compared)}.")

    try:
        write_report(report_path, rows)
    except OSError as exc:
        typer.echo(f"\nError: the report could not be written to {report_path}: {exc.strerror}. The summary above is all there is.", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nReport written to: {report_path}")

    failed = [r for r in rows if r.status in FAILED]
    if failed:
        typer.echo(f"\n{len(failed)} row(s) {'failed or were blocked' if execute else 'are blocked and would not be restored'}.", err=True)
        raise typer.Exit(1)
