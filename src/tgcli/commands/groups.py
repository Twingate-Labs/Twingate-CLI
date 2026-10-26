"""Group management commands."""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from typing import Optional

import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.completion import complete_migratable_groups
from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.output.transformers import groups as t
from tgcli.pagination import NestedLists
from tgcli.queries import groups as q
from tgcli.textio import check_writable

app = typer.Typer(help="Manage Twingate Groups.")


@app.command("list")
def group_list() -> None:
    """List all Groups."""
    run_paginated(
        get_client(), q.LIST_GROUPS, "groups", t.get_list_as_csv,
        nested=NestedLists("group", q.GROUP_CONTINUATIONS),
    )


@app.command("show")
def group_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Group ID."),
) -> None:
    """Show details for a specific group."""
    run_query(
        get_client(), q.SHOW_GROUP, {"itemID": itemid}, t.get_show_as_csv,
        nested=NestedLists("group", q.GROUP_CONTINUATIONS),
    )


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
        nested=NestedLists("group", q.GROUP_CONTINUATIONS, at=("groupCreate", "entity")),
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
        nested=NestedLists("group", q.GROUP_USERS_CONTINUATIONS, at=("groupUpdate", "entity")),
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
        nested=NestedLists("group", q.GROUP_USERS_CONTINUATIONS, at=("groupUpdate", "entity")),
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
        nested=NestedLists("group", q.GROUP_RESOURCES_ECHO_CONTINUATIONS, at=("groupUpdate", "entity")),
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
        nested=NestedLists("group", q.GROUP_RESOURCES_ECHO_CONTINUATIONS, at=("groupUpdate", "entity")),
    )


def _migratable(group: dict) -> bool:
    return group["type"] == "SYNCED" and group["isActive"]


def _select_groups(all_groups: list[dict], selectors: list[str]) -> tuple[list[dict], list[str]]:
    """Resolve --group values (a group ID, else an exact name) to the active Synced Groups to migrate.

    Returns (groups in the order given, without repeats, problems). A group that cannot be migrated is a problem
    rather than something to skip, because the caller asked for it by name.
    """
    chosen: list[dict] = []
    problems: list[str] = []
    for selector in selectors:
        by_id = [g for g in all_groups if g["id"] == selector]
        matches = by_id or [g for g in all_groups if g["name"] == selector]
        ready = [g for g in matches if _migratable(g)]
        if len(ready) == 1:
            if ready[0] not in chosen:
                chosen.append(ready[0])
        elif len(ready) > 1:
            ids = ", ".join(g["id"] for g in ready)
            problems.append(f"'{selector}' matches {len(ready)} active synced groups ({ids}); use the ID")
        elif not matches:
            problems.append(f"no group with ID or name '{selector}'")
        elif len(matches) > 1:
            problems.append(f"none of the {len(matches)} groups named '{selector}' can be migrated (they are not active SYNCED groups)")
        elif matches[0]["type"] != "SYNCED":
            problems.append(f"'{matches[0]['name']}' ({matches[0]['id']}) is a {matches[0]['type']} group; only SYNCED groups can be migrated")
        else:
            problems.append(f"'{matches[0]['name']}' ({matches[0]['id']}) is inactive; only active SYNCED groups can be migrated")
    return chosen, problems


@app.command("migrate")
def group_migrate(
    execute: bool = typer.Option(False, "--execute", help="Apply changes. Without this flag, only a dry run is performed."),
    name_suffix: str = typer.Option(" (Manual)", "--name-suffix", help="Suffix appended to new Manual Group names."),
    no_copy_policy: bool = typer.Option(False, "--no-copy-security-policy", help="Don't copy the source group's Security Policy."),
    report: Optional[str] = typer.Option(None, "--report", help="Path to write the CSV report."),
    only_groups: Optional[list[str]] = typer.Option(
        None, "-g", "--group",
        help=(
            "Migrate only this Synced Group, given by ID or exact name. Repeat for several. "
            "Default: every active Synced Group."
        ),
        autocompletion=complete_migratable_groups,
    ),
) -> None:
    """Migrate active Synced Groups (all, or only those named with --group) to new Manual Groups (dry run by default)."""
    BATCH_SIZE = 200
    client = get_client()
    # Decided, and checked, before anything is read or created: a report path that cannot be written would otherwise
    # only be found after the groups were already made.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report or f"group_migration_report_{ts}.csv"
    try:
        check_writable(report_path)
    except OSError as exc:
        typer.echo(f"Error: cannot write the report to {report_path}: {exc.strerror}. Nothing was changed.", err=True)
        raise typer.Exit(1)

    def paginate_nested(query, variables, path):
        items = []
        after = None
        while True:
            vars_ = {**variables, "after": after}
            result = client.execute(query, vars_)
            node = result["data"]
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
    try:
        pages = client.paginate(q.LIST_GROUPS_FOR_MIGRATE, lambda c: {"cursor": c}, "groups")
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)
    all_groups = [item["node"] for page in pages for item in page]

    synced_groups = [g for g in all_groups if _migratable(g)]
    inactive_synced = [g for g in all_groups if g["type"] == "SYNCED" and not g["isActive"]]
    existing_manual = {g["name"]: g for g in all_groups if g["type"] == "MANUAL"}

    typer.echo(
        f"Found {len(all_groups)} total groups: "
        f"{len(synced_groups)} active synced, "
        f"{len(inactive_synced)} inactive synced (will be skipped)."
    )

    if only_groups:
        chosen, problems = _select_groups(all_groups, only_groups)
        if problems:
            for problem in problems:
                typer.echo(f"Error: {problem}", err=True)
            raise typer.Exit(1)
        typer.echo(f"Selected {len(chosen)} of the {len(synced_groups)} active synced groups with --group.")
        synced_groups = chosen

    if not execute:
        typer.echo("\n*** DRY RUN — no groups will be created or modified. Re-run with --execute to apply. ***")

    report_rows = []

    for g in synced_groups:
        new_name = f"{g['name']}{name_suffix}"
        typer.echo(f"\n=== {g['name']} ({g['id']}) -> {new_name} ===")

        row = {
            "source_group_id": g["id"],
            "source_group_name": g["name"],
            "target_group_name": new_name,
            "user_count": "",
            "resource_count": "",
            "target_group_id": "",
            "status": "",
            "error": "",
        }
        try:
            users = paginate_nested(q.LIST_GROUP_USERS, {"id": g["id"]}, ["group", "users"])
            resources = paginate_nested(q.LIST_GROUP_RESOURCES, {"id": g["id"]}, ["group", "resources"])
        except (TwingateAuthError, TwingateAPIError) as e:
            # Nothing has been created for this group yet. Record it and carry on, so one failed read does not
            # lose the report of the groups already migrated.
            row["status"] = "error"
            row["error"] = f"reading group failed: {e}"
            typer.echo(f"  ERROR: {e}", err=True)
            report_rows.append(row)
            continue
        typer.echo(f"  members: {len(users)}   resources: {len(resources)}")
        row["user_count"] = len(users)
        row["resource_count"] = len(resources)
        row["status"] = "dry-run" if not execute else ""

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

    for g in ([] if only_groups else inactive_synced):
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

    if report_rows:
        try:
            with open(report_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
                writer.writeheader()
                writer.writerows(report_rows)
        except OSError as exc:
            typer.echo(
                f"\nError: the report could not be written to {report_path}: {exc.strerror}. "
                "The results above are all there is; any group shown as created was created.",
                err=True,
            )
            raise typer.Exit(1)
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
        nested=NestedLists("group", q.GROUP_USERS_CONTINUATIONS, at=("groupUpdate", "entity")),
    )
