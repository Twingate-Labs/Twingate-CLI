"""Connector management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import connectors as t
from tgcli.queries import connectors as q
from tgcli.validators.generic import parse_bool_string

app = typer.Typer(help="Manage Twingate Connectors.")


@app.command("list")
def connector_list() -> None:
    """List all Connectors."""
    run_paginated(get_client(), q.LIST_CONNECTORS, "Connectors", t.get_list_as_csv)


@app.command("show")
def connector_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Connector ID."),
) -> None:
    """Show details for a specific Connector."""
    run_query(get_client(), q.SHOW_CONNECTOR, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def connector_create(
    networkid: str = typer.Option(..., "-i", "--networkid", help="Remote Network ID."),
    connname: str = typer.Option(..., "-c", "--connname", help="Connector name."),
    sendnotifications: str = typer.Option("true", "-s", "--sendnotifications", help="Enable status notifications: true or false."),
) -> None:
    """Create a new connector."""
    notifications = parse_bool_string(sendnotifications)
    run_query(
        get_client(),
        q.CREATE_CONNECTOR,
        {"connName": connname, "remoteNetworkID": networkid, "statNotifications": notifications},
        t.get_create_as_csv,
    )


@app.command("rename")
def connector_rename(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Connector ID."),
    itemname: str = typer.Option(..., "-n", "--itemname", help="New Connector name."),
) -> None:
    """Rename a connector."""
    run_query(get_client(), q.RENAME_CONNECTOR, {"id": itemid, "name": itemname}, t.get_update_as_csv)


@app.command("generateTokens")
def connector_generate_tokens(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Connector ID."),
) -> None:
    """Generate new access/refresh tokens for a Connector."""
    run_query(get_client(), q.GENERATE_CONNECTOR_TOKENS, {"id": itemid}, t.get_gen_tokens_as_csv)


@app.command("updateNotifications")
def connector_update_notifications(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Connector ID."),
    sendnotifications: str = typer.Option("true", "-s", "--sendnotifications", help="Enable notifications: true or false."),
) -> None:
    """Enable or disable status email notifications for a Connector."""
    notifications = parse_bool_string(sendnotifications)
    run_query(
        get_client(),
        q.UPDATE_CONNECTOR_NOTIFICATIONS,
        {"id": itemid, "hasStatusNotificationsEnabled": notifications},
        t.get_update_as_csv,
    )
