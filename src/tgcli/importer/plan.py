"""Decide, from the file and what the tenant already has, what an import would do. Pure: no API calls, nothing written.

Rules that hold throughout:
  * an object that already exists is never changed. It is only added to: missing group members, missing resource access.
    (With ``sync`` it is also brought in line with what the file states; with ``prune`` it also loses what the file omits.)
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

from tgcli.importer.load import GROUP, SERVICE_ACCOUNT, GroupSpec, ResourceSpec, Specs
from tgcli.importer.state import State
from tgcli.importer.sync import grant_changes, resource_changes

CREATE, UPDATE, EXISTS, SKIP, BLOCKED = "create", "update", "exists", "skip", "blocked"


@dataclass
class Grant:
    """One principal's access to a resource, with the IDs resolved. ``group_id`` is None for a group this import creates.

    ``group`` is the name of a group, or of a service account when ``kind`` says so (service accounts are never created).
    """

    group: str
    group_id: Optional[str]
    kind: str = GROUP
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
    device_ids: list = field(default_factory=list)  # devices whose trust is to be changed
    # --sync / --prune, existing objects only:
    group_policy_id: Optional[str] = None  # a group's Security Policy to set
    remove_member_ids: list = field(default_factory=list)  # users to take out of a group
    resource_update: dict = field(default_factory=dict)  # resourceUpdate variables (what differs)
    grant_updates: list = field(default_factory=list)  # Grants whose settings change (only the changed ones are set)
    remove_access_ids: list = field(default_factory=list)  # principals whose access is removed
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


def _plan_group(spec: GroupSpec, state: State, sync: bool = False, prune: bool = False) -> Row:
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
        group_id = manual[0]["id"]
        policy_change = policy_id if sync and "security_policy" in spec.given and policy_id != (manual[0].get("securityPolicy") or {}).get("id") else None
        removals: list = []
        if sync and prune and "members" in spec.given:
            keep = set().union(*(found for _, found in candidates))
            removals = sorted(have - keep)
        parts = []
        if member_ids:
            parts.append(f"{_plural(len(member_ids), 'member')} to add")
        if policy_change:
            parts.append("Security Policy to change")
        if removals:
            emails = state.member_emails.get(group_id, {})
            parts.append(f"{_plural(len(removals), 'member')} to remove ({', '.join(emails.get(u, u) for u in removals)})")
        action = UPDATE if parts else EXISTS
        detail = "already exists; " + ("; ".join(parts) if parts else "no members to add")
        return Row(
            "group", spec.name, action, spec, detail, warnings, group_id, member_ids=member_ids,
            group_policy_id=policy_change, remove_member_ids=removals,
        )
    return Row("group", spec.name, CREATE, spec, _plural(len(member_ids), "member"), warnings, policy_id=policy_id, member_ids=member_ids)


def _plan_groups(specs: list, state: State, rows: list, sync: bool = False, prune: bool = False) -> dict:
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
        row = _plan_group(spec, state, sync, prune)
        if row.action == CREATE:
            planned[spec.name] = True
        rows.append(row)
    return planned


def _grant_words(grants: list) -> str:
    """'2 groups', '1 service account', '1 group and 2 service accounts'."""
    groups = sum(1 for g in grants if g.kind == GROUP)
    accounts = len(grants) - groups
    parts = ([_plural(groups, "group")] if groups or not accounts else []) + ([_plural(accounts, "service account")] if accounts else [])
    return " and ".join(parts)


def _service_account_refusal(entry: Any) -> Optional[str]:
    """Why the API cannot give this entry to a service account (it takes a plain grant and nothing else), if it cannot."""
    wanted = []
    if entry.security_policy:
        wanted.append("its own Security Policy")
    if entry.access_policy:
        wanted.append("an access policy (auto-lock)")
    if entry.expires_at:
        wanted.append("an expiry")
    if entry.approval_mode and entry.approval_mode != "MANUAL":
        wanted.append(f"approval mode {entry.approval_mode}")
    if not wanted:
        return None
    return f"the API cannot give a service account {', '.join(wanted)}, and a plain grant would be wider than the file says"


def _plan_grants(spec: ResourceSpec, state: State, new_groups: dict, have: set, warnings: list, edges: Optional[dict] = None) -> tuple:
    """(grants to add, grants whose settings change). ``edges`` (what each principal has now) is only known for a sync."""
    grants = []
    updates = []
    for entry in spec.access:
        if entry.kind == SERVICE_ACCOUNT:
            found = state.service_accounts.get(entry.group, [])
            label = f"service account '{entry.group}'"
            if len(found) > 1:
                warnings.append(f"access for {label} not added: the tenant has {len(found)} service accounts with that name")
                continue
            if not found:
                warnings.append(f"access for {label} not added: no such service account in this tenant (the import does not create them)")
                continue
            refusal = _service_account_refusal(entry)
            if refusal:
                warnings.append(f"access for {label} not added: {refusal}")
                continue
            if found[0]["id"] not in have:
                grants.append(Grant(entry.group, found[0]["id"], kind=SERVICE_ACCOUNT))
            continue
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
        group_id = found[0]["id"] if found else None
        has_access = group_id is not None and group_id in have
        expired = bool(entry.expires_at and _expired(entry.expires_at))
        if has_access and edges is not None:
            settings, _, warning = grant_changes(entry, edges.get(group_id, {}), policy_id, expired)
            if warning:
                warnings.append(warning)
            if settings:
                updates.append(Grant(
                    entry.group, group_id, GROUP, settings.get("policy_id"), settings.get("access_policy"),
                    settings.get("approval_mode"), settings.get("expires_at"),
                ))
            continue
        if expired:
            warnings.append(f"access for group '{entry.group}' not added: it expired on {entry.expires_at}")
            continue
        if has_access:
            continue  # already has access; its existing settings are left as they are (unless --sync)
        grants.append(Grant(entry.group, group_id, GROUP, policy_id, entry.access_policy, entry.approval_mode, entry.expires_at))
    return grants, updates


def _extra_access(spec: ResourceSpec, state: State, edges: Optional[dict]) -> list:
    """Principals that have access now but are not named by any access entry in the file (every same-named one counts as named)."""
    named: set = set()
    for entry in spec.access:
        pool = state.groups if entry.kind == GROUP else state.service_accounts
        named |= {n["id"] for n in pool.get(entry.group, [])}
    return sorted(i for i in (edges or {}) if i not in named)


def _plan_resources(specs: list, state: State, new_networks: dict, new_groups: dict, rows: list, sync: bool = False, prune: bool = False) -> None:
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
        edges = state.grants.get(existing[0]["id"], {}) if existing and sync else None
        grants, updates = _plan_grants(spec, state, new_groups, have, warnings, edges)
        if existing:
            variables, words = resource_changes(spec, existing[0], policy_id, prune) if sync else ({}, [])
            removals = _extra_access(spec, state, edges) if sync and prune and "access" in spec.given else []
            parts = []
            if grants:
                parts.append(f"access to add for {_grant_words(grants)}")
            if words:
                parts.append("change " + ", ".join(words))
            if updates:
                parts.append(f"access settings to change for {_plural(len(updates), 'group')}")
            if removals:
                names = [(edges.get(i) or {}).get("name") or i for i in removals]
                parts.append(f"access to remove for {_plural(len(removals), 'principal')} ({', '.join(names)})")
            action = UPDATE if parts else EXISTS
            detail = "already exists; " + ("; ".join(parts) if parts else "no access to add")
            rows.append(Row(
                "resource", spec.name, action, spec, detail, warnings, existing[0]["id"], grants=grants, network_id=network_id,
                resource_update=variables, grant_updates=updates, remove_access_ids=removals,
            ))
        else:
            rows.append(Row(
                "resource", spec.name, CREATE, spec, f"in '{spec.network}', access for {_grant_words(grants)}", warnings,
                policy_id=policy_id, network_id=network_id, grants=grants,
            ))


def _plan_devices(specs: list, state: State, rows: list) -> None:
    seen: dict = {}
    for spec in specs:
        if spec.problems:
            rows.append(_blocked("device", spec, spec.problems))
            continue
        key = spec.serial.lower()
        if key in seen:
            rows.append(_blocked("device", spec, [f"same serial number as {seen[key]}"]))
            continue
        seen[key] = spec.source
        found = state.devices.get(key, [])
        live = [d for d in found if d["activeState"] != "ARCHIVED"]
        archived = len(found) - len(live)
        note = f"; {_plural(archived, 'archived device')} ignored" if archived and live else ""
        if not live:
            why = "only archived devices have this serial number" if found else "no device with this serial number has registered in this tenant yet"
            rows.append(Row("device", spec.serial, SKIP, spec, f"{why}; to trust a serial number ahead of time, use `tgcli device snumber add`"))
            continue
        owners = {(d.get("user") or {}).get("email") for d in live}
        if spec.trusted and len(owners) > 1:
            rows.append(_blocked("device", spec, [
                f"{_plural(len(live), 'device')} belonging to {len(owners)} different users have this serial number, and trusting by serial "
                "is only done for one user's devices; use `tgcli device updateTrust -i` for the one you mean"
            ]))
            continue
        todo = [d["id"] for d in live if d["isTrusted"] != spec.trusted]
        word = "trusted" if spec.trusted else "untrusted"
        if todo:
            rows.append(Row("device", spec.serial, UPDATE, spec, f"make {_plural(len(todo), 'device')} {word}{note}", device_ids=todo))
        else:
            rows.append(Row("device", spec.serial, EXISTS, spec, f"already {word} ({_plural(len(live), 'device')}){note}"))


def build_plan(specs: Specs, state: State, sync: bool = False, prune: bool = False) -> list:
    """Every row of the file, as a Row: networks, groups, resources, then devices (the order they are applied in).

    ``sync`` also brings existing groups and resources in line with what the file states; ``prune`` (with ``sync``) also
    removes the members, access and tags the file leaves out. ``state`` must have been read with ``sync`` too.
    """
    rows: list = []
    new_networks = _plan_networks(specs.networks, state, rows)
    new_groups = _plan_groups(specs.groups, state, rows, sync, prune)
    _plan_resources(specs.resources, state, new_networks, new_groups, rows, sync, prune)
    _plan_devices(specs.devices, state, rows)
    return rows
