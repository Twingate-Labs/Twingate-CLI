"""Device management commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import fetch_paginated, get_client, run_paginated, run_query, split_ids
from tgcli.main import state
from tgcli.output.formatter import OutputFormatter
from tgcli.output.transformers import devices as t
from tgcli.output.transformers import generic
from tgcli.queries import devices as q
from tgcli.validators.generic import parse_bool_string

app = typer.Typer(help="Manage Twingate Devices.")


DEVICE_STATES = ("ACTIVE", "ARCHIVED", "BLOCKED")


def _build_device_filter(
    trusted: Optional[bool],
    states: Optional[list[str]],
    serial_number: str,
    user_ids: Optional[list[str]],
) -> Optional[dict]:
    """Build the API's DeviceFilterInput; returns None when no filter is requested."""
    flt: dict = {}
    if trusted is not None:
        flt["isTrusted"] = {"eq": trusted}
    if states:
        upper = [x.upper() for x in states]
        bad = [x for x in upper if x not in DEVICE_STATES]
        if bad:
            raise typer.BadParameter(f"{bad}. Choose from: {', '.join(DEVICE_STATES)}", param_hint="--state")
        flt["activeState"] = {"in": upper}
    if serial_number:
        flt["serialNumber"] = {"eq": serial_number}
    if user_ids:
        flt["userId"] = {"in": user_ids}
    return flt or None


@app.command("list")
def device_list(
    fileofids: str = typer.Option(
        "", "-l", "--fileofids",
        help="File of known device IDs (comma/newline separated). Prints IDs new to the tenant and IDs missing from it.",
    ),
    idsonly: bool = typer.Option(False, "-i", "--idsonly", help="Print IDs only."),
    trusted: Optional[bool] = typer.Option(None, "--trusted/--untrusted", help="Only trusted / only untrusted devices."),
    state_filter: Optional[list[str]] = typer.Option(
        None, "--state", help="Only devices in this state: ACTIVE, ARCHIVED or BLOCKED. Repeat for several."
    ),
    serial_number: str = typer.Option("", "--serial-number", help="Only the device with this exact serial number."),
    user_ids: Optional[list[str]] = typer.Option(
        None, "--user-id", help="Only devices belonging to this user ID. Repeat for several."
    ),
) -> None:
    """List devices, optionally filtered (filters are applied server-side and combine with AND)."""
    if fileofids and idsonly:
        typer.echo("Error: Cannot use --fileofids and --idsonly together.", err=True)
        raise typer.Exit(1)
    flt = _build_device_filter(trusted, state_filter, serial_number, user_ids)
    extra_vars = {"filter": flt} if flt else None
    client = get_client()

    if not (fileofids or idsonly):
        run_paginated(client, q.LIST_DEVICES, "devices", t.get_list_as_csv, extra_vars)
        return

    pages = fetch_paginated(client, q.LIST_DEVICES, "devices", extra_vars)
    ids = [edge["node"]["id"] for page in pages for edge in page if edge["node"]]
    if idsonly:
        OutputFormatter.print_output(ids, state.output_format, t.get_ids_as_df)
        return

    try:
        known = generic.read_ids_file(fileofids)
    except OSError as exc:
        typer.echo(f"Error: cannot read {fileofids}: {exc.strerror}", err=True)
        raise typer.Exit(1)
    diff = {"new": sorted(set(ids) - known), "missing": sorted(known - set(ids))}
    OutputFormatter.print_output(diff, state.output_format, t.get_id_diff_as_df)


@app.command("show")
def device_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Show details for a specific device."""
    run_query(get_client(), q.SHOW_DEVICE, {"deviceID": itemid}, t.get_show_as_csv)


@app.command("updateTrust")
def device_update_trust(
    itemid: str = typer.Option("", "-i", "--itemid", help="Single Device ID. Mandatory if not using --itemlist."),
    itemlist: str = typer.Option("", "-l", "--itemlist", help="Comma-separated Device IDs. Mandatory if not using --itemid."),
    trust: str = typer.Option("True", "-t", "--trust", help="Trust value: True or False."),
) -> None:
    """Update the trust status of one or more Devices."""
    if not itemid and not itemlist:
        typer.echo("Error: Provide -i (single ID) or -l (comma-separated IDs).", err=True)
        raise typer.Exit(1)
    if itemid and itemlist:
        typer.echo("Error: Cannot use both -i and -l together.", err=True)
        raise typer.Exit(1)

    trust_bool = parse_bool_string(trust)
    ids = split_ids(itemlist) if itemlist else [itemid]
    client = get_client()
    for device_id in ids:
        run_query(
            client,
            q.UPDATE_DEVICE_TRUST,
            {"deviceID": device_id, "isTrusted": trust_bool},
            t.get_update_as_csv,
        )


@app.command("block")
def device_block(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Block a device."""
    run_query(get_client(), q.BLOCK_DEVICE, {"deviceID": itemid}, t.get_block_as_csv)


@app.command("unblock")
def device_unblock(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Unblock a device."""
    run_query(get_client(), q.UNBLOCK_DEVICE, {"deviceID": itemid}, t.get_unblock_as_csv)


@app.command("archive")
def device_archive(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Archive a device."""
    run_query(get_client(), q.ARCHIVE_DEVICE, {"deviceID": itemid}, t.get_archive_as_csv)


@app.command("posture")
def device_posture(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Show posture check results for a specific device."""
    run_query(get_client(), q.POSTURE_DEVICE, {"deviceID": itemid}, t.get_posture_as_csv)


# --- Serial number sub-commands (snumber) ---

snumber_app = typer.Typer(help="Manage Device serial number allowlist.")
app.add_typer(snumber_app, name="snumber")


@snumber_app.command("list")
def snumber_list() -> None:
    """List Device serial numbers on the allowlist."""
    run_paginated(get_client(), q.LIST_SERIAL_NUMBERS, "serialNumbers", t.get_sn_list_as_csv)


@snumber_app.command("add")
def snumber_add(
    snumbers: str = typer.Option(..., "-n", "--snumbers", help="Comma-separated serial numbers."),
) -> None:
    """Add serial numbers to the allowlist."""
    sn_list = split_ids(snumbers)
    run_query(get_client(), q.ADD_SERIAL_NUMBERS, {"serialnums": sn_list}, t.get_add_serial_as_csv)


@snumber_app.command("remove")
def snumber_remove(
    snumbers: str = typer.Option(..., "-n", "--snumbers", help="Comma-separated serial numbers."),
) -> None:
    """Remove serial numbers from the allowlist."""
    sn_list = split_ids(snumbers)
    run_query(get_client(), q.DELETE_SERIAL_NUMBERS, {"serialnums": sn_list}, t.get_remove_serial_as_csv)
