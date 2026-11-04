"""Read what the tenant already has that the import file mentions. Read-only: the plan is built from this, nothing else."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from tgcli.client.exceptions import TwingateAPIError, TwingateThrottleError
from tgcli.importer.load import GROUP, SERVICE_ACCOUNT, Specs
from tgcli.pagination import fetch_connection
from tgcli.queries import backup as backup_queries
from tgcli.queries import importing as q
from tgcli.resolve import lookup_nodes


CA_TYPES = {"X509CertificateAuthority": "x509", "SSHCertificateAuthority": "ssh"}


@dataclass
class State:
    networks: dict = field(default_factory=dict)  # name -> [node]
    groups: dict = field(default_factory=dict)  # name -> [node with type]
    users: dict = field(default_factory=dict)  # lowercased email -> [node]
    service_accounts: dict = field(default_factory=dict)  # name -> [node]
    policies: dict = field(default_factory=dict)  # name -> [node]
    resources: dict = field(default_factory=dict)  # (name, network name, address) -> [node]
    gateways: dict = field(default_factory=dict)  # address -> [node with remoteNetwork] (read only when a resource is served through one)
    cas: list = field(default_factory=list)  # every certificate authority: {"id", "name", "fingerprint", "type"} (read only when the file has a Gateway or a CA)
    dns_profiles: dict = field(default_factory=dict)  # name -> [node] (read only when the file has DNS profiles)
    unreadable: dict = field(default_factory=dict)  # what could not be read (a tenant without the feature): "certificate authorities" or "DNS profiles" -> the API's words
    devices: dict = field(default_factory=dict)  # lowercased serial number -> [node with isTrusted, activeState, user]
    group_members: dict = field(default_factory=dict)  # group id -> set of user ids (only groups that will be topped up)
    resource_access: dict = field(default_factory=dict)  # resource id -> set of principal ids (only resources that will be topped up)
    resource_approvers: dict = field(default_factory=dict)  # resource id -> set of approver group ids (only resources whose file names approvers)
    # Only read for --sync, which compares an existing object with the file:
    grants: dict = field(default_factory=dict)  # resource id -> {principal id: {name, policy_id, access_policy, approval_mode, expires_at}}
    member_emails: dict = field(default_factory=dict)  # group id -> {user id: email}


def _by(nodes: list, key: Callable[[dict], Any]) -> dict:
    out: dict = {}
    for node in nodes:
        out.setdefault(key(node), []).append(node)
    return out


def _names(specs: Specs) -> dict:
    networks = {s.name for s in specs.networks} | {r.network for r in specs.resources if r.network} | {g.network for g in specs.gateways if g.network}
    groups = {g.name for g in specs.groups} | {a.group for r in specs.resources for a in r.access if a.kind == GROUP}
    groups |= {name for r in specs.resources for name in r.approver_groups} | {name for p in specs.dns_profiles for name in p.groups}
    accounts = {a.group for r in specs.resources for a in r.access if a.kind == SERVICE_ACCOUNT} | {a.name for a in specs.service_accounts}
    policies = {g.security_policy for g in specs.groups} | {r.security_policy for r in specs.resources}
    policies |= {a.security_policy for r in specs.resources for a in r.access}
    emails = {e for g in specs.groups for e in g.members}
    resources = {r.name for r in specs.resources}
    serials = {d.serial for d in specs.devices}
    clean = lambda values: sorted(v for v in values if v)  # noqa: E731
    return {
        "networks": clean(networks), "groups": clean(groups), "service_accounts": clean(accounts), "policies": clean(policies),
        "emails": clean(emails), "resources": clean(resources), "serials": clean(serials),
    }


def _ids(client: Any, query: str, variables: dict, path: list) -> set:
    edges, _, _ = fetch_connection(client, query, variables, path)
    return {edge["node"]["id"] for edge in edges if edge.get("node")}


def resource_grants(client: Any, resource_id: str) -> dict:
    """Who has access to a resource, by principal ID, with the settings of each grant."""
    edges, _, _ = fetch_connection(client, q.RESOURCE_GRANTS, {"id": resource_id}, ["resource", "access"])
    out: dict = {}
    for edge in edges:
        node = edge.get("node") or {}
        if node.get("id"):
            out[node["id"]] = {
                "name": node.get("name"), "policy_id": (edge.get("securityPolicy") or {}).get("id"),
                "access_policy": edge.get("accessPolicy"), "approval_mode": edge.get("approvalMode"), "expires_at": edge.get("expiresAt"),
            }
    return out


def fetch_state(client: Any, specs: Specs, progress: Callable[[str], None] = lambda message: None, sync: bool = False) -> State:
    """Everything the file mentions that the tenant already has. ``sync`` also reads the settings of what exists, to compare."""
    names = _names(specs)
    state = State()

    if names["policies"]:
        progress("Looking up Security Policies...")
        state.policies = _by(lookup_nodes(client, "securityPolicies", "name", names["policies"]), lambda n: n["name"])
    if names["networks"]:
        progress("Looking up Remote Networks...")
        state.networks = _by(lookup_nodes(client, "remoteNetworks", "name", names["networks"]), lambda n: n["name"])
    if names["groups"]:
        progress("Looking up groups...")
        state.groups = _by(lookup_nodes(client, "groups", "name", names["groups"], q.GROUP_DETAIL if sync else "id name type"), lambda n: n["name"])
    if names["service_accounts"]:
        progress("Looking up service accounts...")
        state.service_accounts = _by(lookup_nodes(client, "serviceAccounts", "name", names["service_accounts"]), lambda n: n["name"])
    if names["emails"]:
        progress(f"Looking up {len(names['emails'])} user email(s)...")
        # The email filter is case-sensitive, so the lowercase form is asked for too and matching is done ignoring case.
        asked = sorted(set(names["emails"]) | {e.lower() for e in names["emails"]})
        state.users = _by(lookup_nodes(client, "users", "email", asked, "id email"), lambda n: n["email"].lower())
    if names["resources"]:
        progress("Looking up resources...")
        nodes = lookup_nodes(client, "resources", "name", names["resources"], q.RESOURCE_DETAIL if sync else q.RESOURCE_KEYS)
        state.resources = _by(nodes, lambda n: (n["name"], (n.get("remoteNetwork") or {}).get("name", ""), (n.get("address") or {}).get("value", "")))

    if specs.certificate_authorities or specs.gateways:
        progress("Reading the certificate authorities...")
        try:
            edges, _, _ = fetch_connection(client, q.CERTIFICATE_AUTHORITIES, {}, ["certificateAuthorities"])
        except TwingateAPIError as exc:
            if isinstance(exc, TwingateThrottleError):
                raise
            state.unreadable["certificate authorities"] = str(exc)
        else:
            state.cas = [
                {"id": n["id"], "name": n["name"], "fingerprint": n.get("fingerprint") or "", "type": CA_TYPES.get(n["__typename"], n["__typename"])}
                for n in (e["node"] for e in edges if e.get("node"))
            ]
    if specs.dns_profiles:
        progress("Reading the DNS profiles...")
        try:
            listed = client.execute(q.DNS_PROFILES).get("data", {}).get("dnsFilteringProfiles") or []
        except TwingateAPIError as exc:
            if isinstance(exc, TwingateThrottleError):
                raise
            state.unreadable["DNS profiles"] = str(exc)
        else:
            state.dns_profiles = _by(listed, lambda n: n["name"])

    if any(r.gateway for r in specs.resources) or specs.gateways:
        progress("Reading the Gateways...")
        edges, _, _ = fetch_connection(client, q.GATEWAYS, {}, ["gateways"])
        state.gateways = _by([e["node"] for e in edges if e.get("node")], lambda n: n["address"])

    if names["serials"]:
        progress(f"Looking up {len(names['serials'])} device serial number(s)...")
        # The serial filter is case-sensitive, so the upper and lower case forms are asked for too and matching ignores case.
        asked = sorted(set(names["serials"]) | {v.upper() for v in names["serials"]} | {v.lower() for v in names["serials"]})
        nodes = lookup_nodes(client, "devices", "serialNumber", asked, "id serialNumber isTrusted activeState user { id email }")
        state.devices = _by(nodes, lambda n: n["serialNumber"].lower())

    # Existing objects are topped up (never changed), so what they already hold has to be known.
    for group in specs.groups:
        matches = [n for n in state.groups.get(group.name, []) if n["type"] == "MANUAL"]
        if (group.members or (sync and "members" in group.given)) and len(matches) == 1 and matches[0]["id"] not in state.group_members:
            progress(f"Reading the members of '{group.name}'...")
            if sync:
                edges, _, _ = fetch_connection(client, q.GROUP_USERS_DETAIL, {"id": matches[0]["id"]}, ["group", "users"])
                emails = {e["node"]["id"]: e["node"]["email"] for e in edges if e.get("node")}
                state.member_emails[matches[0]["id"]] = emails
                state.group_members[matches[0]["id"]] = set(emails)
            else:
                state.group_members[matches[0]["id"]] = _ids(client, q.GROUP_USERS, {"id": matches[0]["id"]}, ["group", "users"])
    for resource in specs.resources:
        matches = state.resources.get((resource.name, resource.network, resource.address), [])
        if (resource.access or (sync and "access" in resource.given)) and len(matches) == 1 and matches[0]["id"] not in state.resource_access:
            progress(f"Reading the access of '{resource.name}'...")
            if sync:
                state.grants[matches[0]["id"]] = resource_grants(client, matches[0]["id"])
                state.resource_access[matches[0]["id"]] = set(state.grants[matches[0]["id"]])
            else:
                state.resource_access[matches[0]["id"]] = _ids(client, q.RESOURCE_ACCESS, {"id": matches[0]["id"]}, ["resource", "access"])
        if (resource.approver_groups or (sync and "approvers" in resource.given)) and len(matches) == 1 and matches[0]["id"] not in state.resource_approvers:
            progress(f"Reading the approvers of '{resource.name}'...")
            state.resource_approvers[matches[0]["id"]] = _ids(
                client, backup_queries.CONTINUATION_QUERIES[("resources", "approverGroups")], {"id": matches[0]["id"]}, ["resource", "approverGroups"]
            )
    return state
