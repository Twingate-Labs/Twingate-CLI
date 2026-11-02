"""Decide what `tgcli remove` would delete, and delete it. The planner is pure: no API calls, nothing written.

`remove` takes a file that names resources, groups and Remote Networks and removes exactly those. It is the most dangerous
thing the CLI does, so the rules are strict:
  * only what the file names is removed, and each line must match exactly one object. A name that matches several
    objects, an ID whose object has a different name than the line says, or a file line that cannot be read is BLOCKED,
    never guessed. If any line is blocked nothing at all is removed (the command checks, see commands/remove.py).
  * Synced Groups (and the System group) are never removed: they belong to the identity provider.
  * a Remote Network is removed only when everything in it goes too: a resource that is not in the file, a Connector or a
    Gateway still in it blocks it. (The Connector is not a thing this command removes, so it is never taken along silently.)
  * a line whose object is not there (already removed, or a typo) is reported as "not found" and skipped, so a run that
    stopped half way can simply be run again.
  * every row says what hangs off the object, so the list the user confirms shows the consequences.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from tgcli.client.exceptions import TwingateAPIError
from tgcli.queries import groups as group_queries
from tgcli.queries import networks as network_queries
from tgcli.queries import resources as resource_queries
from tgcli.textio import TextFileError, read_text

RESOURCE, GROUP, NETWORK = "resource", "group", "remote network"
KINDS = (RESOURCE, GROUP, NETWORK)
ORDER = (RESOURCE, GROUP, NETWORK)  # a Remote Network can only go once its resources have
ALIASES = {
    "resource": RESOURCE, "resources": RESOURCE, "group": GROUP, "groups": GROUP,
    "network": NETWORK, "networks": NETWORK, "remote network": NETWORK, "remote networks": NETWORK,
    "remote-network": NETWORK, "remote_network": NETWORK, "remotenetwork": NETWORK, "remote-networks": NETWORK,
}
ITEM_KEYS = {RESOURCE: "resources", GROUP: "groups", NETWORK: "remote_networks"}
READ_KEYS = frozenset({"groups", "resources", "remote_networks", "users", "security_policies", "service_accounts"})

REMOVE, SKIP, BLOCKED = "remove", "skip", "blocked"
REMOVED, ERROR, NOT_RUN = "removed", "error", "not-run"
DRY_RUN_STATUS = {REMOVE: "would-remove", SKIP: "not-found", BLOCKED: "blocked"}
MUTATIONS = {RESOURCE: resource_queries.DELETE_RESOURCE, GROUP: group_queries.DELETE_GROUP, NETWORK: network_queries.DELETE_NETWORK}
VARIABLE = {RESOURCE: "id", GROUP: "groupId", NETWORK: "id"}
RESULT_FIELD = {RESOURCE: "resourceDelete", GROUP: "groupDelete", NETWORK: "remoteNetworkDelete"}


class LoadError(Exception):
    """The file cannot be read as a list of things to remove."""


@dataclass
class Target:
    """One line of the file: which kind of object, and how it is identified. ``problems`` means the line cannot be used."""

    kind: str
    id: str = ""
    name: str = ""
    network: str = ""  # resources only: narrows a name that is used in several Remote Networks
    address: str = ""  # resources only: likewise
    source: str = ""
    problems: list = field(default_factory=list)


@dataclass
class Row:
    kind: str
    name: str
    action: str
    id: str = ""
    detail: str = ""  # what the object is, and what hangs off it
    reason: str = ""  # why it is skipped or blocked
    source: str = ""
    status: str = ""
    error: str = ""
    _item: Any = None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def kind_of(value: Any) -> Optional[str]:
    return ALIASES.get(_text(value).lower())


def _target(record: dict, source: str, default_kind: Optional[str]) -> Target:
    lowered = {_text(k).lower(): v for k, v in record.items() if k is not None}
    raw_kind = _text(lowered.get("kind") or lowered.get("type"))
    kind = kind_of(raw_kind) if raw_kind else default_kind
    target = Target(kind or "", id=_text(lowered.get("id")), name=_text(lowered.get("name")), network=_text(lowered.get("network")), address=_text(lowered.get("address")), source=source)
    if not kind:
        target.problems.append(f"the kind '{raw_kind}' is not one of resource, group or network" if raw_kind else "no kind given (a kind column, or --kind)")
    if not target.id and not target.name:
        target.problems.append("neither an id nor a name")
    return target


def _from_csv(text: str, file: str, default_kind: Optional[str]) -> list:
    rows = list(csv.DictReader(io.StringIO(text)))
    return [_target(row, f"{file} row {number}", default_kind) for number, row in enumerate(rows, start=2) if any(_text(v) for v in row.values())]


def _from_json(text: str, file: str, default_kind: Optional[str]) -> list:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoadError(f"{file} is not valid JSON: {exc}")
    if not isinstance(data, list):
        raise LoadError(f"{file}: expected a JSON list of objects such as {{\"kind\": \"group\", \"name\": \"Old group\"}}")
    out = []
    for number, record in enumerate(data, start=1):
        if isinstance(record, dict):
            out.append(_target(record, f"{file} item {number}", default_kind))
        else:
            out.append(Target(default_kind or "", source=f"{file} item {number}", problems=["not an object"]))
    return out


def _from_lines(text: str, file: str, default_kind: Optional[str]) -> list:
    """A plain list: one ID or name per line (blank lines and lines starting with # are ignored). Needs --kind."""
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        target = Target(default_kind or "", source=f"{file} line {number}")
        if not default_kind:
            target.problems.append("a plain list needs --kind (resource, group or network)")
        # An ID and a name look alike in a plain list, so both are tried: the planner matches an ID first and a name second.
        target.id = target.name = value
        out.append(target)
    return out


def load_targets(path: Path, default_kind: Optional[str] = None) -> list:
    """Read the file. Only a file that cannot be read at all is an error; a line that cannot be understood stays, with ``problems``."""
    try:
        text = read_text(path)
    except OSError as exc:
        raise LoadError(f"cannot read {path}: {exc.strerror}")
    except TextFileError as exc:
        raise LoadError(str(exc))
    suffix = path.suffix.lower()
    targets = _from_json(text, path.name, default_kind) if suffix == ".json" else _from_csv(text, path.name, default_kind) if suffix == ".csv" else _from_lines(text, path.name, default_kind)
    if not targets:
        raise LoadError(f"{path.name} names nothing to remove.")
    return targets


def _label(kind: str, item: dict) -> str:
    return str(item.get("name") or item.get("id"))


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _match(target: Target, items: list) -> tuple:
    """(matches, problem): the objects the line could mean. An ID decides when there is one; a line that gives both must agree."""
    if target.kind == NETWORK or target.kind == GROUP:
        narrow = lambda item: True  # noqa: E731
    else:
        narrow = lambda item: (not target.network or (item.get("remoteNetwork") or {}).get("name") == target.network) and (  # noqa: E731
            not target.address or (item.get("address") or {}).get("value") == target.address
        )
    by_id = [i for i in items if str(i.get("id")) == target.id] if target.id else []
    if by_id:
        found = by_id[0]
        if target.name and target.name != target.id and found.get("name") != target.name:
            return [], f"the id {target.id} is '{found.get('name')}', not '{target.name}': the file is out of date"
        return by_id, ""
    if not target.name:
        return [], ""
    named = [i for i in items if i.get("name") == target.name and narrow(i)]
    return named, ""


def build_plan(targets: list, current: dict) -> list:
    """One Row per distinct object named (or per line that matches nothing or cannot be used), resources first, networks last."""
    rows: list = []
    chosen: dict = {kind: {} for kind in KINDS}  # kind -> id -> Row, so an object named twice is removed once
    for target in targets:
        label = target.name or target.id or "(blank)"
        if target.problems:
            rows.append(Row(target.kind or "?", label, BLOCKED, reason="; ".join(target.problems), source=target.source))
            continue
        items = current.get(ITEM_KEYS[target.kind]) or []
        matches, problem = _match(target, items)
        if problem:
            rows.append(Row(target.kind, label, BLOCKED, id=target.id, reason=problem, source=target.source))
        elif not matches:
            rows.append(Row(target.kind, label, SKIP, id=target.id, reason="not found in the tenant (already removed, or the name or id is wrong)", source=target.source))
        elif len(matches) > 1:
            candidates = "; ".join(
                f"{m['id']} ({(m.get('remoteNetwork') or {}).get('name', '?')}, {(m.get('address') or {}).get('value', '?')})" if target.kind == RESOURCE else str(m["id"])
                for m in matches
            )
            rows.append(Row(target.kind, label, BLOCKED, reason=f"matches {len(matches)} {target.kind}s: {candidates}. Name one by its id", source=target.source))
        else:
            item = matches[0]
            if str(item["id"]) not in chosen[target.kind]:
                row = Row(target.kind, _label(target.kind, item), REMOVE, id=str(item["id"]), source=target.source, _item=item)
                chosen[target.kind][str(item["id"])] = row
                rows.append(row)
    removing = {kind: set(rows_by_id) for kind, rows_by_id in chosen.items()}
    for row in [r for r in rows if r.action == REMOVE]:
        _judge(row, current, removing)
    rows.sort(key=lambda r: ORDER.index(r.kind) if r.kind in ORDER else len(ORDER))
    return rows


def _judge(row: Row, current: dict, removing: dict) -> None:
    item = row._item
    if row.kind == GROUP:
        _judge_group(row, item, current, removing)
    elif row.kind == RESOURCE:
        access = item.get("access") or []
        network = (item.get("remoteNetwork") or {}).get("name") or "?"
        address = (item.get("address") or {}).get("value") or "?"
        kind = {"NETWORK": "resource", "SSH": "SSH resource", "WEB_APP": "web app resource", "KUBERNETES": "Kubernetes resource"}.get(item.get("type"), "resource")
        who = "nobody has access to it" if not access else f"access for {len(access)} {'group or service account' if len(access) == 1 else 'groups or service accounts'} is removed with it"
        row.detail = f"{kind} {address} in network '{network}'; {who}"
    else:
        _judge_network(row, item, current, removing)


def _judge_group(row: Row, item: dict, current: dict, removing: dict) -> None:
    kind = item.get("type")
    if kind != "MANUAL":
        row.action = BLOCKED
        row.reason = f"a {str(kind).lower()} group belongs to the identity provider, so it is never removed here" if kind else "its type is not known, so it is not removed"
        return
    members = item.get("users") or []
    granted = {str(r.get("id")) for r in item.get("resources") or []}
    gone_with_it = removing[GROUP]
    stranded = 0
    for resource in current.get("resources") or []:
        if str(resource["id"]) in removing[RESOURCE] or str(resource["id"]) not in granted:
            continue
        who = {str((e.get("principal") or {}).get("id")) for e in resource.get("access") or []}
        if who <= gone_with_it:
            stranded += 1
    approving = [r for r in current.get("resources") or [] if str(item["id"]) in {str(a.get("id")) for a in r.get("approverGroups") or []} and str(r["id"]) not in removing[RESOURCE]]
    parts = [f"manual group; {_plural(len(members), 'member')} lose what it gave them", f"it has access to {_plural(len(granted), 'resource')}"]
    if stranded:
        parts.append(f"{_plural(stranded, 'resource')} would be left with nobody who can reach them")
    if approving:
        parts.append(f"it approves access requests for {_plural(len(approving), 'resource')}")
    row.detail = "; ".join(parts)


def _judge_network(row: Row, item: dict, current: dict, removing: dict) -> None:
    resources = [r for r in item.get("resources") or [] if str(r.get("id")) not in removing[RESOURCE]]
    connectors = item.get("connectors") or []
    gateways = item.get("gateways") or []
    problems = []
    if resources:
        shown = ", ".join(str(r.get("name") or r.get("id")) for r in resources[:5]) + (", ..." if len(resources) > 5 else "")
        problems.append(f"{_plural(len(resources), 'resource')} still in it would be left behind and are not in the file ({shown})")
    if connectors:
        shown = ", ".join(str(c.get("name") or c.get("id")) for c in connectors[:5]) + (", ..." if len(connectors) > 5 else "")
        problems.append(f"{_plural(len(connectors), 'Connector')} still in it ({shown}); remove them first with `tgcli connector delete`")
    if gateways:
        problems.append(f"{_plural(len(gateways), 'Gateway')} still in it; remove them first with `tgcli gateway delete`")
    if problems:
        row.action = BLOCKED
        row.reason = "; ".join(problems)
        return
    going = len(item.get("resources") or [])
    row.detail = f"remote network with {_plural(going, 'resource')}, all of them in the file" if going else "remote network with nothing in it"


def apply_plan(client: Any, rows: list, progress: Any = lambda row: None) -> None:
    """Remove every ``remove`` row, resources first. A failure is recorded on its row and the rest carry on, except that a
    Remote Network is not attempted when a resource of this run that was in it failed to go."""
    failed_networks: set = set()
    for row in rows:
        if row.action != REMOVE:
            row.status = DRY_RUN_STATUS[row.action]
            continue
        if row.kind == NETWORK and row.id in failed_networks:
            row.status, row.error = NOT_RUN, "a resource in it could not be removed"
            progress(row)
            continue
        try:
            result = ((client.execute(MUTATIONS[row.kind], {VARIABLE[row.kind]: row.id}).get("data") or {}).get(RESULT_FIELD[row.kind])) or {}
        except TwingateAPIError as exc:
            if not _is_per_object(exc):
                raise
            result = {"ok": False, "error": str(exc)}
        if result.get("ok"):
            row.status = REMOVED
        else:
            row.status, row.error = ERROR, str(result.get("error") or "the API did not say why")
            if row.kind == RESOURCE:
                network = (row._item.get("remoteNetwork") or {}).get("id")
                if network:
                    failed_networks.add(str(network))
        progress(row)


def _is_per_object(exc: TwingateAPIError) -> bool:
    """An error about this one object is recorded and the run goes on; being rate limited out or not logged in stops the run."""
    from tgcli.client.exceptions import TwingateAuthError, TwingateThrottleError

    return not isinstance(exc, (TwingateAuthError, TwingateThrottleError))


def counts(rows: list) -> dict:
    """How many objects of each kind are to be removed."""
    out: dict = {}
    for row in rows:
        if row.action == REMOVE:
            out[row.kind] = out.get(row.kind, 0) + 1
    return out
