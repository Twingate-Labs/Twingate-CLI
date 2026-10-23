"""Decide, from the file and what the tenant already has, what an import would do. Pure: no API calls, nothing written.

Rules that hold throughout:
  * an object that already exists is never changed. It is only added to: missing group members, missing resource access.
  * Synced Groups are never modified (their members belong to the identity provider).
  * a reference that cannot be resolved to exactly one object is never guessed. If the row cannot be made correctly
    without it (its Remote Network, its Security Policy) the row is blocked; if only an optional extra is lost (a member
    who has left, an access grant to a group that does not exist) the row proceeds and says what it left out. Leaving
    something out never gives anyone more access than the file describes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from tgcli.importer.load import GroupSpec, ResourceSpec, Specs
from tgcli.importer.state import State

CREATE, UPDATE, EXISTS, SKIP, BLOCKED = "create", "update", "exists", "skip", "blocked"


@dataclass
class Grant:
    """One group's access to a resource, with the IDs resolved. ``group_id`` is None for a group this import creates."""

    group: str
    group_id: Optional[str]
    policy_id: Optional[str] = None
    access_policy: Optional[dict] = None
    approval_mode: Optional[str] = None
    expires_at: Optional[str] = None


@dataclass
class Row:
    kind: str  # "remote network" | "group" | "resource"
    name: str
    action: str
    spec: Any
    detail: str = ""
    warnings: list = field(default_factory=list)
    existing_id: Optional[str] = None
    policy_id: Optional[str] = None  # a group's or resource's Security Policy
    network_id: Optional[str] = None  # None when the network is created by this import
    member_ids: list = field(default_factory=list)  # users to add
    grants: list = field(default_factory=list)  # Grants to add
    # filled in by apply
    status: str = ""
    id: str = ""
    error: str = ""


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _expired(expires_at: str) -> bool:
    try:
        when = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when <= datetime.now(timezone.utc)


def _blocked(kind: str, spec: Any, reasons: list) -> Row:
    return Row(kind, spec.name or "(no name)", BLOCKED, spec, "; ".join(reasons))


def _resolve_policy(state: State, name: Optional[str], what: str) -> tuple:
    """(policy id, problem). No name means no policy to resolve."""
    if not name:
        return None, None
    matches = state.policies.get(name, [])
    if not matches:
        return None, f"{what} Security Policy '{name}' does not exist in this tenant"
    if len(matches) > 1:
        return None, f"{what} Security Policy '{name}' matches {len(matches)} policies"
    return matches[0]["id"], None


def _plan_networks(specs: list, state: State, rows: list) -> dict:
    """Returns name -> action for networks this plan will create, so resources can rely on them."""
    seen: dict = {}
    planned: dict = {}
    for spec in specs:
        if spec.problems:
            rows.append(_blocked("remote network", spec, spec.problems))
            continue
        if spec.name in seen:
            rows.append(_blocked("remote network", spec, [f"same name as {seen[spec.name]}"]))
            continue
        seen[spec.name] = spec.source
        found = state.networks.get(spec.name, [])
        if len(found) > 1:
            rows.append(_blocked("remote network", spec, [f"the tenant has {len(found)} Remote Networks with this name"]))
        elif found:
            rows.append(Row("remote network", spec.name, EXISTS, spec, "already exists", existing_id=found[0]["id"]))
        else:
            planned[spec.name] = True
            rows.append(Row("remote network", spec.name, CREATE, spec, f"{spec.network_type.lower()}, {spec.location}"))
    return planned


def _plan_group(spec: GroupSpec, state: State) -> Row:
    if spec.type == "SYNCED":
        return Row("group", spec.name, SKIP, spec, "Synced Group: its members come from your identity provider, so it is never created or changed")
    if spec.type != "MANUAL":
        return Row("group", spec.name, SKIP, spec, f"{spec.type.title()} group: not imported")
    policy_id, problem = _resolve_policy(state, spec.security_policy, "the group's")
    if problem:
        return _blocked("group", spec, [problem])

    candidates = [(email, {n["id"] for n in state.users.get(email.lower(), [])}) for email in spec.members]
    matches = state.groups.get(spec.name, [])
    manual = [n for n in matches if n["type"] == "MANUAL"]
    if len(manual) > 1:
        return _blocked("group", spec, [f"the tenant has {len(manual)} Manual Groups with this name"])
    if not manual and matches:
        kinds = ", ".join(sorted({n["type"].lower() for n in matches}))
        return Row("group", spec.name, SKIP, spec, f"a {kinds} group with this name already exists here; nothing created or changed")
    have = state.group_members.get(manual[0]["id"], set()) if manual else set()
    warnings: list = []
    member_ids: list = []
    for email, found in candidates:
        if found & have:
            continue  # already a member (this also settles an email that two users share)
        if not found:
            warnings.append(f"member not found: {email}")
        elif len(found) > 1:
            warnings.append(f"member matches {len(found)} users, not added: {email}")
        else:
            member_ids.append(next(iter(found)))
    member_ids = list(dict.fromkeys(member_ids))
    if manual:
        action = UPDATE if member_ids else EXISTS
        detail = f"already exists; {_plural(len(member_ids), 'member')} to add" if member_ids else "already exists; no members to add"
        return Row("group", spec.name, action, spec, detail, warnings, manual[0]["id"], member_ids=member_ids)
    return Row("group", spec.name, CREATE, spec, _plural(len(member_ids), "member"), warnings, policy_id=policy_id, member_ids=member_ids)


def _plan_groups(specs: list, state: State, rows: list) -> dict:
    """Returns name -> True for groups this plan creates."""
    seen: dict = {}
    planned: dict = {}
    for spec in specs:
        if spec.problems:
            rows.append(_blocked("group", spec, spec.problems))
            continue
        key = (spec.name, spec.type)
        if spec.type == "MANUAL" and key in seen:
            rows.append(_blocked("group", spec, [f"same name as {seen[key]}"]))
            continue
        seen[key] = spec.source
        row = _plan_group(spec, state)
        if row.action == CREATE:
            planned[spec.name] = True
        rows.append(row)
    return planned


def _plan_grants(spec: ResourceSpec, state: State, new_groups: dict, have: set, warnings: list) -> list:
    grants = []
    for entry in spec.access:
        found = state.groups.get(entry.group, [])
        if len(found) > 1:
            warnings.append(f"access for group '{entry.group}' not added: the tenant has {len(found)} groups with that name")
            continue
        if not found and entry.group not in new_groups:
            warnings.append(f"access for group '{entry.group}' not added: no such group in this tenant or in the file")
            continue
        policy_id, problem = _resolve_policy(state, entry.security_policy, f"group '{entry.group}'")
        if problem:
            warnings.append(f"access for group '{entry.group}' not added: {problem}")
            continue
        if entry.expires_at and _expired(entry.expires_at):
            warnings.append(f"access for group '{entry.group}' not added: it expired on {entry.expires_at}")
            continue
        group_id = found[0]["id"] if found else None
        if group_id is not None and group_id in have:
            continue  # already has access; its existing settings are left as they are
        grants.append(Grant(entry.group, group_id, policy_id, entry.access_policy, entry.approval_mode, entry.expires_at))
    return grants


def _plan_resources(specs: list, state: State, new_networks: dict, new_groups: dict, rows: list) -> None:
    seen: dict = {}
    for spec in specs:
        if spec.type != "NETWORK":
            rows.append(Row("resource", spec.name or "(no name)", SKIP, spec, f"{spec.type} resources are not imported yet; only standard network resources are"))
            continue
        if spec.problems:
            rows.append(_blocked("resource", spec, spec.problems))
            continue
        key = (spec.name, spec.network, spec.address)
        if key in seen:
            rows.append(_blocked("resource", spec, [f"same name, Remote Network and address as {seen[key]}, so the two cannot be told apart"]))
            continue
        seen[key] = spec.source

        problems: list = []
        networks = state.networks.get(spec.network, [])
        network_id = None
        if len(networks) > 1:
            problems.append(f"the tenant has {len(networks)} Remote Networks named '{spec.network}'")
        elif networks:
            network_id = networks[0]["id"]
        elif spec.network not in new_networks:
            problems.append(f"Remote Network '{spec.network}' does not exist in this tenant or in the file")
        policy_id, problem = _resolve_policy(state, spec.security_policy, "the resource's")
        if problem:
            problems.append(problem)
        if problems:
            rows.append(_blocked("resource", spec, problems))
            continue

        existing = state.resources.get(key, [])
        if len(existing) > 1:
            rows.append(_blocked("resource", spec, [f"the tenant has {len(existing)} resources with this name, Remote Network and address, so the right one cannot be told"]))
            continue
        warnings = list(spec.notes)
        have = state.resource_access.get(existing[0]["id"], set()) if existing else set()
        grants = _plan_grants(spec, state, new_groups, have, warnings)
        if existing:
            action = UPDATE if grants else EXISTS
            detail = f"already exists; access to add for {_plural(len(grants), 'group')}" if grants else "already exists; no access to add"
            rows.append(Row("resource", spec.name, action, spec, detail, warnings, existing[0]["id"], grants=grants, network_id=network_id))
        else:
            rows.append(Row(
                "resource", spec.name, CREATE, spec, f"in '{spec.network}', access for {_plural(len(grants), 'group')}", warnings,
                policy_id=policy_id, network_id=network_id, grants=grants,
            ))


def build_plan(specs: Specs, state: State) -> list:
    """Every row of the file, as a Row, networks first, then groups, then resources (the order they are applied in)."""
    rows: list = []
    new_networks = _plan_networks(specs.networks, state, rows)
    new_groups = _plan_groups(specs.groups, state, rows)
    _plan_resources(specs.resources, state, new_networks, new_groups, rows)
    return rows
