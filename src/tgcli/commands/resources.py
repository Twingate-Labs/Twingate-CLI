"""Resource management commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.output.formatter import OutputFormatter
from tgcli.output.transformers import resources as t
from tgcli.queries import resources as q
from tgcli.validators.generic import parse_bool_string
from tgcli.validators.protocol import (
    validate_port_range,
    validate_protocol_policy,
    validate_range_with_policy,
)
from tgcli.main import state

app = typer.Typer(help="Manage Twingate resources.")


def _build_access_array(
    groupid: str,
    serviceid: str,
    policyid: str,
    autolockdays: Optional[int],
    expiresat: str,
) -> list[dict]:
    """Build the AccessInput array for resourceAccessSet/Add mutations."""
    access_array: list[dict] = []

    if serviceid:
        for sid in split_ids(serviceid):
            entry: dict = {"principalId": sid, "securityPolicyId": None}
            if autolockdays:
                entry["usageBasedAutolockDurationDays"] = autolockdays
            if expiresat:
                entry["expiresAt"] = expiresat
            access_array.append(entry)

    if groupid:
        gids = split_ids(groupid)
        pols = split_ids(policyid) if policyid else [""]
        if len(pols) > 1 and len(pols) != len(gids):
            typer.echo(
                "Error: Number of policy IDs must be 1 (applied to all groups) "
                "or match the number of group IDs.",
                err=True,
            )
            raise typer.Exit(1)
        for idx, gid in enumerate(gids):
            pol = pols[idx] if len(pols) > 1 else pols[0]
            entry = {"principalId": gid, "securityPolicyId": pol or None}
            if autolockdays:
                entry["usageBasedAutolockDurationDays"] = autolockdays
            if expiresat:
                entry["expiresAt"] = expiresat
            access_array.append(entry)

    return access_array


@app.command("list")
def resource_list() -> None:
    """List all resources."""
    run_paginated(get_client(), q.LIST_RESOURCES, "resources", t.get_list_as_csv)


@app.command("show")
def resource_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Show details for a specific resource."""
    run_query(get_client(), q.SHOW_RESOURCE, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def resource_create(
    address: str = typer.Option(..., "-a", "--address", help="Resource address: CIDR/IP/FQDN."),
    name: str = typer.Option(..., "-n", "--name", help="Resource name."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    alias: str = typer.Option("", "-l", "--alias", help="Resource alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="Security policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated group IDs."),
    isvisible: str = typer.Option("True", "-v", "--isvisible", help="Visible in resource list: true or false."),
    icmp: bool = typer.Option(False, "-i", "--icmp", help="Disallow ICMP protocol."),
    tcppolicy: str = typer.Option("ALLOW_ALL", "-t", "--tcppolicy", help="TCP policy: ALLOW_ALL or RESTRICTED."),
    tcprange: str = typer.Option("[]", "-c", "--tcprange", help="TCP port ranges e.g. [[22,22],[443,446]]."),
    udppolicy: str = typer.Option("ALLOW_ALL", "-u", "--udppolicy", help="UDP policy: ALLOW_ALL or RESTRICTED."),
    udprange: str = typer.Option("[]", "-d", "--udprange", help="UDP port ranges e.g. [[53,53]]."),
) -> None:
    """Create a new resource."""
    visible_bool = parse_bool_string(isvisible)
    tcp_policy = validate_protocol_policy(tcppolicy)
    udp_policy = validate_protocol_policy(udppolicy)
    tcp_ports = validate_port_range(tcprange)
    udp_ports = validate_port_range(udprange)
    validate_range_with_policy(tcp_ports, tcp_policy)
    validate_range_with_policy(udp_ports, udp_policy)

    variables = {
        "address": address,
        "alias": alias or None,
        "name": name,
        "remoteNetworkId": networkid,
        "groupIds": split_ids(groupids),
        "securityPolicyId": policyid or None,
        "isVisible": visible_bool,
        "protocols": {
            "allowIcmp": not icmp,
            "tcp": {"policy": tcp_policy, "ports": tcp_ports},
            "udp": {"policy": udp_policy, "ports": udp_ports},
        },
    }
    run_query(get_client(), q.CREATE_RESOURCE, variables, t.get_create_as_csv)


@app.command("delete")
def resource_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Delete a resource."""
    run_query(get_client(), q.DELETE_RESOURCE, {"id": itemid}, t.get_delete_as_csv)


@app.command("assignNetwork")
def resource_assign_network(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    networkid: str = typer.Option(..., "-n", "--networkid", help="Remote Network ID."),
) -> None:
    """Assign a resource to a different remote network."""
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
    """Toggle resource visibility in the resource list."""
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
    """Update a resource's address."""
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
    """Update a resource's alias."""
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_ALIAS,
        {"itemid": itemid, "alias": alias},
        t.get_alias_update_as_csv,
    )


@app.command("policy")
def resource_policy(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Security policy ID."),
) -> None:
    """Update the security policy for a resource."""
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_POLICY,
        {"itemid": itemid, "securityPolicyId": policyid},
        t.get_policy_update_as_csv,
    )


@app.command("autolock")
def resource_autolock(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    autolock: int = typer.Option(..., "-a", "--autolock", help="Autolock duration in days (1–365, or -1 to disable)."),
    autoapprove: str = typer.Option("False", "-r", "--autoapprove", help="Auto-approve mode: true (AUTOMATIC) or false (MANUAL)."),
) -> None:
    """Update usage-based autolock duration for a resource."""
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
    """Update the auto-approve mode for a resource."""
    approve_bool = parse_bool_string(autoapprove)
    approve_mode = "AUTOMATIC" if approve_bool else "MANUAL"
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_AUTOAPPROVE,
        {"itemid": itemid, "autoapprovemode": approve_mode},
        t.get_autolock_update_as_csv,
    )


@app.command("access_set")
def resource_access_set(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: str = typer.Option("", "-g", "--group", help="Comma-separated group IDs."),
    policyid: str = typer.Option("", "-p", "--policy", help="Comma-separated policy IDs (1 per group, or 1 for all)."),
    serviceid: str = typer.Option("", "-s", "--service", help="Comma-separated service account IDs."),
    autolockdays: Optional[int] = typer.Option(None, "-a", "--autolock", help="Autolock days (1–365)."),
    expiresat: str = typer.Option("", "-e", "--expiresat", help="Expiry (ISO8601, e.g. 2024-03-14T20:20:32-07:00)."),
) -> None:
    """Set resource access (replaces all existing group/service-account relationships)."""
    access_array = _build_access_array(groupid, serviceid, policyid, autolockdays, expiresat)
    run_query(
        get_client(),
        q.RESOURCE_ACCESS_SET,
        {"accessids": access_array, "itemid": itemid},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessSet"),
    )


@app.command("access_add")
def resource_access_add(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: str = typer.Option("", "-g", "--group", help="Comma-separated group IDs."),
    policyid: str = typer.Option("", "-p", "--policy", help="Comma-separated policy IDs."),
    serviceid: str = typer.Option("", "-s", "--service", help="Comma-separated service account IDs."),
    autolockdays: Optional[int] = typer.Option(None, "-a", "--autolock", help="Autolock days (1–365)."),
    expiresat: str = typer.Option("", "-e", "--expiresat", help="Expiry (ISO8601)."),
) -> None:
    """Add group/service-account access to a resource (non-destructive)."""
    access_array = _build_access_array(groupid, serviceid, policyid, autolockdays, expiresat)
    run_query(
        get_client(),
        q.RESOURCE_ACCESS_ADD,
        {"accessids": access_array, "itemid": itemid},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessAdd"),
    )


@app.command("access_remove")
def resource_access_remove(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: str = typer.Option(..., "-g", "--groupid", help="Comma-separated group/service-account IDs to remove."),
) -> None:
    """Remove group/service-account access from a resource."""
    principal_ids = split_ids(groupid)
    run_query(
        get_client(),
        q.RESOURCE_ACCESS_REMOVE,
        {"itemid": itemid, "groupid": principal_ids},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessRemove"),
    )
