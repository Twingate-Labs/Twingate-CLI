"""Access request commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import access_requests as t
from tgcli.queries import access_requests as q

app = typer.Typer(help="Manage Twingate Access Requests.")

REQUEST_STATES = ("PENDING", "APPROVED", "REJECTED")


@app.command("list")
def access_request_list(
    status: Optional[list[str]] = typer.Option(
        None, "--status",
        help="Only requests in this status: PENDING, APPROVED or REJECTED. Repeat for several. Default: all statuses.",
    ),
    user_ids: Optional[list[str]] = typer.Option(None, "--user-id", help="Only requests from this user ID. Repeatable."),
    resource_ids: Optional[list[str]] = typer.Option(
        None, "--resource-id", help="Only requests for this resource ID. Repeatable."
    ),
) -> None:
    """List access requests, optionally filtered (filters combine with AND)."""
    # The API returns only PENDING requests when no status filter is sent, so default to every status.
    wanted = [s.upper() for s in status] if status else list(REQUEST_STATES)
    bad = [s for s in wanted if s not in REQUEST_STATES]
    if bad:
        raise typer.BadParameter(f"{bad}. Choose from: {', '.join(REQUEST_STATES)}", param_hint="--status")
    flt: dict = {"status": {"in": wanted}}
    if user_ids:
        flt["userId"] = {"in": user_ids}
    if resource_ids:
        flt["resourceId"] = {"in": resource_ids}
    run_paginated(get_client(), q.LIST_ACCESS_REQUESTS, "accessRequests", t.get_list_as_csv, {"filter": flt})


@app.command("show")
def access_request_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Access request ID."),
) -> None:
    """Show details for a specific access request."""
    run_query(get_client(), q.SHOW_ACCESS_REQUEST, {"itemID": itemid}, t.get_show_as_csv)


@app.command("approve")
def access_request_approve(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Access request ID."),
) -> None:
    """Approve an access request."""
    run_query(get_client(), q.APPROVE_ACCESS_REQUEST, {"itemID": itemid}, t.get_approve_as_csv)


@app.command("reject")
def access_request_reject(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Access request ID."),
) -> None:
    """Reject an access request."""
    run_query(get_client(), q.REJECT_ACCESS_REQUEST, {"itemID": itemid}, t.get_reject_as_csv)
