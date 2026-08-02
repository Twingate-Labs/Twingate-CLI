"""Resource management commands."""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import get_client, run_paginated, run_query, split_ids
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.output.formatter import OutputFormatter
from tgcli.output.transformers import resources as t
from tgcli.queries import resources as q
from tgcli.validators.generic import parse_bool_string, validate_routing_mode
from tgcli.validators.protocol import (
    validate_port_range,
    validate_protocol_policy,
    validate_range_with_policy,
)
from tgcli.main import state

app = typer.Typer(help="Manage Twingate Resources.")


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

            if expiresat:
                entry["expiresAt"] = expiresat
            access_array.append(entry)

    if groupid:
        gids = split_ids(groupid)
        pols = split_ids(policyid) if policyid else [""]
        if len(pols) > 1 and len(pols) != len(gids):
            typer.echo(
                "Error: Number of Policy IDs must be 1 (applied to all Groups) "
                "or match the number of Group IDs.",
                err=True,
            )
            raise typer.Exit(1)
        for idx, gid in enumerate(gids):
            pol = pols[idx] if len(pols) > 1 else pols[0]
            entry = {"principalId": gid, "securityPolicyId": pol or None}

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
) -> None:
    """List all Resources."""
    filter_fn = None
    if active is not None:
        active_bool = parse_bool_string(active)
        filter_fn = lambda node: node.get("isActive") == active_bool  # noqa: E731
    run_paginated(get_client(), q.LIST_RESOURCES, "resources", t.get_list_as_csv, filter_fn=filter_fn)


@app.command("show")
def resource_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
) -> None:
    """Show details for a specific Resource."""
    run_query(get_client(), q.SHOW_RESOURCE, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def resource_create(
    address: str = typer.Option(..., "-a", "--address", help="Resource address: CIDR/IP/FQDN."),
    name: str = typer.Option(..., "-n", "--name", help="Resource name."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    alias: str = typer.Option("", "-l", "--alias", help="Resource alias FQDN."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Resource Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
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
    tags: str = typer.Option("", "--tags", help="Comma-separated key=value tags, e.g. env=prod,team=backend."),
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

    tag_list = []
    if tags:
        for pair in tags.split(","):
            k, v = pair.split("=", 1)
            tag_list.append({"key": k.strip(), "value": v.strip()})

    variables = {
        "address": address,
        "alias": alias or None,
        "name": name,
        "remoteNetworkId": networkid,
        "groupIds": split_ids(groupids),
        "securityPolicyId": policyid or None,
        "isVisible": visible_bool,
        "routingMode": routing_mode,
        "protocols": {
            "allowIcmp": not icmp,
            "tcp": {"policy": tcp_policy, "ports": tcp_ports},
            "udp": {"policy": udp_policy, "ports": udp_ports},
        },
        "tags": tag_list or None,
    }
    run_query(get_client(), q.CREATE_RESOURCE, variables, t.get_create_as_csv)


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
    mode: str = typer.Option("AUTO_LOCK", "-m", "--mode", help="Access policy mode: MANUAL, AUTO_LOCK, or ACCESS_REQUEST."),
    autoapprove: str = typer.Option("False", "-r", "--autoapprove", help="Auto-approve mode: true (AUTOMATIC) or false (MANUAL)."),
) -> None:
    """Update access policy for a Resource."""
    approve_bool = parse_bool_string(autoapprove)
    approve_mode = "AUTOMATIC" if approve_bool else "MANUAL"
    duration_seconds = autolock * 86400 if autolock != -1 else None
    access_policy = {"mode": mode, "durationSeconds": duration_seconds}
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_AUTOLOCK,
        {"itemid": itemid, "accessPolicy": access_policy, "autoapprovemode": approve_mode},
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


@app.command("rename")
def resource_rename(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    name: str = typer.Option(..., "-n", "--name", help="New Resource name."),
) -> None:
    """Rename a Resource."""
    run_query(get_client(), q.RENAME_RESOURCE, {"itemid": itemid, "name": name}, t.get_rename_as_csv)


@app.command("protocols")
def resource_protocols(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    tcppolicy: str = typer.Option("ALLOW_ALL", "-t", "--tcppolicy", help="TCP policy: ALLOW_ALL or RESTRICTED."),
    tcprange: str = typer.Option("[]", "-c", "--tcprange", help="TCP port ranges e.g. [[22,22],[443,446]]."),
    udppolicy: str = typer.Option("ALLOW_ALL", "-u", "--udppolicy", help="UDP policy: ALLOW_ALL or RESTRICTED."),
    udprange: str = typer.Option("[]", "-d", "--udprange", help="UDP port ranges e.g. [[53,53]]."),
    icmp: bool = typer.Option(False, "--no-icmp", help="Disallow ICMP protocol."),
) -> None:
    """Update protocol restrictions for a Resource."""
    tcp_policy = validate_protocol_policy(tcppolicy)
    udp_policy = validate_protocol_policy(udppolicy)
    tcp_ports = validate_port_range(tcprange)
    udp_ports = validate_port_range(udprange)
    validate_range_with_policy(tcp_ports, tcp_policy)
    validate_range_with_policy(udp_ports, udp_policy)
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_PROTOCOLS,
        {
            "itemid": itemid,
            "protocols": {
                "allowIcmp": not icmp,
                "tcp": {"policy": tcp_policy, "ports": tcp_ports},
                "udp": {"policy": udp_policy, "ports": udp_ports},
            },
        },
        t.get_protocols_update_as_csv,
    )


@app.command("browserShortcut")
def resource_browser_shortcut(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    enabled: str = typer.Option(..., "-e", "--enabled", help="Enable browser shortcut: true or false."),
) -> None:
    """Toggle the browser shortcut for a Resource."""
    enabled_bool = parse_bool_string(enabled)
    run_query(
        get_client(),
        q.UPDATE_RESOURCE_BROWSER_SHORTCUT,
        {"itemid": itemid, "isBrowserShortcutEnabled": enabled_bool},
        t.get_browser_shortcut_update_as_csv,
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
    """Set Resource access (replaces all existing Group/Service Account relationships)."""
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
    """Add Group/Service Account access to a Resource (non-destructive)."""
    access_array = _build_access_array(groupid, serviceid, policyid, autolockdays, expiresat)
    run_query(
        get_client(),
        q.RESOURCE_ACCESS_ADD,
        {"accessids": access_array, "itemid": itemid},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessAdd"),
    )


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


@app.command("access_remove")
def resource_access_remove(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupid: str = typer.Option(..., "-g", "--groupid", help="Comma-separated group/service-account IDs to remove."),
) -> None:
    """Remove Group/Service Account access from a Resource."""
    principal_ids = split_ids(groupid)
    run_query(
        get_client(),
        q.RESOURCE_ACCESS_REMOVE,
        {"itemid": itemid, "groupid": principal_ids},
        lambda d: t.get_access_update_as_csv(d, "resourceAccessRemove"),
    )


@app.command("createSSH")
def resource_create_ssh(
    name: str = typer.Option(..., "-n", "--name", help="SSH Resource name."),
    address: str = typer.Option(..., "-a", "--address", help="Resource address."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    gatewayid: str = typer.Option(..., "--gateway-id", help="Gateway ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Security Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
    isvisible: str = typer.Option("True", "-v", "--isvisible", help="Visible: true or false."),
    upstream: int = typer.Option(None, "--upstream-port", help="Upstream port."),
    downstream: int = typer.Option(None, "--downstream-port", help="Downstream port."),
) -> None:
    """Create an SSH Resource."""
    visible_bool = parse_bool_string(isvisible)
    variables = {
        "name": name, "address": address, "remoteNetworkId": networkid,
        "gatewayId": gatewayid, "securityPolicyId": policyid,
        "groupIds": split_ids(groupids), "isVisible": visible_bool,
    }
    if upstream is not None:
        variables["upstream"] = {"port": upstream}
    if downstream is not None:
        variables["downstream"] = {"port": downstream}
    run_query(get_client(), q.CREATE_SSH_RESOURCE, variables,
              lambda d: t.get_typed_create_as_csv(d, "sshResourceCreate"))


@app.command("updateSSH")
def resource_update_ssh(
    itemid: str = typer.Option(..., "-i", "--itemid", help="SSH Resource ID."),
    name: str = typer.Option("", "-n", "--name", help="New name."),
    address: str = typer.Option("", "-a", "--address", help="New address."),
    gatewayid: str = typer.Option("", "--gateway-id", help="New Gateway ID."),
    upstream: int = typer.Option(None, "--upstream-port", help="Upstream port."),
    downstream: int = typer.Option(None, "--downstream-port", help="Downstream port."),
) -> None:
    """Update an SSH Resource."""
    variables: dict = {"id": itemid}
    if name:
        variables["name"] = name
    if address:
        variables["address"] = address
    if gatewayid:
        variables["gatewayId"] = gatewayid
    if upstream is not None:
        variables["upstream"] = {"port": upstream}
    if downstream is not None:
        variables["downstream"] = {"port": downstream}
    run_query(get_client(), q.UPDATE_SSH_RESOURCE, variables,
              lambda d: t.get_typed_update_as_csv(d, "sshResourceUpdate"))


@app.command("createK8s")
def resource_create_k8s(
    name: str = typer.Option(..., "-n", "--name", help="Kubernetes Resource name."),
    address: str = typer.Option(..., "-a", "--address", help="Resource address."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    gatewayid: str = typer.Option(..., "--gateway-id", help="Gateway ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Security Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
    isvisible: str = typer.Option("True", "-v", "--isvisible", help="Visible: true or false."),
    upstream: int = typer.Option(None, "--upstream-port", help="Upstream port."),
    downstream: int = typer.Option(None, "--downstream-port", help="Downstream port."),
) -> None:
    """Create a Kubernetes Resource."""
    visible_bool = parse_bool_string(isvisible)
    variables = {
        "name": name, "address": address, "remoteNetworkId": networkid,
        "gatewayId": gatewayid, "securityPolicyId": policyid,
        "groupIds": split_ids(groupids), "isVisible": visible_bool,
    }
    if upstream is not None:
        variables["upstream"] = {"port": upstream}
    if downstream is not None:
        variables["downstream"] = {"port": downstream}
    run_query(get_client(), q.CREATE_KUBERNETES_RESOURCE, variables,
              lambda d: t.get_typed_create_as_csv(d, "kubernetesResourceCreate"))


@app.command("updateK8s")
def resource_update_k8s(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Kubernetes Resource ID."),
    name: str = typer.Option("", "-n", "--name", help="New name."),
    address: str = typer.Option("", "-a", "--address", help="New address."),
    gatewayid: str = typer.Option("", "--gateway-id", help="New Gateway ID."),
    upstream: int = typer.Option(None, "--upstream-port", help="Upstream port."),
    downstream: int = typer.Option(None, "--downstream-port", help="Downstream port."),
) -> None:
    """Update a Kubernetes Resource."""
    variables: dict = {"id": itemid}
    if name:
        variables["name"] = name
    if address:
        variables["address"] = address
    if gatewayid:
        variables["gatewayId"] = gatewayid
    if upstream is not None:
        variables["upstream"] = {"port": upstream}
    if downstream is not None:
        variables["downstream"] = {"port": downstream}
    run_query(get_client(), q.UPDATE_KUBERNETES_RESOURCE, variables,
              lambda d: t.get_typed_update_as_csv(d, "kubernetesResourceUpdate"))


@app.command("createWebApp")
def resource_create_webapp(
    name: str = typer.Option(..., "-n", "--name", help="Web App Resource name."),
    address: str = typer.Option(..., "-a", "--address", help="Resource address."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    gatewayid: str = typer.Option(..., "--gateway-id", help="Gateway ID."),
    policyid: str = typer.Option(..., "-p", "--policyid", help="Security Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
    isvisible: str = typer.Option("True", "-v", "--isvisible", help="Visible: true or false."),
    upstream: int = typer.Option(None, "--upstream-port", help="Upstream port."),
    downstream: int = typer.Option(None, "--downstream-port", help="Downstream port."),
) -> None:
    """Create a Web App Resource."""
    visible_bool = parse_bool_string(isvisible)
    variables = {
        "name": name, "address": address, "remoteNetworkId": networkid,
        "gatewayId": gatewayid, "securityPolicyId": policyid,
        "groupIds": split_ids(groupids), "isVisible": visible_bool,
    }
    if upstream is not None:
        variables["upstream"] = {"port": upstream}
    if downstream is not None:
        variables["downstream"] = {"port": downstream}
    run_query(get_client(), q.CREATE_WEBAPP_RESOURCE, variables,
              lambda d: t.get_typed_create_as_csv(d, "webAppResourceCreate"))


@app.command("updateWebApp")
def resource_update_webapp(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Web App Resource ID."),
    name: str = typer.Option("", "-n", "--name", help="New name."),
    address: str = typer.Option("", "-a", "--address", help="New address."),
    gatewayid: str = typer.Option("", "--gateway-id", help="New Gateway ID."),
    upstream: int = typer.Option(None, "--upstream-port", help="Upstream port."),
    downstream: int = typer.Option(None, "--downstream-port", help="Downstream port."),
) -> None:
    """Update a Web App Resource."""
    variables: dict = {"id": itemid}
    if name:
        variables["name"] = name
    if address:
        variables["address"] = address
    if gatewayid:
        variables["gatewayId"] = gatewayid
    if upstream is not None:
        variables["upstream"] = {"port": upstream}
    if downstream is not None:
        variables["downstream"] = {"port": downstream}
    run_query(get_client(), q.UPDATE_WEBAPP_RESOURCE, variables,
              lambda d: t.get_typed_update_as_csv(d, "webAppResourceUpdate"))


@app.command("updateTags")
def resource_update_tags(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    tags: str = typer.Option(..., "--tags", help="Comma-separated key=value tags (replaces all). Use '' to clear."),
) -> None:
    """Set tags on a Resource (replaces all existing tags)."""
    tag_list = []
    if tags:
        for pair in tags.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                tag_list.append({"key": k.strip(), "value": v.strip()})
    run_query(get_client(), q.UPDATE_RESOURCE_TAGS, {"itemid": itemid, "tags": tag_list}, t.get_tags_update_as_csv)


@app.command("addApproverGroups")
def resource_add_approver_groups(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupids: str = typer.Option(..., "-g", "--groupids", help="Comma-separated Group IDs to add as approvers."),
) -> None:
    """Add approver groups to a Resource."""
    run_query(
        get_client(),
        q.ADD_APPROVER_GROUPS,
        {"itemid": itemid, "addedApproverGroupIds": split_ids(groupids)},
        t.get_approver_groups_update_as_csv,
    )


@app.command("removeApproverGroups")
def resource_remove_approver_groups(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupids: str = typer.Option(..., "-g", "--groupids", help="Comma-separated Group IDs to remove as approvers."),
) -> None:
    """Remove approver groups from a Resource."""
    run_query(
        get_client(),
        q.REMOVE_APPROVER_GROUPS,
        {"itemid": itemid, "removedApproverGroupIds": split_ids(groupids)},
        t.get_approver_groups_update_as_csv,
    )


@app.command("setApproverGroups")
def resource_set_approver_groups(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Resource ID."),
    groupids: str = typer.Option(..., "-g", "--groupids", help="Comma-separated Group IDs (replaces all approvers)."),
) -> None:
    """Replace all approver groups on a Resource."""
    run_query(
        get_client(),
        q.SET_APPROVER_GROUPS,
        {"itemid": itemid, "approverGroupIds": split_ids(groupids)},
        t.get_approver_groups_update_as_csv,
    )
