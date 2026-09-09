"""Access request management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import access_requests as t
from tgcli.queries import access_requests as q

app = typer.Typer(help="Manage Access Requests.")


@app.command("list")
def access_request_list() -> None:
    """List all Access Requests."""
    run_paginated(get_client(), q.LIST_ACCESS_REQUESTS, "accessRequests", t.get_list_as_csv)


@app.command("show")
def access_request_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Access Request ID."),
) -> None:
    """Show details for a specific Access Request."""
    run_query(get_client(), q.SHOW_ACCESS_REQUEST, {"itemID": itemid}, t.get_show_as_csv)


@app.command("approve")
def access_request_approve(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Access Request ID."),
) -> None:
    """Approve an Access Request."""
    run_query(get_client(), q.APPROVE_ACCESS_REQUEST, {"id": itemid}, t.get_approve_as_csv)


@app.command("reject")
def access_request_reject(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Access Request ID."),
) -> None:
    """Reject an Access Request."""
    run_query(get_client(), q.REJECT_ACCESS_REQUEST, {"id": itemid}, t.get_reject_as_csv)
