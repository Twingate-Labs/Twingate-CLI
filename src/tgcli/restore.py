"""Decide what `tgcli restore` would do to put a tenant back the way a backup of it was. Pure: no API calls, nothing written.

Restore repairs damage to the SAME tenant, so unlike `import` it matches by ID. A group that was renamed is renamed back,
a resource that was moved is moved back. Only an object whose ID is gone (it was deleted, and a deleted object that is
made again has a new ID) is matched by what it is called, and then only when exactly one candidate fits; otherwise it is
created again. Nothing is ever guessed: a reference that cannot be resolved to exactly one object leaves that part out
and says so.

Rules that hold throughout (the same ones `import` keeps):
  * nothing is deleted. What was created after the backup is left alone (``prune`` also takes group members, resource
    access and tags the backup does not have out of the objects the backup has, but never deletes an object).
  * Synced Groups are never touched: their names and members belong to the identity provider.
  * a setting the backup does not have is not cleared, and an expired grant is never made permanent.
  * what this version does not cover is named (``Plan.not_compared``), never skipped silently.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from tgcli.backup_diff import Backup
from tgcli.importer.load import GROUP, SERVICE_ACCOUNT, ResourceSpec, _access, _group, _network, _resource
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, SKIP, UPDATE, Grant, Row, _plural, _service_account_refusal
from tgcli.importer.sync import grant_changes, is_past, resource_changes
from tgcli.queries import backup as q

SUPPORTED = ("remote_networks", "groups", "resources")  # what this version puts back
LOOKUPS = ("users", "security_policies", "service_accounts")  # read only to resolve references (emails, policies, accounts)
READ_KEYS = frozenset(SUPPORTED + LOOKUPS)


@dataclass
class Plan:
    rows: list = field(default_factory=list)
    created_after: dict = field(default_factory=dict)  # label -> how many exist now that the backup does not have (left alone)
    left_alone: list = field(default_factory=list)  # sentences about what was deliberately not looked at
    not_compared: list = field(default_factory=list)  # types this restore did not cover, and why


def _by_id(items: list) -> dict:
    return {str(i["id"]): i for i in items}


def _name(item: dict) -> str:
    return str(item.get("name") or item.get("id"))


def _address(item: dict) -> str:
    return (item.get("address") or {}).get("value") or ""


def _network_name(item: dict) -> str:
    return (item.get("remoteNetwork") or {}).get("name") or ""


def _pair(backup_items: list, current_items: list, key) -> tuple:
    """(pairs, to_create, ambiguous, extra): backup ID -> current object; backup objects with no counterpart; backup objects
    that more than one current object could be; current objects the backup does not have.

    A match by ID always wins. After that a backup object and a current object that share ``key`` are paired only when each is
    the only one with it.
    """
    current_by_id = _by_id(current_items)
    pairs: dict = {}
    rest: list = []
    for item in backup_items:
        found = current_by_id.get(str(item["id"]))
        if found is None:
            rest.append(item)
        else:
            pairs[str(item["id"])] = found
    taken = {str(c["id"]) for c in pairs.values()}
    free_current = [c for c in current_items if str(c["id"]) not in taken]
    backup_keys, current_keys = defaultdict(list), defaultdict(list)
    for item in rest:
        backup_keys[key(item)].append(item)
    for item in free_current:
        current_keys[key(item)].append(item)
    to_create, ambiguous = [], []
    for item in rest:
        same_backup, same_current = backup_keys[key(item)], current_keys.get(key(item), [])
        if len(same_backup) == 1 and len(same_current) == 1:
            pairs[str(item["id"])] = same_current[0]
        elif same_current:
            ambiguous.append(item)
        else:
            to_create.append(item)
    matched = {str(c["id"]) for c in pairs.values()}
    return pairs, to_create, ambiguous, [c for c in current_items if str(c["id"]) not in matched]


class _Refs:
    """What the tenant has now that a backup's references (policies, service accounts, users) have to be resolved against."""

    def __init__(self, current: dict) -> None:
        self.policies = current.get("security_policies")  # None = could not be read
        self.service_accounts = current.get("service_accounts")
        self.users_by_email: dict = defaultdict(list)
        self.user_ids: set = set()
        for user in current.get("users") or []:
            self.user_ids.add(str(user["id"]))
            if user.get("email"):
                self.users_by_email[user["email"].lower()].append(user["id"])

    @staticmethod
    def _resolve(items: Optional[list], ref: dict, what: str) -> tuple:
        """(id, problem) for a reference to an object that may have been deleted and made again under a new ID."""
        if items is None:
            return ref.get("id"), None  # could not be read, so let the API decide
        if any(str(i["id"]) == str(ref.get("id")) for i in items):
            return ref["id"], None
        named = [i for i in items if ref.get("name") and i.get("name") == ref["name"]]
        if len(named) == 1:
            return named[0]["id"], None
        if named:
            return None, f"{what} '{ref['name']}' matches {len(named)} objects now"
        return None, f"{what} '{ref.get('name') or ref.get('id')}' no longer exists"

    def policy(self, ref: Optional[dict]) -> tuple:
        if not ref or not (ref.get("id") or ref.get("name")):
            return None, None
        return self._resolve(self.policies, ref, "Security Policy")

    def service_account(self, ref: dict) -> tuple:
        return self._resolve(self.service_accounts, ref, "service account")

    def user(self, email: str) -> tuple:
        found = self.users_by_email.get(email.lower(), [])
        if len(found) == 1:
            return found[0], None
        return None, (f"member matches {len(found)} users, not added: {email}" if found else f"member not found: {email}")


def _notes(spec: ResourceSpec) -> list:
    """What the importer says it leaves out of a resource, worded for a restore."""
    return [note.replace("not imported", "not restored") for note in spec.notes]


def _source(file: str, item: dict) -> str:
    return f"{file} id {item['id']}"


# ---------------------------------------------------------------- remote networks


def _plan_networks(backup: list, current: list, plan: Plan) -> tuple:
    """Returns (backup network ID -> current ID, backup network ID -> name for those this plan creates)."""
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda n: _name(n))
    plan.created_after["remote networks"] = len(extra)
    ids = {backup_id: found["id"] for backup_id, found in pairs.items()}
    creating: dict = {}
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None:
            continue
        spec = _network(item, _source("remote-networks.json", item))
        changes: dict = {}
        words: list = []
        warnings: list = []
        if _name(item) != _name(found):
            changes["name"] = _name(item)
            words.append(f"rename from '{_name(found)}'")
        if item.get("location") and item.get("location") != found.get("location"):
            changes["location"] = item["location"]
            words.append("location")
        if item.get("isActive") is not None and item["isActive"] != found.get("isActive"):
            changes["isActive"] = item["isActive"]
            words.append("turn back on" if item["isActive"] else "turn off")
        if item.get("networkType") and item["networkType"] != found.get("networkType"):
            warnings.append(f"network type is {found.get('networkType')} now and was {item['networkType']}; the API cannot change it")
        by_name = str(item["id"]) != str(found["id"])
        if by_name:
            warnings.append("the original was deleted; this one has the same name and is taken to be it")
        plan.rows.append(Row(
            "remote network", _name(item), UPDATE if changes else EXISTS, spec,
            "; ".join(words) if words else "no changes", warnings, found["id"], network_update=changes, backup_id=str(item["id"]),
        ))
    for item in to_create:
        spec = _network(item, _source("remote-networks.json", item))
        if spec.problems:
            plan.rows.append(Row("remote network", _name(item), BLOCKED, spec, "; ".join(spec.problems), backup_id=str(item["id"])))
            continue
        creating[str(item["id"])] = spec.name
        plan.rows.append(Row("remote network", spec.name, CREATE, spec, f"deleted since the backup; {spec.network_type.lower()}, {spec.location}", backup_id=str(item["id"])))
    for item in ambiguous:
        spec = _network(item, _source("remote-networks.json", item))
        plan.rows.append(Row("remote network", _name(item), BLOCKED, spec, "its ID is gone and more than one Remote Network has this name, so which one it is cannot be told", backup_id=str(item["id"])))
    return ids, creating


# ---------------------------------------------------------------- groups


def _members(item: dict, refs: _Refs, have_ids: set, have_emails: set) -> tuple:
    """(user IDs to add, warnings) for the backup's members who are not in the group now.

    A member whose user still exists under the same ID is that user, whatever their email says (a tenant can have two users
    with one email). Only a member whose user is gone (made again by the identity provider, so with a new ID) is found by email.
    """
    add: list = []
    warnings: list = []
    for user in item.get("users") or []:
        uid = str(user.get("id")) if isinstance(user, dict) and user.get("id") is not None else None
        email = user.get("email") if isinstance(user, dict) else user
        if uid is not None and uid in refs.user_ids:
            if uid not in have_ids and user["id"] not in add:
                add.append(user["id"])
            continue
        if not email or email.lower() in have_emails:
            continue
        found, problem = refs.user(email)
        if problem:
            warnings.append(problem)
        elif found not in add:
            add.append(found)
    return add, warnings


def _plan_groups(backup: list, current: list, refs: _Refs, plan: Plan, prune: bool) -> dict:
    """Returns backup group ID -> ("id", current ID) or ("new", name): where an access grant to that group should now point."""
    synced = [g for g in backup if g.get("type") == "SYNCED"]
    if synced:
        plan.left_alone.append(f"{_plural(len(synced), 'Synced Group')} (names and members belong to your identity provider)")
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda g: (_name(g), g.get("type")))
    plan.created_after["groups"] = len(extra)
    target: dict = {backup_id: ("id", found["id"]) for backup_id, found in pairs.items()}
    names = [g["name"] for g in to_create if g.get("type") == "MANUAL"]
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None or item.get("type") != "MANUAL" or found.get("type") != "MANUAL":
            continue
        spec = _group(item, _source("groups.json", item))
        changes: dict = {}
        words: list = []
        warnings: list = []
        if _name(item) != _name(found):
            changes["name"] = _name(item)
            words.append(f"rename from '{_name(found)}'")
        if item.get("isActive") is not None and item["isActive"] != found.get("isActive"):
            changes["isActive"] = item["isActive"]
            words.append("turn back on" if item["isActive"] else "turn off")
        policy_id = None
        if item.get("securityPolicy"):
            wanted, problem = refs.policy(item["securityPolicy"])
            if problem:
                warnings.append(f"Security Policy not restored: {problem}")
            elif wanted != (found.get("securityPolicy") or {}).get("id"):
                policy_id = wanted
                words.append("Security Policy")
        current_members = found.get("users") or []
        have_ids = {str(u["id"]) for u in current_members}
        have_emails = {u["email"].lower() for u in current_members if u.get("email")}
        add, member_warnings = _members(item, refs, have_ids, have_emails)
        warnings.extend(member_warnings)
        if add:
            words.append(f"{_plural(len(add), 'member')} to add")
        remove: list = []
        if prune:
            wanted_ids = {str(u.get("id")) for u in item.get("users") or []}
            gone_emails = {(u.get("email") or "").lower() for u in item.get("users") or [] if str(u.get("id")) not in refs.user_ids}
            remove = sorted(
                u["id"] for u in current_members if str(u["id"]) not in wanted_ids and (u.get("email") or "").lower() not in gone_emails
            )
            if remove:
                words.append(f"{_plural(len(remove), 'member')} to remove")
        if str(item["id"]) != str(found["id"]):
            warnings.append("the original was deleted; this one has the same name and is taken to be it")
        plan.rows.append(Row(
            "group", _name(item), UPDATE if words else EXISTS, spec, "; ".join(words) if words else "no changes", warnings,
            found["id"], member_ids=add, group_policy_id=policy_id, remove_member_ids=remove, group_update=changes,
            backup_id=str(item["id"]),
        ))
    for item in to_create:
        spec = _group(item, _source("groups.json", item))
        if item.get("type") != "MANUAL":
            continue  # a deleted Synced Group comes back when the identity provider syncs it (and is then paired above by name)
        if spec.problems:
            plan.rows.append(Row("group", _name(item), BLOCKED, spec, "; ".join(spec.problems), backup_id=str(item["id"])))
            continue
        policy_id = None
        if item.get("securityPolicy"):
            policy_id, problem = refs.policy(item["securityPolicy"])
            if problem:
                plan.rows.append(Row("group", _name(item), BLOCKED, spec, f"it had a Security Policy and {problem}; creating it without one would give it a different policy", backup_id=str(item["id"])))
                continue
        add, warnings = _members(item, refs, set(), set())
        group_update = {"isActive": False} if item.get("isActive") is False else {}
        if names.count(item["name"]) == 1:
            target[str(item["id"])] = ("new", item["name"])
        else:
            warnings.append("another deleted group has this name, so access for it is not restored")
        plan.rows.append(Row(
            "group", spec.name, CREATE, spec, f"deleted since the backup; {_plural(len(add), 'member')}", warnings,
            policy_id=policy_id, member_ids=add, group_update=group_update, backup_id=str(item["id"]),
        ))
    for item in ambiguous:
        spec = _group(item, _source("groups.json", item))
        if item.get("type") == "MANUAL":
            plan.rows.append(Row("group", _name(item), BLOCKED, spec, "its ID is gone and more than one group has this name, so which one it is cannot be told", backup_id=str(item["id"])))
    return target


# ---------------------------------------------------------------- resources


def _access_spec(entry: dict) -> tuple:
    """(AccessSpec or None, notes) for one backup access entry, parsed the way the importer parses it."""
    holder = ResourceSpec()
    _access([entry], holder)
    return (holder.access[0] if holder.access else None), [*holder.notes, *holder.problems]


def _current_edges(item: dict) -> dict:
    """What each principal has now on a resource, by principal ID, in the shape grant_changes compares."""
    edges: dict = {}
    for entry in item.get("access") or []:
        principal = entry.get("principal") or {}
        if principal.get("id"):
            edges[principal["id"]] = {
                "name": principal.get("name"), "policy_id": (entry.get("securityPolicy") or {}).get("id"),
                "access_policy": entry.get("accessPolicy"), "approval_mode": entry.get("approvalMode"),
                "expires_at": entry.get("expiresAt"),
            }
    return edges


def _plan_access(item: dict, edges: Optional[dict], refs: _Refs, groups: dict, current_groups: list, known_groups: set, prune: bool) -> tuple:
    """(grants to add, grants whose settings change, principal IDs to remove, warnings) for one backup resource.

    ``edges`` is what each principal has now, or None when the resource is being created.
    """
    grants: list = []
    updates: list = []
    warnings: list = []
    kept: set = set()
    for entry in item.get("access") or []:
        spec, notes = _access_spec(entry)
        warnings.extend(notes)
        if spec is None:
            continue
        principal = entry.get("principal") or {}
        label = f"{spec.kind} '{spec.group}'"
        principal_id: Optional[str] = None
        if spec.kind == SERVICE_ACCOUNT:
            principal_id, problem = refs.service_account(principal)
            if problem:
                warnings.append(f"access for {label} not restored: {problem}")
                continue
        else:
            where = groups.get(str(principal.get("id")))
            if where is None and str(principal.get("id")) not in known_groups:
                # The backup holds no group with this ID (groups.json is missing from it), so all there is to go on is the name.
                by_name = [g for g in current_groups if g.get("name") == principal.get("name")]
                where = ("id", by_name[0]["id"]) if len(by_name) == 1 else None
            if where is None:
                warnings.append(f"access for {label} not restored: the group no longer exists and cannot be created again")
                continue
            principal_id = where[1] if where[0] == "id" else None
        policy_id, problem = refs.policy(entry.get("securityPolicy"))
        if problem:
            warnings.append(f"access for {label} not restored: {problem}")
            continue
        if principal_id:
            kept.add(principal_id)
        expired = bool(spec.expires_at and is_past(spec.expires_at))
        current = (edges or {}).get(principal_id) if principal_id else None
        if current is not None:
            if spec.kind == GROUP:
                settings, _, warning = grant_changes(spec, current, policy_id, expired)
                if warning:
                    warnings.append(warning)
                if settings:
                    updates.append(Grant(
                        spec.group, principal_id, GROUP, settings.get("policy_id"), settings.get("access_policy"),
                        settings.get("approval_mode"), settings.get("expires_at"),
                    ))
            continue
        if spec.kind == SERVICE_ACCOUNT:
            refusal = _service_account_refusal(spec)
            if refusal:
                warnings.append(f"access for {label} not restored: {refusal}")
            else:
                grants.append(Grant(spec.group, principal_id, kind=SERVICE_ACCOUNT))
            continue
        if expired:
            warnings.append(f"access for {label} not restored: it expired on {spec.expires_at}")
            continue
        grants.append(Grant(spec.group, principal_id, GROUP, policy_id, spec.access_policy, spec.approval_mode, spec.expires_at))
    removals = sorted(i for i in (edges or {}) if i not in kept) if prune and edges is not None else []
    return grants, updates, removals, warnings


def _grant_words(grants: list) -> str:
    groups = sum(1 for g in grants if g.kind == GROUP)
    accounts = len(grants) - groups
    parts = ([_plural(groups, "group")] if groups or not accounts else []) + ([_plural(accounts, "service account")] if accounts else [])
    return " and ".join(parts)


def _network_target(item: dict, networks: dict, creating: dict, current_networks: list) -> Optional[tuple]:
    """Where a resource's Remote Network is now: ("id", ID), ("new", name) for one this run creates, or None."""
    ref = item.get("remoteNetwork") or {}
    if str(ref.get("id")) in networks:
        return "id", networks[str(ref["id"])]
    if str(ref.get("id")) in creating:
        return "new", creating[str(ref["id"])]
    by_name = [n for n in current_networks if n.get("name") == ref.get("name")]
    return ("id", by_name[0]["id"]) if len(by_name) == 1 else None


def _plan_resources(backup: list, current: list, refs: _Refs, networks: dict, creating: dict, groups: dict, current_groups: list, backup_groups: list, current_networks: list, plan: Plan, prune: bool) -> None:
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda r: (_name(r), _network_name(r), _address(r)))
    plan.created_after["resources"] = len(extra)
    known_groups = {str(g["id"]) for g in backup_groups}
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None:
            continue
        source = _source("resources.json", item)
        spec = _resource(item, source)
        warnings: list = _notes(spec)
        words: list = []
        changes: dict = {}
        move: Optional[str] = None
        if item.get("type") == "NETWORK" and found.get("type") == "NETWORK":
            if spec.problems:
                plan.rows.append(Row("resource", _name(item), BLOCKED, spec, "; ".join(spec.problems), backup_id=str(item["id"])))
                continue
            policy_id, problem = refs.policy(item.get("securityPolicy"))
            if problem:
                warnings.append(f"Security Policy not restored: {problem}")
                policy_id = (found.get("securityPolicy") or {}).get("id")
            changes, words = resource_changes(spec, found, policy_id, prune)
            if _name(item) != _name(found):
                changes["name"] = _name(item)
                words.append(f"rename from '{_name(found)}'")
            if _address(item) != _address(found):
                changes["address"] = _address(item)
                words.append("address")
            if item.get("isActive") is not None and item["isActive"] != found.get("isActive"):
                changes["isActive"] = item["isActive"]
                words.append("turn back on" if item["isActive"] else "turn off")
            target = _network_target(item, networks, creating, current_networks)
            if target is None:
                warnings.append(f"Remote Network '{_network_name(item)}' no longer exists; the resource was not moved back")
            elif target[0] == "id" and target[1] != (found.get("remoteNetwork") or {}).get("id"):
                changes["remoteNetworkId"] = target[1]
                words.append("Remote Network")
            elif target[0] == "new":
                move = target[1]
                words.append("Remote Network")
        else:
            warnings.append(f"{item.get('type')} resource: only its access is restored, not its settings")
        grants, updates, removals, access_warnings = _plan_access(item, _current_edges(found), refs, groups, current_groups, known_groups, prune)
        warnings.extend(access_warnings)
        if grants:
            words.append(f"access to add for {_grant_words(grants)}")
        if updates:
            words.append(f"access settings to change for {_plural(len(updates), 'group')}")
        if removals:
            words.append(f"access to remove for {_plural(len(removals), 'principal')}")
        if str(item["id"]) != str(found["id"]):
            warnings.append("the original was deleted; this one has the same name, Remote Network and address and is taken to be it")
        plan.rows.append(Row(
            "resource", _name(item), UPDATE if words else EXISTS, spec, "; ".join(words) if words else "no changes", warnings,
            found["id"], grants=grants, grant_updates=updates, remove_access_ids=removals, resource_update=changes,
            move_to_network=move, backup_id=str(item["id"]),
        ))
    for item in to_create:
        source = _source("resources.json", item)
        spec = _resource(item, source)
        if item.get("type") != "NETWORK":
            plan.rows.append(Row("resource", _name(item), SKIP, spec, f"deleted since the backup; {item.get('type')} resources are not created again yet (they need a Gateway)", backup_id=str(item["id"])))
            continue
        problems = list(spec.problems)
        target = _network_target(item, networks, creating, current_networks)
        if target is None:
            problems.append(f"Remote Network '{_network_name(item)}' no longer exists")
        policy_id, problem = refs.policy(item.get("securityPolicy"))
        if problem:
            problems.append(f"the resource's {problem}")
        if problems:
            plan.rows.append(Row("resource", _name(item), BLOCKED, spec, "; ".join(problems), backup_id=str(item["id"])))
            continue
        grants, _, _, warnings = _plan_access(item, None, refs, groups, current_groups, known_groups, prune)
        update = {"isActive": False} if item.get("isActive") is False else {}
        plan.rows.append(Row(
            "resource", spec.name, CREATE, spec, f"deleted since the backup; in '{spec.network}', access for {_grant_words(grants)}",
            [*_notes(spec), *warnings], policy_id=policy_id, network_id=target[1] if target[0] == "id" else None, grants=grants,
            resource_update=update, backup_id=str(item["id"]),
        ))
    for item in ambiguous:
        spec = _resource(item, _source("resources.json", item))
        plan.rows.append(Row("resource", _name(item), BLOCKED, spec, "its ID is gone and more than one resource has this name, Remote Network and address, so which one it is cannot be told", backup_id=str(item["id"])))


# ---------------------------------------------------------------- the plan


def build_plan(backup: Backup, current: dict, prune: bool = False) -> Plan:
    """Every difference between what the backup holds and what the tenant holds now, as importer Rows (networks, groups, resources).

    ``current`` is the tenant read the way a backup reads it (entity key -> items). A type missing from it could not be read.
    """
    plan = Plan()
    for entity in q.ENTITIES:
        if entity.key in SUPPORTED:
            if entity.key not in backup.items:
                plan.not_compared.append(f"{entity.label} (not in this backup)")
            elif entity.key not in current:
                plan.not_compared.append(f"{entity.label} (could not be read from the tenant)")
        elif entity.key in backup.items:
            plan.not_compared.append(f"{entity.label} (restore does not cover them yet)")
        else:
            plan.not_compared.append(f"{entity.label} (not in this backup)")

    refs = _Refs(current)
    networks, creating = {}, {}
    if "remote_networks" in backup.items and "remote_networks" in current:
        networks, creating = _plan_networks(backup.items["remote_networks"], current["remote_networks"], plan)
    groups: dict = {}
    if "groups" in backup.items and "groups" in current:
        groups = _plan_groups(backup.items["groups"], current["groups"], refs, plan, prune)
    if "resources" in backup.items and "resources" in current:
        _plan_resources(
            backup.items["resources"], current["resources"], refs, networks, creating, groups, current.get("groups", []),
            backup.items.get("groups", []), current.get("remote_networks", []), plan, prune,
        )
    return plan
