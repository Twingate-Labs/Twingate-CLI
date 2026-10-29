"""Read an import file (a backup's JSON, or CSV) into plain specs, without touching the API.

CSV rows are first turned into the same shape a backup's JSON has, so there is one parser and a backup, or a CSV
someone wrote by hand, takes exactly the same road from there.

A row that cannot be understood (no name, a bad port list...) is kept with ``problems`` set, not dropped: the plan
reports it as blocked, so nothing disappears silently. Only a file that cannot be read at all is an error.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from tgcli.textio import TextFileError, read_text

NETWORKS, GROUPS, RESOURCES, DEVICES = "remote-networks", "groups", "resources", "devices"
KINDS = (NETWORKS, GROUPS, RESOURCES, DEVICES)
# Files a backup holds that an import has no use for yet.
MANIFEST = "manifest.json"
BACKUP_DEVICES = "devices.json"  # in a backup (a folder with a manifest) it is an inventory, not trust to apply
IGNORED_FILES = (
    "users.json", "connectors.json", BACKUP_DEVICES, "service-accounts.json", "security-policies.json",
    "dns-profiles.json", "gateways.json", "certificate-authorities.json", MANIFEST,
)

LOCATIONS = ("AWS", "AZURE", "GOOGLE_CLOUD", "ON_PREMISE", "OTHER")
NETWORK_TYPES = ("REGULAR", "EXIT")
ROUTING_MODES = ("THROUGH_TWINGATE", "BYPASS_TWINGATE")
PROTOCOL_POLICIES = ("ALLOW_ALL", "RESTRICTED")
ACCESS_MODES = ("MANUAL", "AUTO_LOCK", "ACCESS_REQUEST")
APPROVAL_MODES = ("MANUAL", "AUTOMATIC")

CSV_COLUMNS = {
    NETWORKS: ("name", "location", "network_type", "active"),
    GROUPS: ("name", "members", "security_policy"),
    RESOURCES: (
        "name", "network", "address", "alias", "tcp_ports", "udp_ports", "allow_icmp", "visible",
        "security_policy", "groups", "service_accounts", "routing_mode",
    ),
    DEVICES: ("serial_number", "trusted"),
}
CSV_REQUIRED = {NETWORKS: ("name",), GROUPS: ("name",), RESOURCES: ("name", "network", "address"), DEVICES: ("serial_number",)}


class LoadError(Exception):
    """The file or folder cannot be read as an import."""


@dataclass
class Item:
    source: str = ""  # where it came from, e.g. "groups.csv row 4"
    problems: list = field(default_factory=list)  # reasons it cannot be imported at all
    notes: list = field(default_factory=list)  # things in the file that are not imported (shown, never silent)


@dataclass
class NetworkSpec(Item):
    name: str = ""
    location: str = "OTHER"
    network_type: str = "REGULAR"
    is_active: bool = True


@dataclass
class GroupSpec(Item):
    name: str = ""
    type: str = "MANUAL"
    members: list = field(default_factory=list)  # emails, in file order, without repeats
    security_policy: Optional[str] = None  # a name
    given: set = field(default_factory=set)  # what the file actually says ("members", "security_policy"); a blank is not a statement


GROUP, SERVICE_ACCOUNT = "group", "service account"


@dataclass
class AccessSpec:
    """One principal's access to a resource. ``group`` holds the name of a group or of a service account (see ``kind``)."""

    group: str
    kind: str = GROUP
    security_policy: Optional[str] = None
    access_policy: Optional[dict] = None
    approval_mode: Optional[str] = None
    expires_at: Optional[str] = None
    given: set = field(default_factory=set)  # which of the four settings the file states (so `access_policy=None` can mean MANUAL)


@dataclass
class ResourceSpec(Item):
    type: str = "NETWORK"
    name: str = ""
    network: str = ""
    address: str = ""
    alias: str = ""
    protocols: dict = field(default_factory=dict)
    is_visible: bool = True
    browser_shortcut: bool = False
    tags: list = field(default_factory=list)
    security_policy: Optional[str] = None
    access_policy: Optional[dict] = None
    approval_mode: Optional[str] = None
    routing_mode: Optional[str] = None
    access: list = field(default_factory=list)
    # What the file actually states. A blank CSV cell or a missing JSON key is not a statement, so --sync leaves that alone;
    # the fields above hold the API's defaults for such a field, which is what a create uses but a sync must not apply.
    given: set = field(default_factory=set)


@dataclass
class DeviceSpec(Item):
    serial: str = ""
    trusted: bool = True

    @property
    def name(self) -> str:  # a device is identified, and labelled in reports, by its serial number
        return self.serial or "(no serial number)"


@dataclass
class Specs:
    devices: list = field(default_factory=list)
    networks: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    resources: list = field(default_factory=list)
    files: list = field(default_factory=list)  # the files read
    ignored: list = field(default_factory=list)  # backup files present but not used


# ---------------------------------------------------------------- small parsers


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _stated(value: Any) -> bool:
    """Whether a field says anything: present, and not a blank cell or null."""
    return value.strip() != "" if isinstance(value, str) else value is not None


def _name_of(value: Any) -> str:
    """The name inside a reference like {"id": ..., "name": ...}; a bare string is taken as the name."""
    if isinstance(value, dict):
        return _text(value.get("name"))
    return _text(value)


def _choice(value: Any, allowed: tuple, label: str, default: str, problems: list) -> str:
    if value is None or _text(value) == "":
        return default
    normal = re.sub(r"[\s-]+", "_", _text(value)).upper()
    if normal not in allowed:
        problems.append(f"{label} '{value}' is not one of {', '.join(allowed)}")
        return default
    return normal


def parse_bool(value: Any, label: str, default: bool, problems: list) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or _text(value) == "":
        return default
    word = _text(value).lower()
    if word in ("true", "yes", "y", "1"):
        return True
    if word in ("false", "no", "n", "0"):
        return False
    problems.append(f"{label} '{value}' is not true or false")
    return default


def parse_ports(text: str, label: str, problems: list) -> dict:
    """A CSV port list: `*` is every port, `none` is no ports, otherwise `80;443;8000-8100`."""
    word = text.strip()
    if word in ("", "*") or word.lower() == "all":
        return {"policy": "ALLOW_ALL", "ports": []}
    if word.lower() == "none":
        return {"policy": "RESTRICTED", "ports": []}
    ports = []
    for token in re.split(r"[;,]", word):
        token = token.strip()
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", token)
        if not match:
            problems.append(f"{label} '{token}' is not a port or a range like 8000-8100")
            continue
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if not (1 <= start <= 65535 and 1 <= end <= 65535) or start > end:
            problems.append(f"{label} '{token}' is not a valid port range (1-65535, start no larger than end)")
            continue
        ports.append({"start": start, "end": end})
    return {"policy": "RESTRICTED", "ports": ports}


def _protocols(value: Any, problems: list) -> dict:
    """Backup-shaped protocols, validated; absent means everything allowed (the API's own default for a new resource)."""
    result = {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}
    if not isinstance(value, dict):
        return result
    if "allowIcmp" in value:
        result["allowIcmp"] = parse_bool(value["allowIcmp"], "allowIcmp", True, problems)
    for proto in ("tcp", "udp"):
        entry = value.get(proto)
        if not isinstance(entry, dict):
            continue
        policy = _choice(entry.get("policy"), PROTOCOL_POLICIES, f"{proto} policy", "ALLOW_ALL", problems)
        ports = []
        for item in entry.get("ports") or []:
            try:
                start, end = int(item["start"]), int(item["end"])
            except (KeyError, TypeError, ValueError):
                problems.append(f"{proto} port range {item!r} needs a start and an end")
                continue
            if not (1 <= start <= 65535 and 1 <= end <= 65535) or start > end:
                problems.append(f"{proto} port range {start}-{end} is not valid (1-65535, start no larger than end)")
                continue
            ports.append({"start": start, "end": end})
        if policy == "ALLOW_ALL" and ports:
            problems.append(f"{proto} is ALLOW_ALL but also lists ports; use RESTRICTED")
        result[proto] = {"policy": policy, "ports": ports}
    return result


def _access_policy(value: Any, label: str, problems: list) -> Optional[dict]:
    """{"mode", "durationSeconds"} as the API takes it, or None when the file has none (or the default, MANUAL)."""
    if not isinstance(value, dict) or not value.get("mode"):
        return None
    mode = _choice(value.get("mode"), ACCESS_MODES, f"{label} mode", "MANUAL", problems)
    if mode == "MANUAL":
        return None
    policy: dict = {"mode": mode}
    if value.get("durationSeconds") is not None:
        policy["durationSeconds"] = value["durationSeconds"]
    return policy


def _approval_mode(value: Any, label: str, problems: list) -> Optional[str]:
    if value is None or _text(value) == "":
        return None
    return _choice(value, APPROVAL_MODES, label, "MANUAL", problems)


# ---------------------------------------------------------------- JSON-shaped records -> specs


def _network(record: dict, source: str) -> NetworkSpec:
    spec = NetworkSpec(source=source, name=_text(record.get("name")))
    if not spec.name:
        spec.problems.append("has no name")
    spec.location = _choice(record.get("location"), LOCATIONS, "location", "OTHER", spec.problems)
    spec.network_type = _choice(record.get("networkType"), NETWORK_TYPES, "network type", "REGULAR", spec.problems)
    spec.is_active = parse_bool(record.get("isActive"), "isActive", True, spec.problems)
    return spec


def _group(record: dict, source: str) -> GroupSpec:
    spec = GroupSpec(source=source, name=_text(record.get("name")), type=_text(record.get("type")).upper() or "MANUAL")
    if not spec.name:
        spec.problems.append("has no name")
    seen = set()
    for user in record.get("users") or []:
        email = _text(user.get("email") if isinstance(user, dict) else user)
        if email and email.lower() not in seen:
            seen.add(email.lower())
            spec.members.append(email)
    spec.security_policy = _name_of(record.get("securityPolicy")) or None
    if spec.security_policy:
        spec.given.add("security_policy")
    if isinstance(record.get("users"), list):
        spec.given.add("members")
    return spec


def _principal_kind(type_name: str) -> str:
    """``group``, ``service account``, or the type's own words (lowercased, spaced) for one that is not imported.

    The backup writes ``Group`` and ``ServiceAccount``; ``SERVICE_ACCOUNT`` and ``service account`` mean the same.
    """
    return re.sub(r"[\s_-]+", " ", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type_name)).lower().strip()


def _access(entries: Any, spec: ResourceSpec) -> None:
    seen = set()
    for entry in entries or []:
        principal = entry.get("principal") or {}
        name = _text(principal.get("name"))
        kind = _principal_kind(_text(principal.get("type")) or "Group")
        label = name or "(unnamed)"
        if kind not in (GROUP, SERVICE_ACCOUNT):
            spec.notes.append(f"access for {kind} '{label}' is not imported (only groups and service accounts are)")
            continue
        if not name:
            spec.problems.append(f"an access entry has no {kind} name")
            continue
        if (kind, name) in seen:
            continue
        seen.add((kind, name))
        probs: list = []
        access = AccessSpec(
            group=name,
            kind=kind,
            security_policy=_name_of(entry.get("securityPolicy")) or None,
            access_policy=_access_policy(entry.get("accessPolicy"), f"access for '{name}' access policy", probs),
            approval_mode=_approval_mode(entry.get("approvalMode"), f"access for '{name}' approval mode", probs),
            expires_at=_text(entry.get("expiresAt")) or None,
        )
        if access.security_policy:
            access.given.add("security_policy")
        if isinstance(entry.get("accessPolicy"), dict) and entry["accessPolicy"].get("mode"):
            access.given.add("access_policy")
        if access.approval_mode:
            access.given.add("approval_mode")
        if access.expires_at:
            access.given.add("expires_at")
        spec.problems.extend(probs)
        spec.access.append(access)


def _resource(record: dict, source: str) -> ResourceSpec:
    spec = ResourceSpec(source=source, name=_text(record.get("name")), type=_text(record.get("type")).upper() or "NETWORK")
    spec.network = _name_of(record.get("remoteNetwork"))
    if not spec.name:
        spec.problems.append("has no name")
    if spec.type != "NETWORK":
        return spec  # not imported at all; its other fields are not read
    address = record.get("address")
    spec.address = _text(address.get("value") if isinstance(address, dict) else address)
    if not spec.address:
        spec.problems.append("has no address")
    if not spec.network:
        spec.problems.append("has no Remote Network")
    spec.alias = _text(record.get("alias"))
    spec.protocols = _protocols(record.get("protocols"), spec.problems)
    spec.is_visible = parse_bool(record.get("isVisible"), "isVisible", True, spec.problems)
    spec.browser_shortcut = parse_bool(record.get("isBrowserShortcutEnabled"), "isBrowserShortcutEnabled", False, spec.problems)
    spec.security_policy = _name_of(record.get("securityPolicy")) or None
    spec.access_policy = _access_policy(record.get("accessPolicy"), "access policy", spec.problems)
    spec.approval_mode = _approval_mode(record.get("approvalMode"), "approval mode", spec.problems)
    routing = record.get("routingMode")
    spec.routing_mode = _choice(routing, ROUTING_MODES, "routing mode", "THROUGH_TWINGATE", spec.problems) if routing else None
    for tag in record.get("tags") or []:
        if isinstance(tag, dict) and "key" in tag:
            spec.tags.append({"key": str(tag["key"]), "value": str(tag.get("value", ""))})
    if record.get("approverGroups"):
        spec.notes.append("approver groups are not imported")
    _access(record.get("access"), spec)
    protocols = record.get("protocols") if isinstance(record.get("protocols"), dict) else {}
    stated = {
        "alias": _stated(record.get("alias")), "icmp": _stated(protocols.get("allowIcmp")),
        "tcp": isinstance(protocols.get("tcp"), dict), "udp": isinstance(protocols.get("udp"), dict),
        "visible": _stated(record.get("isVisible")), "browser_shortcut": _stated(record.get("isBrowserShortcutEnabled")),
        "tags": isinstance(record.get("tags"), list), "security_policy": bool(spec.security_policy),
        "access_policy": isinstance(record.get("accessPolicy"), dict) and bool(record["accessPolicy"].get("mode")),
        "approval_mode": bool(spec.approval_mode), "routing_mode": bool(spec.routing_mode),
        "access": isinstance(record.get("access"), list),
    }
    spec.given = {name for name, yes in stated.items() if yes}
    return spec


def _device(record: dict, source: str) -> DeviceSpec:
    # JSON uses the API's own field names (`serialNumber`, `isTrusted`); CSV columns are `serial_number` and `trusted`.
    spec = DeviceSpec(source=source, serial=_text(record.get("serialNumber", record.get("serial_number"))))
    if not spec.serial:
        spec.problems.append("has no serial number")
    spec.trusted = parse_bool(record.get("isTrusted", record.get("trusted")), "trusted", True, spec.problems)
    return spec


# ---------------------------------------------------------------- CSV rows -> JSON-shaped records


def _split(text: str, separators: str = ";") -> list:
    return [part.strip() for part in re.split(f"[{re.escape(separators)}]", text or "") if part.strip()]


def _csv_network(row: dict) -> dict:
    return {"name": row.get("name"), "location": row.get("location"), "networkType": row.get("network_type"), "isActive": row.get("active")}


def _csv_group(row: dict) -> dict:
    # Emails never contain a comma or semicolon, so either separates them. Group names may contain a comma, so below only `;` does.
    record = {"name": row.get("name"), "users": [{"email": email} for email in _split(row.get("members", ""), ";,")]}
    if _text(row.get("security_policy")):
        record["securityPolicy"] = {"name": _text(row["security_policy"])}
    return record


def _csv_group_spec(row: dict, source: str) -> GroupSpec:
    spec = _group(_csv_group(row), source)
    if not spec.members:
        spec.given.discard("members")  # a blank members cell is not a statement that the group is empty
    return spec


def _resource_from_csv(row: dict, source: str) -> ResourceSpec:
    record: dict = {
        "type": "NETWORK",
        "name": row.get("name"),
        "remoteNetwork": {"name": row.get("network")},
        "address": {"value": row.get("address")},
        "alias": row.get("alias"),
        "isVisible": row.get("visible"),
        "routingMode": row.get("routing_mode"),
        "protocols": {"allowIcmp": row.get("allow_icmp")},
        "access": [],
    }
    if _text(row.get("security_policy")):
        record["securityPolicy"] = {"name": _text(row["security_policy"])}
    for item in _split(row.get("groups", "")):
        group, _, policy = item.rpartition("=") if "=" in item else (item, "", "")
        entry: dict = {"principal": {"type": "Group", "name": group.strip()}}
        if policy.strip():
            entry["securityPolicy"] = {"name": policy.strip()}
        record["access"].append(entry)
    # A service account takes no per-grant settings, so there is no `=Policy` form: the whole cell is the name.
    for name in _split(row.get("service_accounts", "")):
        record["access"].append({"principal": {"type": "ServiceAccount", "name": name}})
    spec = _resource(record, source)
    # Port lists in a CSV are written as text (`80;443;8000-8100`), so they are parsed here, not from the JSON shape.
    for proto in ("tcp", "udp"):
        spec.protocols[proto] = parse_ports(row.get(f"{proto}_ports", ""), f"{proto}_ports", spec.problems)
        if _text(row.get(f"{proto}_ports")):
            spec.given.add(proto)
    if not record["access"]:
        spec.given.discard("access")  # no groups and no service accounts named: the cell is blank, not an empty list
    return spec


_CSV_ADAPTERS: dict = {
    NETWORKS: lambda row, source: _network(_csv_network(row), source),
    GROUPS: lambda row, source: _csv_group_spec(row, source),
    RESOURCES: _resource_from_csv,
    DEVICES: lambda row, source: _device({"serial_number": row.get("serial_number"), "trusted": row.get("trusted")}, source),
}
_JSON_PARSERS: dict = {NETWORKS: _network, GROUPS: _group, RESOURCES: _resource, DEVICES: _device}


# ---------------------------------------------------------------- files


def _read_json(path: Path, kind: str) -> list:
    try:
        data = json.loads(read_text(path))
    except (OSError, TextFileError) as exc:
        raise LoadError(f"Cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LoadError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise LoadError(f"{path} must hold a JSON list of {kind}, like the files `tgcli backup` writes.")
    return data


def _read_csv(path: Path, kind: str) -> list:
    try:
        reader = csv.DictReader(io.StringIO(read_text(path), newline=""))
        headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        rows = [{(k or "").strip().lower(): (v or "") for k, v in row.items() if k is not None} for row in reader]
    except (OSError, TextFileError, csv.Error) as exc:
        raise LoadError(f"Cannot read {path}: {exc}") from exc
    unknown = [h for h in headers if h and h not in CSV_COLUMNS[kind]]
    if unknown:
        raise LoadError(
            f"{path} has column(s) it does not recognise: {', '.join(unknown)}. "
            f"Columns for {kind}: {', '.join(CSV_COLUMNS[kind])}."
        )
    missing = [c for c in CSV_REQUIRED[kind] if c not in headers]
    if missing:
        raise LoadError(f"{path} is missing the required column(s): {', '.join(missing)}.")
    return rows


def load_file(path: Path, kind: str) -> list:
    """The specs in one file, in file order."""
    is_csv = path.suffix.lower() == ".csv"
    records = _read_csv(path, kind) if is_csv else _read_json(path, kind)
    parse: Callable = _CSV_ADAPTERS[kind] if is_csv else _JSON_PARSERS[kind]
    specs = []
    for index, record in enumerate(records, start=1):
        # JSON rows are numbered from 1 in the list; CSV rows count the header as row 1, as a spreadsheet shows them.
        label = f"{path.name} row {index + 1}" if is_csv else f"{path.name} item {index}"
        if not isinstance(record, dict):
            raise LoadError(f"{path}: {label} is not an object.")
        specs.append(parse(record, label))
    return specs


def kind_of(path: Path) -> str:
    stem = path.stem.lower()
    if stem in KINDS and path.suffix.lower() in (".json", ".csv"):
        return stem
    raise LoadError(
        f"Cannot tell what {path.name} holds. Name it {', '.join(k + '.json or .csv' for k in KINDS)}, "
        "or give the folder that contains them."
    )


def load(path: Path) -> Specs:
    """Read a folder (a backup, or one holding files named remote-networks / groups / resources / devices) or a single such file."""
    if not path.exists():
        raise LoadError(f"{path} does not exist.")
    specs = Specs()
    if path.is_file():
        found = {kind_of(path): path}
    else:
        found = {}
        is_backup = (path / MANIFEST).is_file()
        for kind in KINDS:
            candidates = [path / f"{kind}.json", path / f"{kind}.csv"]
            if is_backup and kind == DEVICES:
                # A backup lists every device it saw. Reading that as trust to set would block on devices with no
                # serial number and change trust in another tenant, so only a devices.csv added by hand is used.
                candidates = [c for c in candidates if c.name != BACKUP_DEVICES]
            present = [c for c in candidates if c.is_file()]
            if len(present) > 1:
                raise LoadError(f"{path} has both {present[0].name} and {present[1].name}; keep one.")
            if present:
                found[kind] = present[0]
        specs.ignored = [
            name for name in IGNORED_FILES if (path / name).is_file() and (name != BACKUP_DEVICES or is_backup)
        ]
    if not found:
        raise LoadError(f"{path} has none of: {', '.join(k + '.json or .csv' for k in KINDS)}.")
    for kind, file in found.items():
        specs.files.append(file.name)
        loaded = load_file(file, kind)
        {NETWORKS: specs.networks, GROUPS: specs.groups, RESOURCES: specs.resources, DEVICES: specs.devices}[kind].extend(loaded)
    return specs
