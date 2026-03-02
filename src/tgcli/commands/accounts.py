"""Service account management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import accounts as t
from tgcli.queries import accounts as q

app = typer.Typer(help="Manage Twingate service accounts.")


@app.command("list")
def account_list() -> None:
    """List all service accounts."""
    run_paginated(get_client(), q.LIST_ACCOUNTS, "serviceAccounts", t.get_list_as_csv)


@app.command("show")
def account_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Service account ID."),
) -> None:
    """Show details for a specific service account."""
    run_query(get_client(), q.SHOW_ACCOUNT, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def account_create(
    name: str = typer.Option(..., "-n", "--name", help="Service account name."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated resource IDs."),
) -> None:
    """Create a new service account."""
    run_query(
        get_client(),
        q.CREATE_ACCOUNT,
        {"name": name, "resourceIds": split_ids(resourceids)},
        t.get_create_as_csv,
    )


@app.command("delete")
def account_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Service account ID."),
) -> None:
    """Delete a service account."""
    run_query(get_client(), q.DELETE_ACCOUNT, {"id": itemid}, t.get_delete_as_csv)


@app.command("addResources")
def account_add_resources(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Service account ID."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated resource IDs."),
) -> None:
    """Add resources to a service account."""
    run_query(
        get_client(),
        q.ADD_RESOURCES_TO_ACCOUNT,
        {"id": itemid, "resourceIDS": split_ids(resourceids)},
        t.get_add_remove_resources_as_csv,
    )


@app.command("removeResources")
def account_remove_resources(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Service account ID."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated resource IDs."),
) -> None:
    """Remove resources from a service account."""
    run_query(
        get_client(),
        q.REMOVE_RESOURCES_FROM_ACCOUNT,
        {"id": itemid, "resourceIDS": split_ids(resourceids)},
        t.get_add_remove_resources_as_csv,
    )
