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
from tgcli.importer.load import GROUP, NETWORK_RESOURCE, RESOURCE_TYPES, SERVICE_ACCOUNT, Item, ResourceSpec, _access, _group, _network, _resource
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, SKIP, UPDATE, Grant, Ref, Row, Step, _plural, _service_account_refusal
from tgcli.importer.sync import gateway_resource_changes, grant_changes, is_past, resource_changes
from tgcli.queries import backup as q
from tgcli.queries import restoring as w

SUPPORTED = ("remote_networks", "groups", "service_accounts", "gateways", "connectors", "resources", "dns_profiles")  # what this version puts back
LOOKUPS = ("users", "security_policies", "certificate_authorities")  # read only to resolve references (emails, policies, certificate authorities)
# Reversing a device's block or trust, or a user's role, undoes security decisions made since the backup, so these are only restored when asked for.
OPT_IN = ("devices", "roles")
READ_KEYS = frozenset(SUPPORTED + LOOKUPS)


def read_keys(backup: Backup) -> frozenset:
    """What a dry run reads from the tenant: the types it puts back, what it looks references up in, and devices when the backup has them."""
    return READ_KEYS | ({"devices"} if "devices" in backup.items else frozenset())


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
        self.gateways = current.get("gateways")
        self.new_gateways: dict = {}  # backup Gateway ID -> Ref, for a Gateway this restore creates
        self.new_service_accounts: dict = {}  # backup service account ID -> name, for one this restore creates
        self.certificate_authorities = current.get("certificate_authorities")
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

    def gateway(self, ref: Optional[dict]) -> tuple:
        """(Gateway ID or Ref, problem). A Gateway has no name, so one whose ID is gone is found by its address."""
        if not ref or not (ref.get("id") or ref.get("address")):
            return None, None
        if str(ref.get("id")) in self.new_gateways:
            return self.new_gateways[str(ref["id"])], None
        if self.gateways is None:
            return ref.get("id"), None
        if any(str(g["id"]) == str(ref.get("id")) for g in self.gateways):
            return ref["id"], None
        same = [g for g in self.gateways if ref.get("address") and g.get("address") == ref["address"]]
        if len(same) == 1:
            return same[0]["id"], None
        if same:
            return None, f"Gateway '{ref['address']}' matches {len(same)} Gateways now"
        return None, f"Gateway '{ref.get('address') or ref.get('id')}' no longer exists"

    def service_account(self, ref: dict) -> tuple:
        return self._resolve(self.service_accounts, ref, "service account")

    def user(self, email: str) -> tuple:
        found = self.users_by_email.get(email.lower(), [])
        if len(found) == 1:
            return found[0], None
        return None, (f"member matches {len(found)} users, not added: {email}" if found else f"member not found: {email}")


def _notes(spec: ResourceSpec) -> list:
    """What the importer says it leaves out of a resource, worded for a restore (approver groups are restored, so that note goes)."""
    return [note.replace("not imported", "not restored") for note in spec.notes if "approver groups" not in note]


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


# ---------------------------------------------------------------- service accounts


def _item(file: str, item: dict) -> Item:
    return Item(source=_source(file, item))


def _plan_service_accounts(backup: list, current: list, refs: _Refs, plan: Plan) -> None:
    """Rename service accounts back and make deleted ones again (their keys cannot come back). Their access is given from the resource side."""
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda a: _name(a))
    plan.created_after["service accounts"] = len(extra)
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None:
            continue
        warnings = ["the original was deleted; this one has the same name and is taken to be it"] if str(item["id"]) != str(found["id"]) else []
        if _name(item) != _name(found):
            plan.rows.append(Row(
                "service account", _name(item), UPDATE, _item("service-accounts.json", item), f"rename from '{_name(found)}'", warnings, found["id"],
                steps=[Step(w.UPDATE_SERVICE_ACCOUNT, {"id": found["id"], "name": _name(item)}, "serviceAccountUpdate")], backup_id=str(item["id"]),
            ))
        else:
            plan.rows.append(Row("service account", _name(item), EXISTS, _item("service-accounts.json", item), "no changes", warnings, found["id"], backup_id=str(item["id"])))
    names = [_name(a) for a in to_create]
    for item in to_create:
        spec = _item("service-accounts.json", item)
        if names.count(_name(item)) > 1:
            plan.rows.append(Row("service account", _name(item), BLOCKED, spec, "more than one deleted service account had this name, so they cannot be told apart", backup_id=str(item["id"])))
            continue
        keys = item.get("keys") or []
        warnings = [f"its {_plural(len(keys), 'key')} cannot be restored (a backup never holds the secrets): create new ones with `tgcli key create`"] if keys else []
        refs.new_service_accounts[str(item["id"])] = _name(item)
        plan.rows.append(Row(
            "service account", _name(item), CREATE, spec, "deleted since the backup", warnings,
            steps=[Step(w.CREATE_SERVICE_ACCOUNT, {"name": _name(item)}, "serviceAccountCreate", remember=("service account", _name(item)))], backup_id=str(item["id"]),
        ))
    for item in ambiguous:
        plan.rows.append(Row("service account", _name(item), BLOCKED, _item("service-accounts.json", item), "its ID is gone and more than one service account has this name, so which one it is cannot be told", backup_id=str(item["id"])))


# ---------------------------------------------------------------- gateways


def _resolve_ca(cas: Optional[list], ref: Optional[dict]) -> tuple:
    """(ID, problem) for a Gateway's certificate authority. A CA that was deleted cannot be made again without its certificate file."""
    if not ref:
        return None, None
    if cas is None:
        return ref.get("id"), None
    if any(str(c["id"]) == str(ref.get("id")) for c in cas):
        return ref["id"], None
    same = [c for c in cas if ref.get("fingerprint") and c.get("fingerprint") == ref["fingerprint"]]
    if len(same) == 1:
        return same[0]["id"], None
    return None, (
        f"its certificate authority '{ref.get('name') or ref.get('id')}' no longer exists, and a certificate authority can only be made again "
        "from its certificate file (`tgcli ca create`); do that and run the restore again"
    )


def _plan_gateways(backup: list, current: list, refs: _Refs, networks: dict, creating: dict, current_networks: list, plan: Plan) -> None:
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda g: (g.get("address"), _network_name(g)))
    plan.created_after["Gateways"] = len(extra)
    cas = refs.certificate_authorities
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None:
            continue
        spec = _item("gateways.json", item)
        changes: dict = {}
        words: list = []
        warnings: list = []
        if item.get("address") != found.get("address"):
            changes["address"] = item["address"]
            words.append(f"address from '{found.get('address')}'")
        target = _network_target(item, networks, creating, current_networks)
        if target is None:
            warnings.append(f"Remote Network '{_network_name(item)}' no longer exists; the Gateway was not moved back")
        elif target[0] == "id" and target[1] != (found.get("remoteNetwork") or {}).get("id"):
            changes["remoteNetworkId"] = target[1]
            words.append("Remote Network")
        elif target[0] == "new":
            changes["remoteNetworkId"] = Ref("network", target[1])
            words.append("Remote Network")
        for key, field_name, label in (("x509CAId", "x509CA", "X.509 certificate authority"), ("sshCAId", "sshCA", "SSH certificate authority")):
            if not item.get(field_name):
                continue
            wanted, problem = _resolve_ca(cas, item[field_name])
            if problem:
                warnings.append(f"{label} not restored: {problem}")
            elif wanted != (found.get(field_name) or {}).get("id"):
                changes[key] = wanted
                words.append(label)
        if str(item["id"]) != str(found["id"]):
            warnings.append("the original was deleted; this one has the same address and Remote Network and is taken to be it")
        steps = [Step(w.UPDATE_GATEWAY, {"id": found["id"], **changes}, "gatewayUpdate")] if changes else []
        plan.rows.append(Row(
            "gateway", item.get("address") or str(item["id"]), UPDATE if changes else EXISTS, spec, "; ".join(words) if words else "no changes",
            warnings, found["id"], steps=steps, backup_id=str(item["id"]),
        ))
    addresses = [g.get("address") for g in to_create]
    for item in to_create:
        spec = _item("gateways.json", item)
        label = item.get("address") or str(item["id"])
        problems: list = []
        if addresses.count(item.get("address")) > 1:
            problems.append("more than one deleted Gateway had this address, so they cannot be told apart")
        target = _network_target(item, networks, creating, current_networks)
        if target is None:
            problems.append(f"Remote Network '{_network_name(item)}' no longer exists")
        x509, problem = _resolve_ca(cas, item.get("x509CA"))
        if problem:
            problems.append(problem)
        ssh, problem = _resolve_ca(cas, item.get("sshCA"))
        if problem:
            problems.append(problem)
        if not item.get("x509CA"):
            problems.append("the backup does not say which X.509 certificate authority it used")
        if problems:
            plan.rows.append(Row("gateway", label, BLOCKED, spec, "; ".join(problems), backup_id=str(item["id"])))
            continue
        variables = {"address": item["address"], "remoteNetworkId": target[1] if target[0] == "id" else Ref("network", target[1]), "x509CAId": x509}
        if ssh:
            variables["sshCAId"] = ssh
        refs.new_gateways[str(item["id"])] = Ref("gateway", item["address"])
        plan.rows.append(Row(
            "gateway", label, CREATE, spec, f"deleted since the backup; in '{_network_name(item)}'",
            ["its Connectors-side setup (the Gateway deployment itself) is not touched: it needs the new Gateway to be deployed again"],
            steps=[Step(w.CREATE_GATEWAY, variables, "gatewayCreate", remember=("gateway", item["address"]))], backup_id=str(item["id"]),
        ))
    for item in ambiguous:
        plan.rows.append(Row("gateway", item.get("address") or str(item["id"]), BLOCKED, _item("gateways.json", item), "its ID is gone and more than one Gateway has this address and Remote Network, so which one it is cannot be told", backup_id=str(item["id"])))


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
        if spec.kind == SERVICE_ACCOUNT and str(principal.get("id")) in refs.new_service_accounts:
            pass  # made again by this restore: its ID is known when the grant is given
        elif spec.kind == SERVICE_ACCOUNT:
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


def _plan_approvers(item: dict, found: Optional[dict], groups: dict, current_groups: list, known_groups: set, prune: bool) -> tuple:
    """(approver group IDs or Refs to add, IDs to remove, warnings) for one backup resource. ``found`` is None when it is being created."""
    wanted: list = []
    warnings: list = []
    for ref in item.get("approverGroups") or []:
        where = groups.get(str(ref.get("id")))
        if where is None and str(ref.get("id")) not in known_groups:
            by_name = [g for g in current_groups if g.get("name") == ref.get("name")]
            where = ("id", by_name[0]["id"]) if len(by_name) == 1 else None
        if where is None:
            warnings.append(f"approver group '{ref.get('name') or ref.get('id')}' not restored: the group no longer exists and cannot be created again")
            continue
        wanted.append(where[1] if where[0] == "id" else Ref("group", where[1]))
    have = {str(g["id"]) for g in (found or {}).get("approverGroups") or []}
    add = [w for w in wanted if isinstance(w, Ref) or str(w) not in have]
    remove: list = []
    if prune and found is not None and "approverGroups" in item:
        keep = {str(w) for w in wanted if not isinstance(w, Ref)}
        remove = sorted(str(i) for i in have if i not in keep)
    return add, remove, warnings


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
        supported = item.get("type") == found.get("type") and item.get("type") in RESOURCE_TYPES
        if supported:
            if spec.problems:
                plan.rows.append(Row("resource", _name(item), BLOCKED, spec, "; ".join(spec.problems), backup_id=str(item["id"])))
                continue
            policy_id, problem = refs.policy(item.get("securityPolicy"))
            if problem:
                warnings.append(f"Security Policy not restored: {problem}")
                policy_id = (found.get("securityPolicy") or {}).get("id")
            changes, words = resource_changes(spec, found, policy_id, prune)
            if spec.type != NETWORK_RESOURCE:
                gateway_id, problem = refs.gateway(item.get("gateway"))
                if problem:
                    warnings.append(f"Gateway not restored: {problem}")
                    gateway_id = (found.get("gateway") or {}).get("id")
                more, more_words = gateway_resource_changes(spec, found, gateway_id, prune)
                changes, words = {**changes, **more}, words + more_words
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
            warnings.append(f"{item.get('type')} resource: only its access is restored, not its settings (it is {found.get('type')} now)")
        approvers_add, approvers_remove, approver_warnings = _plan_approvers(item, found, groups, current_groups, known_groups, prune)
        warnings.extend(approver_warnings)
        if approvers_add:
            words.append(f"{_plural(len(approvers_add), 'approver group')} to add")
        if approvers_remove:
            words.append(f"{_plural(len(approvers_remove), 'approver group')} to remove")
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
            move_to_network=move, backup_id=str(item["id"]), approvers_add=approvers_add, approvers_remove=approvers_remove,
        ))
    for item in to_create:
        source = _source("resources.json", item)
        spec = _resource(item, source)
        if item.get("type") not in RESOURCE_TYPES:
            plan.rows.append(Row("resource", _name(item), SKIP, spec, f"deleted since the backup; {item.get('type')} resources are not created again", backup_id=str(item["id"])))
            continue
        problems = list(spec.problems)
        gateway_id, problem = refs.gateway(item.get("gateway")) if spec.type != NETWORK_RESOURCE else (None, None)
        if problem:
            problems.append(problem)
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
        approvers_add, _, approver_warnings = _plan_approvers(item, None, groups, current_groups, known_groups, False)
        update = {"isActive": False} if item.get("isActive") is False else {}
        kind = "" if spec.type == NETWORK_RESOURCE else f"{spec.type.replace('_', ' ').lower()} resource, "
        plan.rows.append(Row(
            "resource", spec.name, CREATE, spec, f"deleted since the backup; {kind}in '{spec.network}', access for {_grant_words(grants)}",
            [*_notes(spec), *warnings, *approver_warnings], policy_id=policy_id, gateway_id=gateway_id, approvers_add=approvers_add,
            network_id=target[1] if target[0] == "id" else None, grants=grants, resource_update=update, backup_id=str(item["id"]),
        ))
    for item in ambiguous:
        spec = _resource(item, _source("resources.json", item))
        plan.rows.append(Row("resource", _name(item), BLOCKED, spec, "its ID is gone and more than one resource has this name, Remote Network and address, so which one it is cannot be told", backup_id=str(item["id"])))


# ---------------------------------------------------------------- connectors


def _plan_connectors(backup: list, current: list, networks: dict, creating: dict, current_networks: list, plan: Plan) -> None:
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda c: (_name(c), _network_name(c)))
    plan.created_after["Connectors"] = len(extra)
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None:
            continue
        changes: dict = {}
        words: list = []
        warnings: list = []
        if _name(item) != _name(found):
            changes["name"] = _name(item)
            words.append(f"rename from '{_name(found)}'")
        wanted = item.get("hasStatusNotificationsEnabled")
        if wanted is not None and wanted != found.get("hasStatusNotificationsEnabled"):
            changes["hasStatusNotificationsEnabled"] = wanted
            words.append("status notifications " + ("on" if wanted else "off"))
        target = _network_target(item, networks, creating, current_networks)
        if target is not None and (target[0] == "new" or target[1] != (found.get("remoteNetwork") or {}).get("id")):
            warnings.append(f"it is in Remote Network '{_network_name(found)}' now and was in '{_network_name(item)}'; the API cannot move a Connector")
        if str(item["id"]) != str(found["id"]):
            warnings.append("the original was deleted; this one has the same name and Remote Network and is taken to be it")
        steps = [Step(w.UPDATE_CONNECTOR, {"id": found["id"], **changes}, "connectorUpdate")] if changes else []
        plan.rows.append(Row(
            "connector", _name(item), UPDATE if changes else EXISTS, _item("connectors.json", item), "; ".join(words) if words else "no changes",
            warnings, found["id"], steps=steps, backup_id=str(item["id"]),
        ))
    names = [(_name(c), _network_name(c)) for c in to_create]
    for item in to_create:
        spec = _item("connectors.json", item)
        target = _network_target(item, networks, creating, current_networks)
        if names.count((_name(item), _network_name(item))) > 1:
            plan.rows.append(Row("connector", _name(item), BLOCKED, spec, "more than one deleted Connector had this name in this Remote Network, so they cannot be told apart", backup_id=str(item["id"])))
        elif target is None:
            plan.rows.append(Row("connector", _name(item), BLOCKED, spec, f"Remote Network '{_network_name(item)}' no longer exists", backup_id=str(item["id"])))
        else:
            variables = {"name": _name(item), "remoteNetworkId": target[1] if target[0] == "id" else Ref("network", target[1])}
            if item.get("hasStatusNotificationsEnabled") is not None:
                variables["hasStatusNotificationsEnabled"] = item["hasStatusNotificationsEnabled"]
            plan.rows.append(Row(
                "connector", _name(item), CREATE, spec, f"deleted since the backup; in '{_network_name(item)}'",
                ["a Connector made again is a new, empty Connector: it needs tokens (`tgcli connector generate-tokens`) and has to be deployed again"],
                steps=[Step(w.CREATE_CONNECTOR, variables, "connectorCreate", remember=("connector", _name(item)))], backup_id=str(item["id"]),
            ))
    for item in ambiguous:
        plan.rows.append(Row("connector", _name(item), BLOCKED, _item("connectors.json", item), "its ID is gone and more than one Connector has this name in this Remote Network, so which one it is cannot be told", backup_id=str(item["id"])))


# ---------------------------------------------------------------- DNS filtering profiles

CATEGORY_CONFIGS = ("contentCategoryConfig", "securityCategoryConfig", "privacyCategoryConfig")


def _profile_groups(item: dict, groups: dict, current_groups: list, known_groups: set) -> tuple:
    """(group IDs or Refs the backup assigned the profile to, warnings)."""
    wanted: list = []
    warnings: list = []
    for ref in item.get("groups") or []:
        where = groups.get(str(ref.get("id")))
        if where is None and str(ref.get("id")) not in known_groups:
            by_name = [g for g in current_groups if g.get("name") == ref.get("name")]
            where = ("id", by_name[0]["id"]) if len(by_name) == 1 else None
        if where is None:
            warnings.append(f"group '{ref.get('name') or ref.get('id')}' not put back on the profile: it no longer exists and cannot be created again")
            continue
        wanted.append(where[1] if where[0] == "id" else Ref("group", where[1]))
    return wanted, warnings


def _profile_changes(item: dict, found: Optional[dict], groups: dict, current_groups: list, known_groups: set, prune: bool) -> tuple:
    """(variables for dnsFilteringProfileUpdate without the ID, words, warnings). ``found`` is None for a profile that is being made again.

    The API replaces a list as a whole, so without ``prune`` the domains and groups the profile has now are sent along with the backup's.
    """
    changes: dict = {}
    words: list = []
    have = found or {}
    if _name(item) != _name(have) and found is not None:
        changes["name"] = _name(item)
        words.append(f"rename from '{_name(have)}'")
    for key, label in (("priority", "priority"), ("fallbackMethod", "fallback method")):
        if item.get(key) is not None and item[key] != have.get(key):
            changes[key] = item[key]
            words.append(label)
    for key, label in (("allowedDomains", "allowed domains"), ("deniedDomains", "denied domains")):
        if key not in item:
            continue
        now = list(have.get(key) or [])
        wanted = list(item[key] or [])
        merged = wanted if prune else [*now, *(d for d in wanted if d not in now)]
        if set(merged) != set(now):
            changes[key] = merged
            words.append(label)
    for key in CATEGORY_CONFIGS:
        if item.get(key) and item[key] != have.get(key):
            changes[key] = {k: v for k, v in item[key].items() if v is not None}
            words.append(key.replace("CategoryConfig", " categories"))
    wanted_groups, warnings = _profile_groups(item, groups, current_groups, known_groups)
    if "groups" in item:
        now_groups = [str(g["id"]) for g in have.get("groups") or []]
        kept = {str(g) for g in wanted_groups if not isinstance(g, Ref)}
        missing = [g for g in wanted_groups if isinstance(g, Ref) or str(g) not in now_groups]
        extra = [g for g in now_groups if g not in kept]
        if prune and (missing or extra):
            changes["groups"] = wanted_groups
        elif not prune and missing:
            changes["groups"] = [*now_groups, *missing]
        if "groups" in changes:
            words.append("groups")
    return changes, words, warnings


def _plan_dns_profiles(backup: list, current: list, groups: dict, current_groups: list, backup_groups: list, plan: Plan, prune: bool) -> None:
    pairs, to_create, ambiguous, extra = _pair(backup, current, lambda p: _name(p))
    plan.created_after["DNS profiles"] = len(extra)
    known_groups = {str(g["id"]) for g in backup_groups}
    for item in backup:
        found = pairs.get(str(item["id"]))
        if found is None:
            continue
        changes, words, warnings = _profile_changes(item, found, groups, current_groups, known_groups, prune)
        if str(item["id"]) != str(found["id"]):
            warnings.append("the original was deleted; this one has the same name and is taken to be it")
        steps = [Step(w.UPDATE_DNS_PROFILE, {"id": found["id"], **changes}, "dnsFilteringProfileUpdate")] if changes else []
        plan.rows.append(Row(
            "dns profile", _name(item), UPDATE if changes else EXISTS, _item("dns-profiles.json", item), "; ".join(words) if words else "no changes",
            warnings, found["id"], steps=steps, backup_id=str(item["id"]),
        ))
    names = [_name(p) for p in to_create]
    for item in to_create:
        spec = _item("dns-profiles.json", item)
        if names.count(_name(item)) > 1:
            plan.rows.append(Row("dns profile", _name(item), BLOCKED, spec, "more than one deleted profile had this name, so they cannot be told apart", backup_id=str(item["id"])))
            continue
        changes, words, warnings = _profile_changes(item, None, groups, current_groups, known_groups, prune)
        handle = Ref("dns profile", _name(item))
        steps = [Step(w.CREATE_DNS_PROFILE, {"name": _name(item)}, "dnsFilteringProfileCreate", remember=("dns profile", _name(item)))]
        if changes:
            steps.append(Step(w.UPDATE_DNS_PROFILE, {"id": handle, **changes}, "dnsFilteringProfileUpdate"))
        plan.rows.append(Row("dns profile", _name(item), CREATE, spec, "deleted since the backup; " + (", ".join(words) if words else "default settings"), warnings, steps=steps, backup_id=str(item["id"])))
    for item in ambiguous:
        plan.rows.append(Row("dns profile", _name(item), BLOCKED, _item("dns-profiles.json", item), "its ID is gone and more than one profile has this name, so which one it is cannot be told", backup_id=str(item["id"])))


# ---------------------------------------------------------------- devices and roles (only when asked for)


def _plan_devices(backup: list, current: list, plan: Plan, include: frozenset) -> None:
    """Put a device's trust and blocked / archived state back. A device that is gone registers again when its user signs in."""
    now = _by_id(current)
    gone = 0
    differing: list = []
    for item in backup:
        found = now.get(str(item["id"]))
        if found is None:
            gone += 1
            continue
        steps: list = []
        words: list = []
        if item.get("isTrusted") is not None and item["isTrusted"] != found.get("isTrusted"):
            steps.append(Step(w.UPDATE_DEVICE_TRUST, {"id": found["id"], "isTrusted": item["isTrusted"]}, "deviceUpdate"))
            words.append("trusted" if item["isTrusted"] else "untrusted")
        moves = w.DEVICE_MOVES.get((found.get("activeState"), item.get("activeState")), ())
        for move in moves:
            steps.append(Step(w.DEVICE_STATE[move], {"id": found["id"]}, w.DEVICE_STATE_FIELD[move]))
        if moves:
            words.append(f"{found.get('activeState', '?').lower()} to {item['activeState'].lower()}")
        if steps:
            differing.append((item, found, steps, words))
    if gone:
        plan.left_alone.append(f"{_plural(gone, 'device')} in the backup no longer exist (a device registers again when its user signs in, so restore cannot make one)")
    if differing and "devices" not in include:
        plan.left_alone.append(
            f"{_plural(len(differing), 'device')} differ from the backup in trust or blocked / archived state; this undoes security decisions made since, so add `--include devices` to restore them"
        )
        return
    for item, found, steps, words in differing:
        plan.rows.append(Row(
            "device", _name(item), UPDATE, _item("devices.json", item), "; ".join(words), [], found["id"], steps=steps, backup_id=str(item["id"]),
        ))


def _plan_roles(backup: list, current: list, plan: Plan, include: frozenset) -> None:
    """Put a user's role back. Users come from the identity provider, so one that is gone is found again by email."""
    pairs, _, _, _ = _pair(backup, current, lambda u: (u.get("email") or "").lower())
    differing = [(item, pairs[str(item["id"])]) for item in backup if str(item["id"]) in pairs and item.get("role") and item["role"] != pairs[str(item["id"])].get("role")]
    if differing and "roles" not in include:
        plan.left_alone.append(
            f"{_plural(len(differing), 'user')} have another role than in the backup; this undoes changes made since, so add `--include roles` to restore them"
        )
        return
    for item, found in differing:
        warnings = ["this makes the user an administrator"] if item["role"] == "ADMIN" else []
        plan.rows.append(Row(
            "user", item.get("email") or _name(item), UPDATE, _item("users.json", item), f"role {found.get('role')} to {item['role']}", warnings, found["id"],
            steps=[Step(w.UPDATE_USER_ROLE, {"id": found["id"], "role": item["role"]}, "userRoleUpdate")], backup_id=str(item["id"]),
        ))


# ---------------------------------------------------------------- the plan


def build_plan(backup: Backup, current: dict, prune: bool = False, include: frozenset = frozenset()) -> Plan:
    """Every difference between what the backup holds and what the tenant holds now, as importer Rows (networks, groups, resources).

    ``current`` is the tenant read the way a backup reads it (entity key -> items). A type missing from it could not be read.
    ``include`` names the opt-in kinds to restore as well (``devices``, ``roles``).
    """
    plan = Plan()
    for entity in q.ENTITIES:
        in_backup = entity.key in backup.items
        if entity.key in SUPPORTED:
            if not in_backup:
                plan.not_compared.append(f"{entity.label} (not in this backup)")
            elif entity.key not in current:
                plan.not_compared.append(f"{entity.label} (could not be read from the tenant)")
        elif entity.key in ("devices", "users"):
            if not in_backup:
                plan.not_compared.append(f"{entity.label} (not in this backup)")
            elif entity.key not in current:
                plan.not_compared.append(f"{entity.label} (could not be read from the tenant)")
        elif entity.key == "security_policies":
            plan.not_compared.append(
                f"{entity.label} (a group's own policy is restored with the group; the API cannot make a policy, so a deleted one is only named)"
                if in_backup else f"{entity.label} (not in this backup)"
            )
        elif entity.key == "certificate_authorities":
            plan.not_compared.append(
                f"{entity.label} (a deleted one can only be made again from its certificate file, with `tgcli ca create`)"
                if in_backup else f"{entity.label} (not in this backup)"
            )
        else:
            plan.not_compared.append(f"{entity.label} ({'restore does not cover them yet' if in_backup else 'not in this backup'})")
    if "security_policies" in backup.items and "security_policies" in current:
        now = current["security_policies"]
        lost = [p for p in backup.items["security_policies"] if not any(str(p["id"]) == str(c["id"]) or p.get("name") == c.get("name") for c in now)]
        if lost:
            plan.left_alone.append(
                f"{_plural(len(lost), 'Security Policy')} in the backup no longer exist ({', '.join(str(p.get('name')) for p in lost[:5])}); "
                "the API cannot make a policy, so create it again in the Admin Console. Groups and resources that used it are reported as blocked or left without it"
            )

    refs = _Refs(current)
    networks, creating = {}, {}
    if "remote_networks" in backup.items and "remote_networks" in current:
        networks, creating = _plan_networks(backup.items["remote_networks"], current["remote_networks"], plan)
    groups: dict = {}
    if "groups" in backup.items and "groups" in current:
        groups = _plan_groups(backup.items["groups"], current["groups"], refs, plan, prune)
    if "service_accounts" in backup.items and "service_accounts" in current:
        _plan_service_accounts(backup.items["service_accounts"], current["service_accounts"], refs, plan)
    if "gateways" in backup.items and "gateways" in current:
        _plan_gateways(backup.items["gateways"], current["gateways"], refs, networks, creating, current.get("remote_networks", []), plan)
    if "connectors" in backup.items and "connectors" in current:
        _plan_connectors(backup.items["connectors"], current["connectors"], networks, creating, current.get("remote_networks", []), plan)
    if "resources" in backup.items and "resources" in current:
        _plan_resources(
            backup.items["resources"], current["resources"], refs, networks, creating, groups, current.get("groups", []),
            backup.items.get("groups", []), current.get("remote_networks", []), plan, prune,
        )
    if "dns_profiles" in backup.items and "dns_profiles" in current:
        _plan_dns_profiles(backup.items["dns_profiles"], current["dns_profiles"], groups, current.get("groups", []), backup.items.get("groups", []), plan, prune)
    if "devices" in backup.items and "devices" in current:
        _plan_devices(backup.items["devices"], current["devices"], plan, include)
    if "users" in backup.items and "users" in current:
        _plan_roles(backup.items["users"], current["users"], plan, include)
    return plan
