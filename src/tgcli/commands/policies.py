"""Security policy management commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import policies as t
from tgcli.pagination import NestedLists, PaginationError, fetch_connection
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
    run_query(
        get_client(), q.SHOW_POLICY, {"itemID": itemid}, t.get_show_as_csv,
        nested=NestedLists("securityPolicy", q.POLICY_CONTINUATIONS),
    )


def _current_group_ids(client, policy_id: str) -> list[str]:
    """Every group currently in the policy (all pages), or exit 1 if it cannot be read."""
    try:
        edges, _, found = fetch_connection(client, q.POLICY_GROUP_IDS, {"id": policy_id}, ["securityPolicy", "groups"])
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except (TwingateAPIError, PaginationError) as exc:
        typer.echo(f"Error: could not read the policy's groups: {exc}", err=True)
        raise typer.Exit(1)
    if not found:
        typer.echo(f"Error: no policy with ID '{policy_id}'.", err=True)
        raise typer.Exit(1)
    return [edge["node"]["id"] for edge in edges]


@app.command("update")
def policy_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource Policy ID."),
    add_groups: str = typer.Option("", "-a", "--add-groups", help="Comma-separated Group IDs to assign to the policy."),
    remove_groups: str = typer.Option("", "-r", "--remove-groups", help="Comma-separated Group IDs to unassign from the policy."),
    set_groups: Optional[str] = typer.Option(
        None, "--set-groups",
        help="Comma-separated Group IDs that REPLACE the policy's whole group assignment. Cannot be combined with --add-groups/--remove-groups.",
    ),
    clear_groups: bool = typer.Option(
        False, "--clear-groups",
        help="Remove EVERY group from the policy. The only way to leave a policy with no groups; cannot be combined with the other group options.",
    ),
) -> None:
    """Change which Groups a Resource policy is assigned to."""
    added, removed, replaced = split_ids(add_groups), split_ids(remove_groups), split_ids(set_groups or "")
    if clear_groups and (added or removed or set_groups is not None):
        typer.echo("Error: --clear-groups removes every group, so it cannot be combined with --add-groups, --remove-groups or --set-groups.", err=True)
        raise typer.Exit(1)
    if set_groups is not None and not replaced:
        typer.echo(
            "Error: --set-groups needs at least one Group ID. To remove every group from the policy, use --clear-groups.",
            err=True,
        )
        raise typer.Exit(1)
    if not (added or removed or replaced or clear_groups):
        typer.echo("Error: Provide at least one of --add-groups, --remove-groups, --set-groups or --clear-groups.", err=True)
        raise typer.Exit(1)
    if replaced and (added or removed):
        typer.echo("Error: --set-groups cannot be combined with --add-groups or --remove-groups.", err=True)
        raise typer.Exit(1)
    client = get_client()
    if clear_groups:
        # The API ignores `groupIds: []` (it answers ok and removes nothing), so clearing means removing every current group.
        removed = _current_group_ids(client, itemid)
        if not removed:
            typer.echo("The policy has no groups, so there is nothing to remove.", err=True)
            return
    # Omit unset arguments rather than sending null, so the API never reads null as "clear".
    variables: dict = {"id": itemid}
    for key, ids in (("groupIds", replaced), ("addedGroupIds", added), ("removedGroupIds", removed)):
        if ids:
            variables[key] = ids
    run_query(
        client, q.UPDATE_POLICY_GROUPS, variables, t.get_update_as_csv,
        nested=NestedLists("securityPolicy", q.POLICY_CONTINUATIONS, at=("securityPolicyUpdate", "entity")),
    )
