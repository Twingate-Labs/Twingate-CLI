"""Group management commands."""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from typing import Optional

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import groups as t
from tgcli.queries import groups as q

app = typer.Typer(help="Manage Twingate Groups.")


@app.command("list")
def group_list() -> None:
    """List all Groups."""
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
    userids: str = typer.Option("", "-u", "--userids", help="Comma-separated User IDs."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated Resource IDs."),
    policyid: str = typer.Option("", "-p", "--securitypolicyid", help="Default Resource Policy ID."),
) -> None:
    """Create a new Group."""
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
    """Delete a Group."""
    run_query(get_client(), q.DELETE_GROUP, {"groupId": itemid}, t.get_delete_as_csv)


@app.command("addUsers")
def group_add_users(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    userids: str = typer.Option("", "-u", "--userids", help="Comma-separated User IDs."),
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
    userids: str = typer.Option("", "-u", "--userids", help="Comma-separated User IDs."),
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
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated Resource IDs."),
) -> None:
    """Add Resources to a Group."""
    run_query(
        get_client(),
        q.ADD_RESOURCES_TO_GROUP,
        {"groupID": groupid, "resourceIDS": split_ids(resourceids)},
        t.get_add_remove_resources_as_csv,
    )


@app.command("removeResources")
def group_remove_resources(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    resourceids: str = typer.Option("", "-r", "--resourceids", help="Comma-separated Resource IDs."),
) -> None:
    """Remove Resources from a Group."""
    run_query(
        get_client(),
        q.REMOVE_RESOURCES_FROM_GROUP,
        {"groupID": groupid, "resourceIDS": split_ids(resourceids)},
        t.get_add_remove_resources_as_csv,
    )


@app.command("rename")
def group_rename(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    name: str = typer.Option(..., "-n", "--name", help="New Group name."),
) -> None:
    """Rename a Group."""
    run_query(
        get_client(),
        q.RENAME_GROUP,
        {"groupID": groupid, "name": name},
        t.get_rename_as_csv,
    )


@app.command("setState")
def group_set_state(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    active: str = typer.Option(..., "-a", "--active", help="Active state: true or false."),
) -> None:
    """Activate or deactivate a Group."""
    from tgcli.validators.generic import parse_bool_string
    active_bool = parse_bool_string(active)
    run_query(
        get_client(),
        q.UPDATE_GROUP_STATE,
        {"groupID": groupid, "isActive": active_bool},
        t.get_update_state_as_csv,
    )


@app.command("setUsers")
def group_set_users(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    userids: str = typer.Option(..., "-u", "--userids", help="Comma-separated User IDs (replaces all)."),
) -> None:
    """Replace all users in a Group (full-replace)."""
    run_query(
        get_client(),
        q.SET_GROUP_USERS,
        {"groupID": groupid, "userIDS": split_ids(userids)},
        t.get_set_users_as_csv,
    )


@app.command("setResources")
def group_set_resources(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    resourceids: str = typer.Option(..., "-r", "--resourceids", help="Comma-separated Resource IDs (replaces all)."),
) -> None:
    """Replace all resources in a Group (full-replace)."""
    run_query(
        get_client(),
        q.SET_GROUP_RESOURCES,
        {"groupID": groupid, "resourceIDS": split_ids(resourceids)},
        t.get_set_resources_as_csv,
    )


@app.command("migrate")
def group_migrate(
    execute: bool = typer.Option(False, "--execute", help="Apply changes. Without this flag, only a dry run is performed."),
    name_suffix: str = typer.Option(" (Manual)", "--name-suffix", help="Suffix appended to new Manual Group names."),
    no_copy_policy: bool = typer.Option(False, "--no-copy-security-policy", help="Don't copy the source group's Security Policy."),
    report: Optional[str] = typer.Option(None, "--report", help="Path to write the CSV report."),
) -> None:
    """Migrate all active Synced Groups to new Manual Groups (dry run by default)."""
    BATCH_SIZE = 200
    client = get_client()

    def paginate_nested(query, variables, path):
        items = []
        after = None
        while True:
            vars_ = {**variables, "after": after}
            result = client.execute(query, vars_)
            node = result
            for key in path:
                node = node[key]
            items.extend(edge["node"] for edge in node["edges"])
            if not node["pageInfo"]["hasNextPage"]:
                break
            after = node["pageInfo"]["endCursor"]
        return items

    def chunked(seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    typer.echo("Fetching all groups...")
    pages = client.paginate(q.LIST_GROUPS, lambda c: {"cursor": c}, "groups")
    all_groups = [item["node"] for page in pages for item in page]

    synced_groups = [g for g in all_groups if g["type"] == "SYNCED" and g["isActive"]]
    inactive_synced = [g for g in all_groups if g["type"] == "SYNCED" and not g["isActive"]]
    existing_manual = {g["name"]: g for g in all_groups if g["type"] == "MANUAL"}

    typer.echo(
        f"Found {len(all_groups)} total groups: "
        f"{len(synced_groups)} active synced, "
        f"{len(inactive_synced)} inactive synced (will be skipped)."
    )

    if not execute:
        typer.echo("\n*** DRY RUN — no groups will be created or modified. Re-run with --execute to apply. ***")

    report_rows = []

    for g in synced_groups:
        new_name = f"{g['name']}{name_suffix}"
        typer.echo(f"\n=== {g['name']} ({g['id']}) -> {new_name} ===")

        users = paginate_nested(q.LIST_GROUP_USERS, {"id": g["id"]}, ["data", "group", "users"])
        resources = paginate_nested(q.LIST_GROUP_RESOURCES, {"id": g["id"]}, ["data", "group", "resources"])
        typer.echo(f"  members: {len(users)}   resources: {len(resources)}")

        row = {
            "source_group_id": g["id"],
            "source_group_name": g["name"],
            "target_group_name": new_name,
            "user_count": len(users),
            "resource_count": len(resources),
            "target_group_id": "",
            "status": "dry-run" if not execute else "",
            "error": "",
        }

        if execute:
            try:
                sec_policy_id = None
                if not no_copy_policy and g.get("securityPolicy"):
                    sec_policy_id = g["securityPolicy"]["id"]

                if new_name in existing_manual:
                    new_id = existing_manual[new_name]["id"]
                    typer.echo(f"  reused existing: {new_id}")
                else:
                    result = client.execute(q.CREATE_GROUP, {
                        "groupName": new_name,
                        "userIDS": [],
                        "resourceIDS": [],
                        "securityPolicyId": sec_policy_id,
                    })["data"]["groupCreate"]
                    if not result["ok"]:
                        raise RuntimeError(f"groupCreate failed: {result['error']}")
                    new_id = result["entity"]["id"]
                    typer.echo(f"  created: {new_id}")

                row["target_group_id"] = new_id

                for chunk in chunked([u["id"] for u in users], BATCH_SIZE):
                    res = client.execute(q.ADD_USERS_TO_GROUP, {"groupID": new_id, "userIDS": chunk})["data"]["groupUpdate"]
                    if not res["ok"]:
                        raise RuntimeError(f"adding users failed: {res['error']}")

                for chunk in chunked([r["id"] for r in resources], BATCH_SIZE):
                    res = client.execute(q.ADD_RESOURCES_TO_GROUP, {"groupID": new_id, "resourceIDS": chunk})["data"]["groupUpdate"]
                    if not res["ok"]:
                        raise RuntimeError(f"adding resources failed: {res['error']}")

                row["status"] = "success"
            except Exception as e:
                row["status"] = "error"
                row["error"] = str(e)
                typer.echo(f"  ERROR: {e}", err=True)

        report_rows.append(row)

    for g in inactive_synced:
        report_rows.append({
            "source_group_id": g["id"],
            "source_group_name": g["name"],
            "target_group_name": "",
            "user_count": "",
            "resource_count": "",
            "target_group_id": "",
            "status": "skipped-inactive",
            "error": "",
        })

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report or f"group_migration_report_{ts}.csv"
    if report_rows:
        with open(report_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
            writer.writeheader()
            writer.writerows(report_rows)
        typer.echo(f"\nReport written to: {report_path}")

    errors = [r for r in report_rows if r["status"] == "error"]
    if errors:
        typer.echo(f"\n{len(errors)} group(s) had errors — see the report for details.", err=True)
        raise typer.Exit(1)


@app.command("assignPolicy")
def group_assign_policy(
    groupid: str = typer.Option(..., "-g", "--groupid", help="Group ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Resource Policy ID."),
) -> None:
    """Assign a Resource Policy to a Group."""
    run_query(
        get_client(),
        q.ASSIGN_POLICY_TO_GROUP,
        {"groupID": groupid, "policyID": policyid},
        t.get_assign_policy_as_csv,
    )
