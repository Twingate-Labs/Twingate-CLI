"""Gateway management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import gateways as t
from tgcli.queries import gateways as q

app = typer.Typer(help="Manage Gateways (Access Nodes).")


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
    address: str = typer.Option(..., "-a", "--address", help="Gateway address."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    sshcaid: str = typer.Option("", "--ssh-ca-id", help="SSH Certificate Authority ID."),
    x509caid: str = typer.Option("", "--x509-ca-id", help="X509 Certificate Authority ID."),
) -> None:
    """Create a new Gateway."""
    run_query(
        get_client(),
        q.CREATE_GATEWAY,
        {
            "address": address,
            "remoteNetworkId": networkid,
            "sshCAId": sshcaid or None,
            "x509CAId": x509caid or None,
        },
        t.get_create_as_csv,
    )


@app.command("delete")
def gateway_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Gateway ID."),
) -> None:
    """Delete a Gateway."""
    run_query(get_client(), q.DELETE_GATEWAY, {"id": itemid}, t.get_delete_as_csv)


@app.command("update")
def gateway_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Gateway ID."),
    address: str = typer.Option("", "-a", "--address", help="New Gateway address."),
    networkid: str = typer.Option("", "-r", "--networkid", help="New Remote Network ID."),
    sshcaid: str = typer.Option("", "--ssh-ca-id", help="New SSH Certificate Authority ID."),
    x509caid: str = typer.Option("", "--x509-ca-id", help="New X509 Certificate Authority ID."),
) -> None:
    """Update a Gateway."""
    variables: dict = {"id": itemid}
    if address:
        variables["address"] = address
    if networkid:
        variables["remoteNetworkId"] = networkid
    if sshcaid:
        variables["sshCAId"] = sshcaid
    if x509caid:
        variables["x509CAId"] = x509caid
    run_query(get_client(), q.UPDATE_GATEWAY, variables, t.get_update_as_csv)
