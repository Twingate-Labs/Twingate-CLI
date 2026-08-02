"""Webhook management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import webhooks as t
from tgcli.queries import webhooks as q

app = typer.Typer(help="Manage Webhooks.")


@app.command("list")
def webhook_list() -> None:
    """List all Webhooks."""
    run_paginated(get_client(), q.LIST_WEBHOOKS, "webhooks", t.get_list_as_csv)


@app.command("show")
def webhook_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Webhook ID."),
) -> None:
    """Show details for a Webhook."""
    run_query(get_client(), q.SHOW_WEBHOOK, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def webhook_create(
    name: str = typer.Option(..., "-n", "--name", help="Webhook name."),
    url: str = typer.Option(..., "-u", "--url", help="Webhook URL."),
) -> None:
    """Create a new Webhook."""
    run_query(get_client(), q.CREATE_WEBHOOK, {"name": name, "url": url}, t.get_create_as_csv)


@app.command("delete")
def webhook_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Webhook ID."),
) -> None:
    """Delete a Webhook."""
    run_query(get_client(), q.DELETE_WEBHOOK, {"id": itemid}, t.get_delete_as_csv)


@app.command("update")
def webhook_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Webhook ID."),
    name: str = typer.Option("", "-n", "--name", help="New Webhook name."),
    url: str = typer.Option("", "-u", "--url", help="New Webhook URL."),
) -> None:
    """Update a Webhook."""
    variables: dict = {"id": itemid}
    if name:
        variables["name"] = name
    if url:
        variables["url"] = url
    run_query(get_client(), q.UPDATE_WEBHOOK, variables, t.get_update_as_csv)
