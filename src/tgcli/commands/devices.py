"""Device management commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import devices as t
from tgcli.queries import devices as q
from tgcli.validators.generic import parse_bool_string

app = typer.Typer(help="Manage Twingate devices.")


@app.command("list")
def device_list(
    fileofids: str = typer.Option("", "-l", "--fileofids", help="Path to file of known IDs (for diff)."),
    idsonly: bool = typer.Option(False, "-i", "--idsonly", help="Print IDs only."),
) -> None:
    """List all devices."""
    if fileofids and idsonly:
        typer.echo("Error: Cannot use --fileofids and --idsonly together.", err=True)
        raise typer.Exit(1)
    client = get_client()
    run_paginated(client, q.LIST_DEVICES, "devices", t.get_list_as_csv)


@app.command("show")
def device_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Show details for a specific device."""
    run_query(get_client(), q.SHOW_DEVICE, {"deviceID": itemid}, t.get_show_as_csv)


@app.command("updateTrust")
def device_update_trust(
    itemid: str = typer.Option("", "-i", "--itemid", help="Single device ID. Mandatory if not using --itemlist."),
    itemlist: str = typer.Option("", "-l", "--itemlist", help="Comma-separated device IDs. Mandatory if not using --itemid."),
    trust: str = typer.Option("True", "-t", "--trust", help="Trust value: True or False."),
) -> None:
    """Update the trust status of one or more devices."""
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


# --- Serial number sub-commands (snumber) ---

snumber_app = typer.Typer(help="Manage device serial number allowlist.")
app.add_typer(snumber_app, name="snumber")


@snumber_app.command("list")
def snumber_list() -> None:
    """List device serial numbers on the allowlist."""
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
