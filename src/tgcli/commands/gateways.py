"""Gateway commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import gateways as t
from tgcli.queries import gateways as q

app = typer.Typer(help="Manage Twingate Gateways.")


@app.command("list")
def gateway_list() -> None:
    """List all Gateways."""
    run_paginated(get_client(), q.LIST_GATEWAYS, "gateways", t.get_list_as_csv)


@app.command("show")
def gateway_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Gateway ID."),
) -> None:
    """Show details for a specific Gateway."""
    run_query(get_client(), q.SHOW_GATEWAY, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def gateway_create(
    networkid: str = typer.Option(..., "-n", "--networkid", help="Remote Network ID."),
    address: str = typer.Option(..., "-a", "--address", help="Gateway address, e.g. gateway.example.com:443."),
    x509caid: str = typer.Option(..., "-x", "--x509caid", help="X.509 Certificate Authority ID."),
    sshcaid: str = typer.Option("", "-s", "--sshcaid", help="SSH Certificate Authority ID (optional)."),
) -> None:
    """Create a new Gateway."""
    variables = {"address": address, "remoteNetworkId": networkid, "x509CAId": x509caid}
    if sshcaid:
        variables["sshCAId"] = sshcaid
    run_query(get_client(), q.CREATE_GATEWAY, variables, t.get_create_as_csv)


@app.command("update")
def gateway_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Gateway ID."),
    address: str = typer.Option("", "-a", "--address", help="New Gateway address."),
    networkid: str = typer.Option("", "-n", "--networkid", help="Move to this Remote Network ID."),
    x509caid: str = typer.Option("", "-x", "--x509caid", help="New X.509 Certificate Authority ID."),
    sshcaid: str = typer.Option("", "-s", "--sshcaid", help="New SSH Certificate Authority ID."),
) -> None:
    """Update a Gateway. Only the options you pass are changed."""
    # Unset options are omitted (never sent as null) so the API cannot read them as "clear this field".
    variables = {"id": itemid}
    for key, value in (("address", address), ("remoteNetworkId", networkid), ("x509CAId", x509caid), ("sshCAId", sshcaid)):
        if value:
            variables[key] = value
    if len(variables) == 1:
        typer.echo("Error: Provide at least one of --address, --networkid, --x509caid or --sshcaid.", err=True)
        raise typer.Exit(1)
    run_query(get_client(), q.UPDATE_GATEWAY, variables, t.get_update_as_csv)


@app.command("delete")
def gateway_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Gateway ID."),
) -> None:
    """Delete a Gateway. Cannot be undone."""
    run_query(get_client(), q.DELETE_GATEWAY, {"id": itemid}, t.get_delete_as_csv)
