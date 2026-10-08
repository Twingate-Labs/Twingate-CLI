"""Commands for SSH, web app and Kubernetes resources (the Gateway-backed resource types).

Listing, showing, deleting and enabling/disabling these work through the generic ``resource`` commands.
"""

from __future__ import annotations

from typing import Optional

import typer

from tgcli.commands._common import get_client, run_query, split_ids
from tgcli.output.transformers import resource_types as t
from tgcli.queries import resource_types as q
from tgcli.validators.generic import parse_bool_string

ssh_app = typer.Typer(help="Create and update SSH Resources (served through a Gateway).")
webapp_app = typer.Typer(help="Create and update Web App Resources (served through a Gateway).")
k8s_app = typer.Typer(help="Create and update Kubernetes Resources.")

TLS_CLIENT_MODES = ("VERIFY_FULL", "VERIFY_CA", "INSECURE", "NONE")
TLS_SERVER_MODES = ("TLS13", "NONE")


def _bool(value: str, flag: str) -> bool:
    try:
        return parse_bool_string(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint=flag)


def _choice(value: str, allowed: tuple[str, ...], flag: str) -> str:
    upper = value.strip().upper()
    if upper not in allowed:
        raise typer.BadParameter(f"'{value}'. Choose from: {', '.join(allowed)}", param_hint=flag)
    return upper


def _endpoint(port: Optional[int], tls: str, allowed: tuple[str, ...], label: str) -> Optional[dict]:
    """Build an upstream/downstream input, or None when neither port nor TLS mode was given."""
    if port is None:
        if tls:
            raise typer.BadParameter(f"--{label}-tls needs --{label}-port too.", param_hint=f"--{label}-tls")
        return None
    endpoint: dict = {"port": port}
    if tls:
        endpoint["tlsMode"] = _choice(tls, allowed, f"--{label}-tls")
    return endpoint


def _headers(pairs: Optional[list[str]]) -> Optional[list[dict]]:
    if not pairs:
        return None
    rewrites = []
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise typer.BadParameter(f"'{pair}'. Use Key=Value.", param_hint="--header")
        rewrites.append({"key": key.strip(), "value": value})
    return rewrites


def _put(variables: dict, **optional) -> dict:
    """Add each optional value to variables only when it was actually provided (never sends null)."""
    for key, value in optional.items():
        if value not in (None, "", []):
            variables[key] = value
    return variables


def _create_variables(name, address, networkid, alias, policyid, groupids, isvisible) -> dict:
    return _put(
        {"name": name, "address": address, "remoteNetworkId": networkid},
        alias=alias,
        securityPolicyId=policyid,
        groupIds=split_ids(groupids),
        isVisible=_bool(isvisible, "--isvisible") if isvisible else None,
    )


def _update_variables(itemid, name, address, alias, networkid, gatewayid, policyid, isvisible, active, add_groups, remove_groups) -> dict:
    return _put(
        {"id": itemid},
        name=name,
        address=address,
        alias=alias,
        remoteNetworkId=networkid,
        gatewayId=gatewayid,
        securityPolicyId=policyid,
        isVisible=_bool(isvisible, "--isvisible") if isvisible else None,
        isActive=_bool(active, "--active") if active else None,
        addedGroupIds=split_ids(add_groups),
        removedGroupIds=split_ids(remove_groups),
    )


def _require_a_change(variables: dict) -> None:
    if len(variables) == 1:
        typer.echo("Error: Provide at least one option to change.", err=True)
        raise typer.Exit(1)


PORT = {"min": 1, "max": 65535}


# ---------------------------------------------------------------- SSH


@ssh_app.command("create")
def ssh_create(
    name: str = typer.Option(..., "-n", "--name", help="Resource name."),
    address: str = typer.Option(..., "-a", "--address", help="Resource address: IP/FQDN."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    gatewayid: str = typer.Option(..., "-w", "--gatewayid", help="Gateway ID."),
    alias: str = typer.Option("", "-l", "--alias", help="Resource alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="Resource Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
    isvisible: str = typer.Option("", "-v", "--isvisible", help="Visible in Resource list: true or false."),
    upstream_port: Optional[int] = typer.Option(None, "--upstream-port", help="Port on the target host.", **PORT),
    downstream_port: Optional[int] = typer.Option(None, "--downstream-port", help="Port clients connect to.", **PORT),
) -> None:
    """Create an SSH Resource."""
    variables = _put(
        _create_variables(name, address, networkid, alias, policyid, groupids, isvisible),
        gatewayId=gatewayid,
        upstream=_endpoint(upstream_port, "", (), "upstream"),
        downstream=_endpoint(downstream_port, "", (), "downstream"),
    )
    run_query(get_client(), q.CREATE_SSH_RESOURCE, variables, t.get_create_ssh_as_csv)


@ssh_app.command("update")
def ssh_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="SSH Resource ID."),
    name: str = typer.Option("", "-n", "--name", help="New name."),
    address: str = typer.Option("", "-a", "--address", help="New address."),
    networkid: str = typer.Option("", "-r", "--networkid", help="Move to this Remote Network ID."),
    gatewayid: str = typer.Option("", "-w", "--gatewayid", help="Use this Gateway ID."),
    alias: str = typer.Option("", "-l", "--alias", help="New alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="New Resource Policy ID."),
    isvisible: str = typer.Option("", "-v", "--isvisible", help="Visible in Resource list: true or false."),
    active: str = typer.Option("", "--active", help="Enable or disable the Resource: true or false."),
    add_groups: str = typer.Option("", "--add-groups", help="Comma-separated Group IDs to grant access."),
    remove_groups: str = typer.Option("", "--remove-groups", help="Comma-separated Group IDs to revoke access."),
    upstream_port: Optional[int] = typer.Option(None, "--upstream-port", help="Port on the target host.", **PORT),
    downstream_port: Optional[int] = typer.Option(None, "--downstream-port", help="Port clients connect to.", **PORT),
) -> None:
    """Update an SSH Resource. Only the options you pass are changed."""
    variables = _put(
        _update_variables(itemid, name, address, alias, networkid, gatewayid, policyid, isvisible, active, add_groups, remove_groups),
        upstream=_endpoint(upstream_port, "", (), "upstream"),
        downstream=_endpoint(downstream_port, "", (), "downstream"),
    )
    _require_a_change(variables)
    run_query(get_client(), q.UPDATE_SSH_RESOURCE, variables, t.get_update_ssh_as_csv)


# ---------------------------------------------------------------- Web app


@webapp_app.command("create")
def webapp_create(
    name: str = typer.Option(..., "-n", "--name", help="Resource name."),
    address: str = typer.Option(..., "-a", "--address", help="Resource address: IP/FQDN."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    gatewayid: str = typer.Option(..., "-w", "--gatewayid", help="Gateway ID."),
    upstream_port: int = typer.Option(..., "--upstream-port", help="Port of the web app.", **PORT),
    downstream_port: int = typer.Option(..., "--downstream-port", help="Port clients connect to.", **PORT),
    upstream_tls: str = typer.Option("", "--upstream-tls", help=f"Gateway-to-app TLS: {', '.join(TLS_CLIENT_MODES)}."),
    downstream_tls: str = typer.Option("", "--downstream-tls", help=f"Client-to-Gateway TLS: {', '.join(TLS_SERVER_MODES)}."),
    header: Optional[list[str]] = typer.Option(None, "--header", help="Request header rewrite as Key=Value. Repeatable."),
    alias: str = typer.Option("", "-l", "--alias", help="Resource alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="Resource Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
    isvisible: str = typer.Option("", "-v", "--isvisible", help="Visible in Resource list: true or false."),
) -> None:
    """Create a Web App Resource."""
    variables = _put(
        _create_variables(name, address, networkid, alias, policyid, groupids, isvisible),
        gatewayId=gatewayid,
        upstream=_endpoint(upstream_port, upstream_tls, TLS_CLIENT_MODES, "upstream"),
        downstream=_endpoint(downstream_port, downstream_tls, TLS_SERVER_MODES, "downstream"),
        requestHeaderRewrites=_headers(header),
    )
    run_query(get_client(), q.CREATE_WEBAPP_RESOURCE, variables, t.get_create_webapp_as_csv)


@webapp_app.command("update")
def webapp_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Web App Resource ID."),
    name: str = typer.Option("", "-n", "--name", help="New name."),
    address: str = typer.Option("", "-a", "--address", help="New address."),
    networkid: str = typer.Option("", "-r", "--networkid", help="Move to this Remote Network ID."),
    gatewayid: str = typer.Option("", "-w", "--gatewayid", help="Use this Gateway ID."),
    alias: str = typer.Option("", "-l", "--alias", help="New alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="New Resource Policy ID."),
    isvisible: str = typer.Option("", "-v", "--isvisible", help="Visible in Resource list: true or false."),
    active: str = typer.Option("", "--active", help="Enable or disable the Resource: true or false."),
    add_groups: str = typer.Option("", "--add-groups", help="Comma-separated Group IDs to grant access."),
    remove_groups: str = typer.Option("", "--remove-groups", help="Comma-separated Group IDs to revoke access."),
    upstream_port: Optional[int] = typer.Option(None, "--upstream-port", help="Port of the web app.", **PORT),
    downstream_port: Optional[int] = typer.Option(None, "--downstream-port", help="Port clients connect to.", **PORT),
    upstream_tls: str = typer.Option("", "--upstream-tls", help=f"Needs --upstream-port. {', '.join(TLS_CLIENT_MODES)}."),
    downstream_tls: str = typer.Option("", "--downstream-tls", help=f"Needs --downstream-port. {', '.join(TLS_SERVER_MODES)}."),
    header: Optional[list[str]] = typer.Option(
        None, "--header", help="Request header rewrite as Key=Value. Repeatable. REPLACES the existing list."
    ),
) -> None:
    """Update a Web App Resource. Only the options you pass are changed."""
    variables = _put(
        _update_variables(itemid, name, address, alias, networkid, gatewayid, policyid, isvisible, active, add_groups, remove_groups),
        upstream=_endpoint(upstream_port, upstream_tls, TLS_CLIENT_MODES, "upstream"),
        downstream=_endpoint(downstream_port, downstream_tls, TLS_SERVER_MODES, "downstream"),
        requestHeaderRewrites=_headers(header),
    )
    _require_a_change(variables)
    run_query(get_client(), q.UPDATE_WEBAPP_RESOURCE, variables, t.get_update_webapp_as_csv)


# ---------------------------------------------------------------- Kubernetes


@k8s_app.command("create")
def k8s_create(
    name: str = typer.Option(..., "-n", "--name", help="Resource name."),
    address: str = typer.Option(..., "-a", "--address", help="Resource address: IP/FQDN."),
    networkid: str = typer.Option(..., "-r", "--networkid", help="Remote Network ID."),
    gatewayid: str = typer.Option("", "-w", "--gatewayid", help="Gateway ID."),
    clusterref: str = typer.Option("", "--clusterref", help="Cluster reference."),
    alias: str = typer.Option("", "-l", "--alias", help="Resource alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="Resource Policy ID."),
    groupids: str = typer.Option("", "-g", "--groupids", help="Comma-separated Group IDs."),
    isvisible: str = typer.Option("", "-v", "--isvisible", help="Visible in Resource list: true or false."),
    upstream_port: Optional[int] = typer.Option(None, "--upstream-port", help="Port of the API server.", **PORT),
    downstream_port: Optional[int] = typer.Option(None, "--downstream-port", help="Port clients connect to.", **PORT),
) -> None:
    """Create a Kubernetes Resource."""
    variables = _put(
        _create_variables(name, address, networkid, alias, policyid, groupids, isvisible),
        gatewayId=gatewayid,
        clusterRef=clusterref,
        upstream=_endpoint(upstream_port, "", (), "upstream"),
        downstream=_endpoint(downstream_port, "", (), "downstream"),
    )
    run_query(get_client(), q.CREATE_K8S_RESOURCE, variables, t.get_create_k8s_as_csv)


@k8s_app.command("update")
def k8s_update(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Kubernetes Resource ID."),
    name: str = typer.Option("", "-n", "--name", help="New name."),
    address: str = typer.Option("", "-a", "--address", help="New address."),
    networkid: str = typer.Option("", "-r", "--networkid", help="Move to this Remote Network ID."),
    gatewayid: str = typer.Option("", "-w", "--gatewayid", help="Use this Gateway ID."),
    clusterref: str = typer.Option("", "--clusterref", help="New cluster reference."),
    alias: str = typer.Option("", "-l", "--alias", help="New alias FQDN."),
    policyid: str = typer.Option("", "-p", "--policyid", help="New Resource Policy ID."),
    isvisible: str = typer.Option("", "-v", "--isvisible", help="Visible in Resource list: true or false."),
    active: str = typer.Option("", "--active", help="Enable or disable the Resource: true or false."),
    add_groups: str = typer.Option("", "--add-groups", help="Comma-separated Group IDs to grant access."),
    remove_groups: str = typer.Option("", "--remove-groups", help="Comma-separated Group IDs to revoke access."),
    upstream_port: Optional[int] = typer.Option(None, "--upstream-port", help="Port of the API server.", **PORT),
    downstream_port: Optional[int] = typer.Option(None, "--downstream-port", help="Port clients connect to.", **PORT),
) -> None:
    """Update a Kubernetes Resource. Only the options you pass are changed."""
    variables = _put(
        _update_variables(itemid, name, address, alias, networkid, gatewayid, policyid, isvisible, active, add_groups, remove_groups),
        clusterRef=clusterref,
        upstream=_endpoint(upstream_port, "", (), "upstream"),
        downstream=_endpoint(downstream_port, "", (), "downstream"),
    )
    _require_a_change(variables)
    run_query(get_client(), q.UPDATE_K8S_RESOURCE, variables, t.get_update_k8s_as_csv)
