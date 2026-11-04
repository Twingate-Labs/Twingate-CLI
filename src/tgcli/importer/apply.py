"""Carry out a plan against the tenant: Remote Networks, then groups and their members, then resources and their access.

Within a row, things are added or changed before anything is removed, so a run that stops part way never leaves less access
than the file describes.

One row failing never stops the others (the report says which failed), with one exception: when the API rejects the
credentials there is no point trying the rest, so the remaining rows are marked not-run.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.importer.load import NETWORK_RESOURCE, SERVICE_ACCOUNT
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, SKIP, UPDATE, Grant, Ref, Row
from tgcli.queries import importing as q

BATCH_SIZE = 200  # users per groupUpdate
ACCESS_BATCH = 100  # grants per resourceAccessAdd (and principals per resourceAccessRemove)

DRY_RUN_STATUS = {CREATE: "would-create", UPDATE: "would-update", EXISTS: "exists", SKIP: "skipped", BLOCKED: "blocked"}
DONE_STATUS = {CREATE: "created", UPDATE: "updated", EXISTS: "exists", SKIP: "skipped", BLOCKED: "blocked"}


def write_count(rows: list) -> int:
    """How many write requests applying these rows makes (the API rate-limits writes, so a big import takes a while)."""
    total = 0
    for row in rows:
        if row.action not in (CREATE, UPDATE):
            continue
        if row.steps:
            total += len(row.steps) + -(-(len(row.grants) + len(row.grant_updates)) // ACCESS_BATCH)
        elif row.kind == "remote network":
            total += 1
        elif row.kind == "device":
            total += len(row.device_ids)
        elif row.kind == "group":
            total += (row.action == CREATE) + -(-len(row.member_ids) // BATCH_SIZE) + _sync_group_calls(row)
        else:
            total += (row.action == CREATE) + bool(row.resource_update or row.move_to_network or row.approvers_add or row.approvers_remove)
            total += -(-(len(row.grants) + len(row.grant_updates)) // ACCESS_BATCH)
            total += -(-len(row.remove_access_ids) // ACCESS_BATCH)
    return total


def _sync_group_calls(row: Row) -> int:
    """A group's Security Policy change rides with its first batch of removals; with none it is a call of its own."""
    return max(-(-len(row.remove_member_ids) // BATCH_SIZE), 1 if row.group_policy_id or row.group_update else 0)


class RowError(Exception):
    """A write the API refused (ok: false), or that could only be partly done."""


def _call(client: Any, query: str, variables: dict, field: str) -> dict:
    result = client.execute(query, variables)["data"][field]
    if not result["ok"]:
        raise RowError((result["error"] or "").strip() or f"{field} was refused without a reason")
    return result


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def resolve(value: Any, ids: dict) -> Any:
    """``value`` with every Ref in it (however deeply) replaced by the ID of the object this run created."""
    if isinstance(value, Ref):
        found = ids.get(value.kind, {}).get(value.name)
        if found is None:
            raise RowError(f"the {value.kind} '{value.name}' was not created, so this cannot be done")
        return found
    if isinstance(value, dict):
        return {k: resolve(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, ids) for v in value]
    return value


def _run_steps(client: Any, row: Row, ids: dict) -> None:
    """Carry out a row's own writes in order. The first object a step creates is the row's ID."""
    for step in row.steps:
        result = _call(client, step.query, resolve(step.variables, ids), step.field)
        entity_id = (result.get("entity") or {}).get("id")
        if step.remember:
            if not entity_id:
                raise RowError(f"{step.field} succeeded but did not say what it created")
            ids.setdefault(step.remember[0], {})[step.remember[1]] = entity_id
            row.id = row.id or entity_id


def _approver_variables(row: Row, ids: dict, create: bool) -> dict:
    """The approver groups to set on a resource: all of them when it is created, the ones to add and to take out when it exists."""
    if create:
        return {"approverGroupIds": resolve(row.approvers_add, ids)} if row.approvers_add else {}
    out: dict = {}
    if row.approvers_add:
        out["addedApproverGroupIds"] = resolve(row.approvers_add, ids)
    if row.approvers_remove:
        out["removedApproverGroupIds"] = resolve(row.approvers_remove, ids)
    return out


def _grant_input(grant: Grant, group_id: str) -> dict:
    entry: dict = {"principalId": group_id}
    if grant.kind == SERVICE_ACCOUNT:
        return entry  # the API refuses every setting on a service account's grant, even a default one
    if grant.policy_id:
        entry["securityPolicyId"] = grant.policy_id
    if grant.access_policy:
        entry["accessPolicy"] = grant.access_policy
    if grant.approval_mode:
        entry["approvalMode"] = grant.approval_mode
    if grant.expires_at:
        entry["expiresAt"] = grant.expires_at
    return entry


def _add_members(client: Any, row: Row, group_id: str) -> None:
    done = 0
    for chunk in _chunks(row.member_ids, BATCH_SIZE):
        try:
            _call(client, q.ADD_GROUP_USERS, {"id": group_id, "userIds": chunk}, "groupUpdate")
        except (RowError, TwingateAPIError) as exc:
            raise RowError(f"added {done} of {len(row.member_ids)} members, then: {exc}. Run the import again to add the rest.") from exc
        done += len(chunk)


def _sync_group(client: Any, row: Row, group_id: str) -> None:
    """Change an existing group's Security Policy and take out the members the file leaves out."""
    chunks = list(_chunks(row.remove_member_ids, BATCH_SIZE)) or [[]]
    done = 0
    for index, chunk in enumerate(chunks):
        variables: dict = {"id": group_id}
        if index == 0:
            variables.update(row.group_update)
            if row.group_policy_id:
                variables["securityPolicyId"] = row.group_policy_id
        if chunk:
            variables["removedUserIds"] = chunk
        try:
            _call(client, q.SYNC_GROUP, variables, "groupUpdate")
        except (RowError, TwingateAPIError) as exc:
            raise RowError(f"removed {done} of {len(row.remove_member_ids)} members, then: {exc}. Run the import again to finish.") from exc
        done += len(chunk)


def _update_resource(client: Any, row: Row, resource_id: str, ids: Optional[dict] = None, approvers: bool = True) -> None:
    kind = row.spec.type
    variables = {"id": resource_id, **resolve(row.resource_update, ids or {}), **(_approver_variables(row, ids or {}, False) if approvers else {})}
    if kind == NETWORK_RESOURCE:
        _call(client, q.UPDATE_RESOURCE, variables, "resourceUpdate")
    else:  # an SSH, web app or Kubernetes resource is changed by its own mutation
        _call(client, q.UPDATE_TYPED[kind], variables, q.UPDATE_TYPED_FIELD[kind])


def _remove_access(client: Any, row: Row, resource_id: str) -> None:
    done = 0
    for chunk in _chunks(row.remove_access_ids, ACCESS_BATCH):
        try:
            _call(client, q.REMOVE_RESOURCE_ACCESS, {"id": resource_id, "principalIds": chunk}, "resourceAccessRemove")
        except (RowError, TwingateAPIError) as exc:
            raise RowError(f"removed access for {done} of {len(row.remove_access_ids)} principals, then: {exc}. Run the import again to finish.") from exc
        done += len(chunk)


def _add_access(client: Any, row: Row, resource_id: str, group_ids: dict, account_ids: Optional[dict] = None) -> None:
    grants = []
    for grant in row.grants + row.grant_updates:
        group_id = grant.group_id or (account_ids if grant.kind == SERVICE_ACCOUNT else group_ids or {}).get(grant.group)
        if group_id is None:
            what = "service account" if grant.kind == SERVICE_ACCOUNT else "group"
            row.warnings.append(f"access for {what} '{grant.group}' not added: the {what} was not created")
        else:
            grants.append(_grant_input(grant, group_id))
    who = "groups" if all(g.kind != SERVICE_ACCOUNT for g in row.grants) else "groups and service accounts"
    did = "added or changed access" if row.grant_updates else "added access"
    done = 0
    for chunk in _chunks(grants, ACCESS_BATCH):
        try:
            _call(client, q.ADD_RESOURCE_ACCESS, {"id": resource_id, "access": chunk}, "resourceAccessAdd")
        except (RowError, TwingateAPIError) as exc:
            raise RowError(f"{did} for {done} of {len(grants)} {who}, then: {exc}. Run the import again to add the rest.") from exc
        done += len(chunk)


def _resource_variables(row: Row, network_id: str) -> dict:
    spec = row.spec
    variables: dict = {
        "name": spec.name, "address": spec.address, "remoteNetworkId": network_id,
        "protocols": {
            "allowIcmp": spec.protocols["allowIcmp"],
            "tcp": spec.protocols["tcp"],
            "udp": spec.protocols["udp"],
        },
    }
    # Only what the file sets away from the API's defaults is sent.
    if spec.alias:
        variables["alias"] = spec.alias
    if row.policy_id:
        variables["securityPolicyId"] = row.policy_id
    if not spec.is_visible:
        variables["isVisible"] = False
    if "browser_shortcut" in spec.given or spec.browser_shortcut:
        variables["isBrowserShortcutEnabled"] = spec.browser_shortcut  # the API's own default is True, so a stated False must be sent
    if spec.routing_mode == "BYPASS_TWINGATE":
        variables["routingMode"] = "BYPASS_TWINGATE"
    if spec.tags:
        variables["tags"] = spec.tags
    if spec.access_policy:
        variables["accessPolicy"] = spec.access_policy
    if spec.approval_mode:
        variables["approvalMode"] = spec.approval_mode
    return variables


def _typed_variables(row: Row, network_id: str) -> dict:
    """What creates an SSH, web app or Kubernetes resource. Like a network resource, only what the file sets away from the defaults is sent."""
    spec = row.spec
    variables: dict = {"name": spec.name, "address": spec.address, "remoteNetworkId": network_id}
    if row.gateway_id:
        variables["gatewayId"] = row.gateway_id
    if spec.alias:
        variables["alias"] = spec.alias
    if row.policy_id:
        variables["securityPolicyId"] = row.policy_id
    if not spec.is_visible:
        variables["isVisible"] = False
    if spec.tags:
        variables["tags"] = spec.tags
    if spec.access_policy:
        variables["accessPolicy"] = spec.access_policy
    if spec.approval_mode:
        variables["approvalMode"] = spec.approval_mode
    for side in ("upstream", "downstream"):
        if getattr(spec, side):
            variables[side] = getattr(spec, side)
    if spec.cluster_ref:
        variables["clusterRef"] = spec.cluster_ref
    if spec.headers:
        variables["requestHeaderRewrites"] = spec.headers
    return variables


def _set_trust(client: Any, row: Row) -> None:
    """Change each device in turn, and check the reply says it now has the trust the file asks for."""
    wanted = row.spec.trusted
    done = 0
    for device_id in row.device_ids:
        try:
            result = _call(client, q.UPDATE_DEVICE_TRUST, {"id": device_id, "isTrusted": wanted}, "deviceUpdate")
            if (result.get("entity") or {}).get("isTrusted") is not wanted:
                raise RowError("the API accepted the change but the device is still " + ("untrusted" if wanted else "trusted"))
        except (RowError, TwingateAPIError) as exc:
            raise RowError(f"changed {done} of {len(row.device_ids)} devices, then: {exc}. Run the import again to finish.") from exc
        done += 1
    row.id = ", ".join(row.device_ids)


def _apply_row(client: Any, row: Row, ids: dict) -> None:
    spec = row.spec
    if row.steps:
        _run_steps(client, row, ids)
    elif row.kind == "device":
        _set_trust(client, row)
    elif row.kind == "remote network":
        if row.action == CREATE:
            result = _call(client, q.CREATE_NETWORK, {
                "name": spec.name, "location": spec.location, "networkType": spec.network_type, "isActive": spec.is_active,
            }, "remoteNetworkCreate")
            row.id = ids["network"][spec.name] = result["entity"]["id"]
        else:
            row.id = row.existing_id
            _call(client, q.UPDATE_NETWORK, {"id": row.id, **row.network_update}, "remoteNetworkUpdate")
    elif row.kind == "group":
        if row.action == CREATE:
            variables = {"name": spec.name}
            if row.policy_id:
                variables["securityPolicyId"] = row.policy_id
            row.id = ids["group"][spec.name] = _call(client, q.CREATE_GROUP, variables, "groupCreate")["entity"]["id"]
        else:
            row.id = row.existing_id
        _add_members(client, row, row.id)
        if row.group_policy_id or row.remove_member_ids or row.group_update:
            _sync_group(client, row, row.id)
    else:
        if row.action == CREATE:
            network_id = row.network_id or ids["network"].get(spec.network)
            if network_id is None:
                raise RowError(f"Remote Network '{spec.network}' was not created")
            if spec.type == NETWORK_RESOURCE:
                result = _call(client, q.CREATE_RESOURCE, {**_resource_variables(row, network_id), **_approver_variables(row, ids, True)}, "resourceCreate")
            else:
                variables = {**_typed_variables(row, network_id), **_approver_variables(row, ids, True)}
                result = _call(client, q.CREATE_TYPED[spec.type], resolve(variables, ids), q.CREATE_TYPED_FIELD[spec.type])
            row.id = result["entity"]["id"]
            if row.resource_update:  # what a create cannot say (a restore puts back a disabled resource); the approvers went with the create
                _update_resource(client, row, row.id, ids, approvers=False)
        else:
            row.id = row.existing_id
            if row.move_to_network:
                moved_to = ids["network"].get(row.move_to_network)
                if moved_to is None:
                    raise RowError(f"Remote Network '{row.move_to_network}' was not created")
                row.resource_update["remoteNetworkId"] = moved_to
            if row.resource_update or row.approvers_add or row.approvers_remove:
                _update_resource(client, row, row.id, ids)
        if row.grants or row.grant_updates:
            _add_access(client, row, row.id, ids["group"], ids["service account"])
        if row.remove_access_ids:
            _remove_access(client, row, row.id)


def apply_plan(client: Any, rows: list, progress: Callable[[Row], None] = lambda row: None) -> None:
    """Set ``status`` (and ``id`` / ``error``) on every row; rows that have nothing to do are not sent anywhere."""
    ids: dict = {"network": {}, "group": {}, "service account": {}, "gateway": {}}
    stop = False
    for row in rows:
        row.status = DONE_STATUS[row.action]
        if row.action in (EXISTS, SKIP, BLOCKED):
            continue
        if stop:
            row.status, row.error = "not-run", "not attempted: the API rejected the credentials earlier in this run"
            continue
        try:
            _apply_row(client, row, ids)
        except TwingateAuthError as exc:
            row.status, row.error, stop = "error", f"authentication error: {exc}", True
        except (RowError, TwingateAPIError) as exc:
            row.status, row.error = "error", str(exc)
        except Exception as exc:  # a reply of an unexpected shape must not lose the report of what was already done
            row.status, row.error = "error", f"unexpected {type(exc).__name__}: {exc}"
        progress(row)
