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


@app.command("update")
def policy_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource Policy ID."),
    add_groups: str = typer.Option("", "-a", "--add-groups", help="Comma-separated Group IDs to assign to the policy."),
    remove_groups: str = typer.Option("", "-r", "--remove-groups", help="Comma-separated Group IDs to unassign from the policy."),
    set_groups: str = typer.Option(
        "", "--set-groups",
        help="Comma-separated Group IDs that REPLACE the policy's whole group assignment. Cannot be combined with --add-groups/--remove-groups.",
    ),
) -> None:
    """Change which Groups a Resource policy is assigned to."""
    added, removed, replaced = split_ids(add_groups), split_ids(remove_groups), split_ids(set_groups)
    if not (added or removed or replaced):
        typer.echo("Error: Provide at least one of --add-groups, --remove-groups or --set-groups.", err=True)
        raise typer.Exit(1)
    if replaced and (added or removed):
        typer.echo("Error: --set-groups cannot be combined with --add-groups or --remove-groups.", err=True)
        raise typer.Exit(1)
    # Omit unset arguments rather than sending null, so the API never reads null as "clear".
    variables: dict = {"id": itemid}
    for key, ids in (("groupIds", replaced), ("addedGroupIds", added), ("removedGroupIds", removed)):
        if ids:
            variables[key] = ids
    run_query(get_client(), q.UPDATE_POLICY_GROUPS, variables, t.get_update_as_csv)
