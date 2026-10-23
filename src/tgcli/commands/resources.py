"""Resource management commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import (
    get_client,
    require_session,
    resolve_many_or_exit,
    run_paginated,
    run_query,
    split_ids,
    split_values,
)
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.output.formatter import OutputFormatter
from tgcli.output.transformers import resources as t
from tgcli.pagination import NestedLists
from tgcli.queries import resources as q
from tgcli.resolve import GROUP, NETWORK, POLICY, SERVICE_ACCOUNT
from tgcli.validators.generic import parse_bool_string, validate_routing_mode
from tgcli.validators.protocol import (
    validate_port_range,
    validate_protocol_policy,
    validate_range_with_policy,
)
from tgcli.main import state

app = typer.Typer(help="Manage Twingate Resources.")
access_app = typer.Typer(help="Give groups and service accounts access to a Resource: add, set (replaces everything), remove.")
app.add_typer(access_app, name="access")


def _access_inputs(
    client,
    groupid: Optional[list[str]],
    serviceid: Optional[list[str]],
    policyid: Optional[list[str]],
    autolockdays: Optional[int],
    expiresat: str,
) -> list[dict]:
    """Build the AccessInput array for resourceAccessSet/Add. Groups, policies and service accounts may be IDs or exact names."""
    groups, services, policies = split_values(groupid), split_values(serviceid), split_values(policyid)
    if len(policies) > 1 and len(policies) != len(groups):
        typer.echo(
            "Error: Number of Policy IDs must be 1 (applied to all Groups) "
            "or match the number of Group IDs.",
            err=True,
        )
        raise typer.Exit(1)
    group_ids, service_ids, policy_ids = resolve_many_or_exit(client, (GROUP, groups), (SERVICE_ACCOUNT, services), (POLICY, policies))

    access_array: list[dict] = []

    for sid in service_ids:
        entry: dict = {"principalId": sid, "securityPolicyId": None}
        if autolockdays:
            entry["usageBasedAutolockDurationDays"] = autolockdays
        if expiresat:
            entry["expiresAt"] = expiresat
        access_array.append(entry)

    for idx, gid in enumerate(group_ids):
        pol = (policy_ids[idx] if len(policy_ids) > 1 else policy_ids[0]) if policy_ids else None
        entry = {"principalId": gid, "securityPolicyId": pol}
        if autolockdays:
            entry["usageBasedAutolockDurationDays"] = autolockdays
        if expiresat:
            entry["expiresAt"] = expiresat
        access_array.append(entry)

    return access_array


@app.command("list")
def resource_list(
    active: Optional[str] = typer.Option(
        None, "-a", "--active",
        help="Filter by active state: true or false. Omit to show all Resources.",
    ),
    detail: bool = typer.Option(
        False, "-d", "--detail",
        help="Add access policy, approval mode, approver groups, gateway, ports and cluster ref (slower on large tenants).",
    ),
) -> None:
    """List all Resources."""
    filter_fn = None
    if active is not None:
        active_bool = parse_bool_string(active)
        filter_fn = lambda node: node.get("isActive") == active_bool  # noqa: E731
    query = q.LIST_RESOURCES_DETAIL if detail else q.LIST_RESOURCES
    transformer = t.get_list_detail_as_csv if detail else t.get_list_as_csv
    continuations = q.RESOURCE_DETAIL_CONTINUATIONS if detail else q.RESOURCE_LIST_CONTINUATIONS
    run_paginated(
        get_client(), query, "resources", transformer, filter_fn=filter_fn,
        nested=NestedLists("resource", continuations),
    )


@app.command("show")
def resource_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Show details for a specific Resource."""
    run_query(
        get_client(), q.SHOW_RESOURCE, {"itemID": itemid}, t.get_show_as_csv,
        nested=NestedLists("resource", q.RESOURCE_SHOW_CONTINUATIONS),
    )


@app.command("create")
def resource_create(
    address: str = typer.Option(..., "-a", "--address", help="Resource address: CIDR/IP/FQDN."),
    name: str = typer.Option(..., "-n", "--name", help="Resource name."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID or exact name."),
    alias: str = typer.Option("", "-l", "--alias", help="Resource alias FQDN."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Resource Policy ID or exact name."),
    groupids: Optional[list[str]] = typer.Option(
        None, "-g", "--groupids",
        help="Group ID or exact name to grant access. Comma-separated, or repeat -g. A name containing a comma needs its ID.",
    ),
    isvisible: str = typer.Option("True", "-v", "--isvisible", help="Visible in Resource list: true or false."),
    icmp: bool = typer.Option(False, "-i", "--icmp", help="Disallow ICMP protocol."),
    tcppolicy: str = typer.Option("ALLOW_ALL", "-t", "--tcppolicy", help="TCP policy: ALLOW_ALL or RESTRICTED."),
    tcprange: str = typer.Option("[]", "-c", "--tcprange", help="TCP port ranges e.g. [[22,22],[443,446]]."),
    udppolicy: str = typer.Option("ALLOW_ALL", "-u", "--udppolicy", help="UDP policy: ALLOW_ALL or RESTRICTED."),
    udprange: str = typer.Option("[]", "-d", "--udprange", help="UDP port ranges e.g. [[53,53]]."),
    routingmode: str = typer.Option(
        "THROUGH_TWINGATE",
        "-m",
        "--routingmode",
        help=(
            "Routing mode: THROUGH_TWINGATE (default) or BYPASS_TWINGATE "
            "(traffic bypasses Twingate and connects directly)."
        ),
    ),
) -> None:
    """Create a new Resource."""
    visible_bool = parse_bool_string(isvisible)
    tcp_policy = validate_protocol_policy(tcppolicy)
    udp_policy = validate_protocol_policy(udppolicy)
    tcp_ports = validate_port_range(tcprange)
    udp_ports = validate_port_range(udprange)
    validate_range_with_policy(tcp_ports, tcp_policy)
    validate_range_with_policy(udp_ports, udp_policy)
    routing_mode = validate_routing_mode(routingmode)

    client = get_client()
    networks, policies, group_ids = resolve_many_or_exit(
        client, (NETWORK, [networkid]), (POLICY, [policyid] if policyid else []), (GROUP, split_values(groupids))
    )
    network_id, policy_id = networks[0], (policies[0] if policies else None)

    variables = {
        "address": address,
        "alias": alias or None,
        "name": name,
        "remoteNetworkId": network_id,
        "groupIds": group_ids,
        "securityPolicyId": policy_id,
        "isVisible": visible_bool,
        "routingMode": routing_mode,
        "protocols": {
            "allowIcmp": not icmp,
            "tcp": {"policy": tcp_policy, "ports": tcp_ports},
            "udp": {"policy": udp_policy, "ports": udp_ports},
        },
    }
    result = run_query(client, q.CREATE_RESOURCE, variables, t.get_create_as_csv)
    created = ((result or {}).get("data") or {}).get("resourceCreate") or {}
    if created.get("ok") and not group_ids:
        typer.echo(
            "\nNote: no group has access to this Resource yet, so nobody can reach it. Give a group access with:\n"
            f"  tgcli -s {require_session()} resource access add -i {(created.get('entity') or {}).get('id', '<resource id>')} -g <group name or ID>\n"
            "or add -g <group> to 'resource create' to create the Resource and grant access in one step.",
            err=True,
        )


@app.command("delete")
def resource_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Delete a Resource."""
    run_query(get_client(), q.DELETE_RESOURCE, {"id": itemid}, t.get_delete_as_csv)


@app.command("assignNetwork")
def resource_assign_network(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    networkid: str = typer.Option(..., "-n", "--networkid", help="Remote Network ID."),
) -> None:
    """Assign a Resource to a different Remote Network."""
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_NETWORK,
        {"itemid": itemid, "networkid": networkid},
        t.get_update_as_csv,
    )


@app.command("visibility")
def resource_visibility(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    value: str = typer.Option("True", "-v", "--value", help="Visibility: true or false."),
) -> None:
    """Toggle Resource visibility in the Resource list."""
    vis_bool = parse_bool_string(value)
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_VISIBILITY,
        {"itemid": itemid, "visibility": vis_bool},
        t.get_visibility_update_as_csv,
    )


@app.command("address")
def resource_address(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    address: str = typer.Option(..., "-a", "--address", help="New address: CIDR/IP/FQDN."),
) -> None:
    """Update a Resource's address."""
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_ADDRESS,
        {"itemid": itemid, "address": address},
        t.get_update_as_csv,
    )


@app.command("alias")
def resource_alias(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    alias: str = typer.Option(..., "-a", "--alias", help="New alias FQDN."),
) -> None:
    """Update a Resource's alias."""
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_ALIAS,
        {"itemid": itemid, "alias": alias},
        t.get_alias_update_as_csv,
    )


@app.command("policy")
def resource_policy(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Resource policy ID."),
) -> None:
    """Update the Resource Policy for a Resource."""
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_POLICY,
        {"itemid": itemid, "securityPolicyId": policyid},
        t.get_policy_update_as_csv,
    )


@app.command("routing")
def resource_routing(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    routingmode: str = typer.Option(
        ...,
        "-m",
        "--routingmode",
        help=(
            "Routing mode: THROUGH_TWINGATE or BYPASS_TWINGATE "
            "(traffic bypasses Twingate and connects directly)."
        ),
    ),
) -> None:
    """Update the routing mode for a Resource."""
    routing_mode = validate_routing_mode(routingmode)
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_ROUTING_MODE,
        {"itemid": itemid, "routingMode": routing_mode},
        t.get_routing_mode_update_as_csv,
    )


@app.command("autolock")
def resource_autolock(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    autolock: int = typer.Option(..., "-a", "--autolock", help="Autolock duration in days (1–365, or -1 to disable)."),
    autoapprove: str = typer.Option("False", "-r", "--autoapprove", help="Auto-approve mode: true (AUTOMATIC) or false (MANUAL)."),
) -> None:
    """Update usage-based autolock duration for a Resource."""
    approve_bool = parse_bool_string(autoapprove)
    approve_mode = "AUTOMATIC" if approve_bool else "MANUAL"
    autolock_val = None if autolock == -1 else autolock
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_AUTOLOCK,
        {"itemid": itemid, "autolock": autolock_val, "autoapprovemode": approve_mode},
        t.get_autolock_update_as_csv,
    )


@app.command("autoapprove")
def resource_autoapprove(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    autoapprove: str = typer.Option("False", "-r", "--autoapprove", help="Auto-approve: true (AUTOMATIC) or false (MANUAL)."),
) -> None:
    """Update the auto-approve mode for a Resource."""
    approve_bool = parse_bool_string(autoapprove)
    approve_mode = "AUTOMATIC" if approve_bool else "MANUAL"
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_AUTOAPPROVE,
        {"itemid": itemid, "autoapprovemode": approve_mode},
        t.get_autolock_update_as_csv,
    )


_GROUP_HELP = "Group ID or exact name. Comma-separated, or repeat -g. A name containing a comma needs its ID."
_SERVICE_HELP = "Service Account ID or exact name. Comma-separated, or repeat -s."
_POLICY_HELP = "Policy ID or exact name: one for all groups, or one per group in order. Comma-separated, or repeat -p."


def resource_access_set(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: Optional[list[str]] = typer.Option(None, "-g", "--group", help=_GROUP_HELP),
    policyid: Optional[list[str]] = typer.Option(None, "-p", "--policy", help=_POLICY_HELP),
    serviceid: Optional[list[str]] = typer.Option(None, "-s", "--service", help=_SERVICE_HELP),
    autolockdays: Optional[int] = typer.Option(None, "-a", "--autolock", help="Autolock days (1–365)."),
    expiresat: str = typer.Option("", "-e", "--expiresat", help="Expiry (ISO8601, e.g. 2024-03-14T20:20:32-07:00)."),
    clear: bool = typer.Option(False, "--clear", help="Remove ALL access (the only way to set an empty list). Cannot be combined with -g or -s."),
) -> None:
    """Set Resource access. REPLACES all existing Group/Service Account access: anything not listed loses access. Use 'access add' to keep what is there."""
    named = bool(split_values(groupid) or split_values(serviceid))
    if clear and named:
        typer.echo("Error: --clear removes all access, so it cannot be combined with -g or -s.", err=True)
        raise typer.Exit(1)
    if not clear and not named:
        typer.echo(
            "Error: 'access set' REPLACES all access, and no group (-g) or service account (-s) was given, "
            "so it would remove everyone's access. Name who should have access, or pass --clear if removing all access is what you want. "
            "To keep the existing access and add more, use 'access add'.",
            err=True,
        )
        raise typer.Exit(1)
    client = get_client()
    access_array = [] if clear else _access_inputs(client, groupid, serviceid, policyid, autolockdays, expiresat)
    run_query(
        client,
        q.RESOURCE_ACCESS_SET,
        {"accessids": access_array, "itemid": itemid},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessSet"),
    )


def resource_access_add(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: Optional[list[str]] = typer.Option(None, "-g", "--group", help=_GROUP_HELP),
    policyid: Optional[list[str]] = typer.Option(None, "-p", "--policy", help=_POLICY_HELP),
    serviceid: Optional[list[str]] = typer.Option(None, "-s", "--service", help=_SERVICE_HELP),
    autolockdays: Optional[int] = typer.Option(None, "-a", "--autolock", help="Autolock days (1–365)."),
    expiresat: str = typer.Option("", "-e", "--expiresat", help="Expiry (ISO8601)."),
) -> None:
    """Add Group/Service Account access to a Resource (non-destructive)."""
    if not split_values(groupid) and not split_values(serviceid):
        typer.echo("Error: Provide at least one group (-g) or service account (-s) to give access to.", err=True)
        raise typer.Exit(1)
    client = get_client()
    access_array = _access_inputs(client, groupid, serviceid, policyid, autolockdays, expiresat)
    run_query(
        client,
        q.RESOURCE_ACCESS_ADD,
        {"accessids": access_array, "itemid": itemid},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessAdd"),
    )


def resource_access_remove(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: Optional[list[str]] = typer.Option(
        None, "-g", "--groupid",
        help="Group ID or exact name to remove (an ID may also be a Service Account's). Comma-separated, or repeat -g.",
    ),
    serviceid: Optional[list[str]] = typer.Option(None, "-s", "--service", help="Service Account ID or exact name to remove."),
) -> None:
    """Remove Group/Service Account access from a Resource."""
    groups, services = split_values(groupid), split_values(serviceid)
    if not groups and not services:
        typer.echo("Error: Provide at least one group (-g) or service account (-s) to remove.", err=True)
        raise typer.Exit(1)
    client = get_client()
    group_ids, service_ids = resolve_many_or_exit(client, (GROUP, groups), (SERVICE_ACCOUNT, services))
    principal_ids = group_ids + service_ids
    run_query(
        client,
        q.RESOURCE_ACCESS_REMOVE,
        {"itemid": itemid, "groupid": principal_ids},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessRemove"),
    )


access_app.command("add")(resource_access_add)
access_app.command("set")(resource_access_set)
access_app.command("remove")(resource_access_remove)
# The original names keep working (scripts, customer write-ups) but are no longer listed in --help.
app.command("access_set", hidden=True)(resource_access_set)
app.command("access_add", hidden=True)(resource_access_add)
app.command("access_remove", hidden=True)(resource_access_remove)


@app.command("disable")
def resource_disable(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Disable a Resource."""
    run_query(get_client(), q.DISABLE_RESOURCE, {"itemid": itemid}, t.get_active_update_as_csv)


@app.command("enable")
def resource_enable(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Enable a Resource."""
    run_query(get_client(), q.ENABLE_RESOURCE, {"itemid": itemid}, t.get_active_update_as_csv)
