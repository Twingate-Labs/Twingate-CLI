"""Import command: create Remote Networks, groups (with members) and resources (with group access) from a file."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client
from tgcli.importer.apply import DRY_RUN_STATUS, apply_plan, write_count
from tgcli.importer.cafiles import read_ca_files
from tgcli.importer.load import LoadError, load
from tgcli.importer.notices import not_carried_over
from tgcli.importer.plan import BLOCKED, build_plan
from tgcli.importer.report import write_report
from tgcli.importer.state import fetch_state
from tgcli.textio import check_writable

MAX_LISTED = 200  # rows echoed to the terminal; the report always has all of them
KIND_ORDER = (
    "remote network", "group", "service account", "certificate authority", "gateway", "connector", "resource", "dns profile", "device", "user",
)
PLURALS = {"certificate authority": "certificate authorities"}
FAILED = ("error", "blocked", "not-run")
RATE_LIMIT_PER_MINUTE = 20  # typical write limit (see Rate Limiting in the README); only used to warn about big imports


def _echo_row(row) -> None:
    extra = f"  [{len(row.warnings)} warning(s)]" if row.warnings else ""
    reason = row.error or row.detail
    typer.echo(f"  {row.status:<13}{row.kind:<15}{row.name}  ({reason}){extra}")


def _summary(rows: list, source: str = "file") -> None:
    typer.echo("\nSummary")
    for kind in KIND_ORDER:
        mine = [r for r in rows if r.kind == kind]
        if not mine:
            continue
        counts: dict = {}
        for row in mine:
            counts[row.status] = counts.get(row.status, 0) + 1
        typer.echo(f"  {PLURALS.get(kind, kind + 's'):<24}" + ", ".join(f"{n} {status}" for status, n in sorted(counts.items())))
    warned = sum(len(r.warnings) for r in rows)
    if warned:
        typer.echo(f"  {warned} warning(s): something in the {source} was left out of a row (see the report).")


def _not_carried(notices: list) -> None:
    if not notices:
        return
    typer.echo("\nNot carried over (see the report for the reasons)")
    for notice in notices:
        typer.echo(f"  {notice.what}: {notice.detail}")


def _removals(rows: list) -> None:
    members = sum(len(r.remove_member_ids) for r in rows)
    access = sum(len(r.remove_access_ids) for r in rows)
    if members or access:
        typer.echo(f"--prune would REMOVE {members} group member(s) and {access} resource access grant(s) that the file does not list.")


def import_(
    path: Path = typer.Argument(..., help="A folder (a `tgcli backup`, or files named remote-networks / groups / service-accounts / certificate-authorities / gateways / resources / dns-profiles / devices, .json or .csv) or one such file."),
    execute: bool = typer.Option(False, "--execute", help="Apply the changes. Without this flag, only a dry run is performed."),
    report: Optional[str] = typer.Option(None, "--report", help="Path to write the CSV report."),
    sync: bool = typer.Option(False, "--sync", help="Also change what already exists to match what the file states (resource settings, per-group access settings, a group's Security Policy). A blank CSV cell or a missing JSON key states nothing and is left alone; settings are only set, never cleared."),
    prune: bool = typer.Option(False, "--prune", help="With --sync: also REMOVE group members, resource access, approver groups and tags that the file leaves out, for the groups and resources whose members, access, approvers or tags the file lists. Never deletes a group, resource or network."),
    ca_files: Optional[Path] = typer.Option(None, "--ca-files", help="A certificate or SSH public key file, or a folder of them, to make the backup's certificate authorities from. A file is only used for the CA whose fingerprint it has; a file holding a private key is refused."),
) -> None:
    """Create Remote Networks, groups with members, service accounts, certificate authorities, Gateways, resources (network, SSH, web app and Kubernetes) with group and service account access and approver groups, and DNS profiles, and set device trust, from a file (dry run by default).

    Anything that already exists is left as it is and only added to (missing members, missing access, missing approvers) unless --sync is given; Synced Groups are never touched. Group members are matched by email, groups, service accounts, DNS profiles and Remote Networks by exact name, resources by name, Remote Network and address together, Gateways by address and Remote Network, certificate authorities by fingerprint, and devices by serial number (devices.csv sets trust on devices that have already registered). An SSH, web app or Kubernetes resource is served through a Gateway, which has no name: the file gives its address, and the Gateway is made first when a gateways file lists it. Service accounts are made without keys. A certificate authority is made only from a file given with --ca-files whose own fingerprint is the one in the backup. What a backup holds that cannot be carried to another tenant (users, Connectors, Security Policy rules, device registrations, keys) is listed at the end and in the report.
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
    certificates = None
    if ca_files is not None:
        if not ca_files.exists():
            typer.echo(f"Error: --ca-files {ca_files} does not exist. Nothing was changed.", err=True)
            raise typer.Exit(1)
        certificates = read_ca_files(ca_files)
        typer.echo(f"Read {len(certificates.files)} certificate file(s) from {ca_files}.")

    client = get_client()
    try:
        state = fetch_state(client, specs, progress=lambda message: typer.echo(message, err=True), sync=sync)
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    rows = build_plan(specs, state, sync, prune, certificates)
    notices = not_carried_over(specs, rows, certificates)

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
    _not_carried(notices)

    try:
        write_report(report_path, rows, notices)
    except OSError as exc:
        typer.echo(f"\nError: the report could not be written to {report_path}: {exc.strerror}. The summary above is all there is.", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nReport written to: {report_path}")

    failed = [r for r in rows if r.status in FAILED]
    if failed:
        typer.echo(f"\n{len(failed)} row(s) {'failed or were blocked' if execute else 'are blocked and would not be imported'}.", err=True)
        raise typer.Exit(1)
