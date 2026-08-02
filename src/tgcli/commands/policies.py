"""Security policy management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import policies as t
from tgcli.queries import policies as q

app = typer.Typer(help="Manage Twingate Resource policies.")


@app.command("list")
def policy_list() -> None:
    """List all Resource policies."""
    run_paginated(get_client(), q.LIST_POLICIES, "securityPolicies", t.get_list_as_csv)


@app.command("show")
def policy_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource Policy ID."),
) -> None:
    """Show details for a specific Resource policy."""
    run_query(get_client(), q.SHOW_POLICY, {"itemID": itemid}, t.get_show_as_csv)


@app.command("addGroups")
def policy_add_groups(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Security Policy ID."),
    groupids: str = typer.Option(..., "-g", "--groupids", help="Comma-separated Group IDs to add."),
) -> None:
    """Add Groups to a Security Policy."""
    run_query(
        get_client(),
        q.UPDATE_POLICY_ADD_GROUPS,
        {"id": itemid, "addedGroupIds": split_ids(groupids)},
        t.get_update_as_csv,
    )


@app.command("removeGroups")
def policy_remove_groups(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Security Policy ID."),
    groupids: str = typer.Option(..., "-g", "--groupids", help="Comma-separated Group IDs to remove."),
) -> None:
    """Remove Groups from a Security Policy."""
    run_query(
        get_client(),
        q.UPDATE_POLICY_REMOVE_GROUPS,
        {"id": itemid, "removedGroupIds": split_ids(groupids)},
        t.get_update_as_csv,
    )
