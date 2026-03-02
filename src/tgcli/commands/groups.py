"""Group management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import groups as t
from tgcli.queries import groups as q

app = typer.Typer(help="Manage Twingate groups.")


@app.command("list")
def group_list() -> None:
    """List all groups."""
    run_paginated(get_client(), q.LIST_GROUPS, "groups", t.get_list_as_csv)


@app.command("show")
def group_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Group ID."),
) -> None:
    """Show details for a specific group."""
    run_query(get_client(), q.SHOW_GROUP, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def group_create(
    groupname: str = typer.Option(..., "-g", "--groupname", help="Group name."),
    userids: str = typer.Option("", "-u", "--userids", help="Comma-separated user IDs."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated resource IDs."),
    policyid: str = typer.Option("", "-p", "--securitypolicyid", help="Default security policy ID."),
) -> None:
    """Create a new group."""
    run_query(
        get_client(),
        q.CREATE_GROUP,
        {
            "groupName": groupname,
            "userIDS": split_ids(userids),
            "resourceIDS": split_ids(resourceids),
            "securityPolicyId": policyid or None,
        },
        t.get_create_as_csv,
    )


@app.command("delete")
def group_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Group ID."),
) -> None:
    """Delete a group."""
    run_query(get_client(), q.DELETE_GROUP, {"groupId": itemid}, t.get_delete_as_csv)


@app.command("addUsers")
def group_add_users(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    userids: str = typer.Option("", "-u", "--userids", help="Comma-separated user IDs."),
) -> None:
    """Add users to a group."""
    run_query(
        get_client(),
        q.ADD_USERS_TO_GROUP,
        {"groupID": groupid, "userIDS": split_ids(userids)},
        t.get_add_remove_users_as_csv,
    )


@app.command("removeUsers")
def group_remove_users(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    userids: str = typer.Option("", "-u", "--userids", help="Comma-separated user IDs."),
) -> None:
    """Remove users from a group."""
    run_query(
        get_client(),
        q.REMOVE_USERS_FROM_GROUP,
        {"groupID": groupid, "userIDS": split_ids(userids)},
        t.get_add_remove_users_as_csv,
    )


@app.command("addResources")
def group_add_resources(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated resource IDs."),
) -> None:
    """Add resources to a group."""
    run_query(
        get_client(),
        q.ADD_RESOURCES_TO_GROUP,
        {"groupID": groupid, "resourceIDS": split_ids(resourceids)},
        t.get_add_remove_resources_as_csv,
    )


@app.command("removeResources")
def group_remove_resources(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated resource IDs."),
) -> None:
    """Remove resources from a group."""
    run_query(
        get_client(),
        q.REMOVE_RESOURCES_FROM_GROUP,
        {"groupID": groupid, "resourceIDS": split_ids(resourceids)},
        t.get_add_remove_resources_as_csv,
    )


@app.command("assignPolicy")
def group_assign_policy(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Security policy ID."),
) -> None:
    """Assign a security policy to a group."""
    run_query(
        get_client(),
        q.ASSIGN_POLICY_TO_GROUP,
        {"groupID": groupid, "policyID": policyid},
        t.get_assign_policy_as_csv,
    )
