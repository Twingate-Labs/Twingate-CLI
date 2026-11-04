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
SERVICE_ACCOUNTS, CERTIFICATE_AUTHORITIES, GATEWAYS, DNS_PROFILES = "service-accounts", "certificate-authorities", "gateways", "dns-profiles"
# In the order they are applied: a Gateway needs its Remote Network and certificate authorities, a resource its Gateway, a DNS profile its groups.
KINDS = (NETWORKS, GROUPS, SERVICE_ACCOUNTS, CERTIFICATE_AUTHORITIES, GATEWAYS, RESOURCES, DNS_PROFILES, DEVICES)
JSON_ONLY = (CERTIFICATE_AUTHORITIES, DNS_PROFILES)  # too structured for a spreadsheet; a backup writes them, and so can anyone else
# Files a backup holds that an import has no use for: they are counted and named in the "not carried over" section.
MANIFEST = "manifest.json"
BACKUP_DEVICES = "devices.json"  # in a backup (a folder with a manifest) it is an inventory, not trust to apply
IGNORED_FILES = ("users.json", "connectors.json", BACKUP_DEVICES, "security-policies.json", MANIFEST)

LOCATIONS = ("AWS", "AZURE", "GOOGLE_CLOUD", "ON_PREMISE", "OTHER")
NETWORK_TYPES = ("REGULAR", "EXIT")
ROUTING_MODES = ("THROUGH_TWINGATE", "BYPASS_TWINGATE")
NETWORK_RESOURCE, SSH, WEB_APP, KUBERNETES = "NETWORK", "SSH", "WEB_APP", "KUBERNETES"
RESOURCE_TYPES = (NETWORK_RESOURCE, SSH, WEB_APP, KUBERNETES)
# What each type is called in the API (a backup records the type under these names too, as __typename) and by people.
TYPENAMES = {"NetworkResource": NETWORK_RESOURCE, "SSHResource": SSH, "WebAppResource": WEB_APP, "KubernetesResource": KUBERNETES}
TYPE_ALIASES = {"WEBAPP": WEB_APP, "WEB": WEB_APP, "K8S": KUBERNETES, "KUBE": KUBERNETES, "STANDARD": NETWORK_RESOURCE}
TLS_CLIENT_MODES = ("VERIFY_FULL", "VERIFY_CA", "INSECURE", "NONE")  # Gateway to the web app
TLS_SERVER_MODES = ("TLS13", "NONE")  # client to the Gateway
PROTOCOL_POLICIES = ("ALLOW_ALL", "RESTRICTED")
ACCESS_MODES = ("MANUAL", "AUTO_LOCK", "ACCESS_REQUEST")
APPROVAL_MODES = ("MANUAL", "AUTOMATIC")

CSV_COLUMNS = {
    NETWORKS: ("name", "location", "network_type", "active"),
    GROUPS: ("name", "members", "security_policy"),
    RESOURCES: (
        "name", "network", "address", "alias", "tcp_ports", "udp_ports", "allow_icmp", "visible",
        "security_policy", "groups", "service_accounts", "routing_mode", "approver_groups",
        # Only for SSH, web app and Kubernetes resources (blank on a network resource, which is what a blank type means):
        "type", "gateway", "upstream_port", "downstream_port", "upstream_tls", "downstream_tls", "cluster_ref", "headers",
    ),
    DEVICES: ("serial_number", "trusted"),
    SERVICE_ACCOUNTS: ("name",),
    GATEWAYS: ("address", "network", "x509_ca", "ssh_ca"),
}
CSV_REQUIRED = {
    NETWORKS: ("name",), GROUPS: ("name",), RESOURCES: ("name", "network", "address"), DEVICES: ("serial_number",),
    SERVICE_ACCOUNTS: ("name",), GATEWAYS: ("address", "network", "x509_ca"),
}


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
    approver_groups: list = field(default_factory=list)  # names of the groups that approve access requests
    # SSH, web app and Kubernetes resources only. They are served through a Gateway, which has no name: it is found by address.
    gateway: str = ""
    upstream: Optional[dict] = None  # {"port": 22, "tlsMode": ...}, as the API takes it; tlsMode only for a web app
    downstream: Optional[dict] = None
    cluster_ref: str = ""
    headers: list = field(default_factory=list)  # web app request header rewrites: [{"key", "value"}]
    # What the file actually states. A blank CSV cell or a missing JSON key is not a statement, so --sync leaves that alone;
    # the fields above hold the API's defaults for such a field, which is what a create uses but a sync must not apply.
    given: set = field(default_factory=set)


@dataclass
class ServiceAccountSpec(Item):
    name: str = ""
    keys: int = 0  # how many keys the backup lists for it; they cannot be carried over


@dataclass
class CaSpec(Item):
    """A Certificate Authority as a backup lists it: its name and fingerprint. The certificate itself comes from `--ca-files`."""

    name: str = ""
    type: str = ""  # "x509" or "ssh"
    fingerprint: str = ""


@dataclass
class GatewaySpec(Item):
    """A Gateway has no name: it is its address within a Remote Network."""

    address: str = ""
    network: str = ""
    x509_ca: dict = field(default_factory=dict)  # {"name", "fingerprint"}; a file written by hand may give only the name
    ssh_ca: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.address or "(no address)"


@dataclass
class DnsProfileSpec(Item):
    name: str = ""
    priority: Optional[float] = None
    fallback_method: Optional[str] = None
    allowed_domains: Optional[list] = None
    denied_domains: Optional[list] = None
    categories: dict = field(default_factory=dict)  # "contentCategoryConfig" -> {setting: bool}, as the API takes them
    groups: list = field(default_factory=list)  # names of the groups the profile applies to


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
    service_accounts: list = field(default_factory=list)
    certificate_authorities: list = field(default_factory=list)
    gateways: list = field(default_factory=list)
    dns_profiles: list = field(default_factory=list)
    files: list = field(default_factory=list)  # the files read
    ignored: list = field(default_factory=list)  # backup files present but not used
    counts: dict = field(default_factory=dict)  # backup file name -> how many things it lists (None when that cannot be told), for the ignored ones


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


def _approvers(value: Any, spec: ResourceSpec) -> list:
    """The names of the approver groups, in file order, without repeats."""
    names: list = []
    for item in value or []:
        name = _name_of(item)
        if not name:
            spec.problems.append("an approver group has no name")
        elif name not in names:
            names.append(name)
    return names


def _resource_type(value: Any) -> str:
    """The type a record names; blank is a network resource. A name this tool does not know is kept (uppercased) and not imported."""
    word = re.sub(r"[\s-]+", "_", _text(value)).upper()
    return TYPE_ALIASES.get(word, word) or NETWORK_RESOURCE


def _port(value: Any, label: str, problems: list) -> Optional[int]:
    try:
        port = int(str(value).strip())
    except ValueError:
        problems.append(f"{label} port '{value}' is not a number")
        return None
    if not 1 <= port <= 65535:
        problems.append(f"{label} port {port} is not valid (1-65535)")
        return None
    return port


def _endpoint(value: Any, label: str, modes: tuple, web_app: bool, problems: list) -> Optional[dict]:
    """``{"port", "tlsMode"}`` from an ``upstream`` / ``downstream`` object, or None when the file says nothing about it."""
    if not isinstance(value, dict) or not (_stated(value.get("port")) or _stated(value.get("tlsMode"))):
        return None
    endpoint: dict = {}
    if _stated(value.get("port")):
        port = _port(value["port"], label, problems)
        if port is not None:
            endpoint["port"] = port
    else:
        problems.append(f"{label} TLS mode is given without a {label} port")
    if _stated(value.get("tlsMode")):
        if not web_app:
            problems.append(f"the {label} TLS mode only applies to web app resources")
        else:
            endpoint["tlsMode"] = _choice(value["tlsMode"], modes, f"{label} TLS mode", "", problems) or None
            if endpoint["tlsMode"] is None:
                del endpoint["tlsMode"]
    return endpoint or None


def _header_rewrites(value: Any, problems: list) -> list:
    rewrites = []
    for item in value or []:
        if not isinstance(item, dict) or not _text(item.get("key")):
            problems.append(f"request header {item!r} needs a key and a value")
            continue
        rewrites.append({"key": _text(item["key"]), "value": str(item.get("value", ""))})
    return rewrites


def _gateway_resource(record: dict, spec: ResourceSpec) -> None:
    """Read what only SSH, web app and Kubernetes resources have, and say what the API would need that the file lacks."""
    gateway = record.get("gateway")
    spec.gateway = _text(gateway.get("address") if isinstance(gateway, dict) else gateway)
    web_app = spec.type == WEB_APP
    spec.upstream = _endpoint(record.get("upstream"), "upstream", TLS_CLIENT_MODES, web_app, spec.problems)
    spec.downstream = _endpoint(record.get("downstream"), "downstream", TLS_SERVER_MODES, web_app, spec.problems)
    spec.cluster_ref = _text(record.get("clusterRef"))
    if spec.cluster_ref and spec.type != KUBERNETES:
        spec.problems.append("a cluster reference only applies to Kubernetes resources")
    spec.headers = _header_rewrites(record.get("requestHeaderRewrites"), spec.problems)
    if spec.headers and not web_app:
        spec.problems.append("request headers only apply to web app resources")
    if spec.type in (SSH, WEB_APP) and not spec.gateway:
        spec.problems.append("has no gateway (the address of the Gateway that serves it)")
    if web_app:
        for label, endpoint in (("upstream", spec.upstream), ("downstream", spec.downstream)):
            if not endpoint or "port" not in endpoint:
                spec.problems.append(f"has no {label} port")


def _resource(record: dict, source: str) -> ResourceSpec:
    spec = ResourceSpec(source=source, name=_text(record.get("name")), type=_resource_type(record.get("type")))
    spec.network = _name_of(record.get("remoteNetwork"))
    if not spec.name:
        spec.problems.append("has no name")
    if spec.type not in RESOURCE_TYPES:
        return spec  # not imported at all; its other fields are not read
    address = record.get("address")
    spec.address = _text(address.get("value") if isinstance(address, dict) else address)
    if not spec.address:
        spec.problems.append("has no address")
    if not spec.network:
        spec.problems.append("has no Remote Network")
    spec.alias = _text(record.get("alias"))
    network_resource = spec.type == NETWORK_RESOURCE
    if network_resource:
        # Ports, ICMP, routing and the browser shortcut are the network resource's own; the other types have a port per side instead.
        spec.protocols = _protocols(record.get("protocols"), spec.problems)
        spec.browser_shortcut = parse_bool(record.get("isBrowserShortcutEnabled"), "isBrowserShortcutEnabled", False, spec.problems)
        routing = record.get("routingMode")
        spec.routing_mode = _choice(routing, ROUTING_MODES, "routing mode", "THROUGH_TWINGATE", spec.problems) if routing else None
    else:
        _gateway_resource(record, spec)
    spec.is_visible = parse_bool(record.get("isVisible"), "isVisible", True, spec.problems)
    spec.security_policy = _name_of(record.get("securityPolicy")) or None
    spec.access_policy = _access_policy(record.get("accessPolicy"), "access policy", spec.problems)
    spec.approval_mode = _approval_mode(record.get("approvalMode"), "approval mode", spec.problems)
    for tag in record.get("tags") or []:
        if isinstance(tag, dict) and "key" in tag:
            spec.tags.append({"key": str(tag["key"]), "value": str(tag.get("value", ""))})
    spec.approver_groups = _approvers(record.get("approverGroups"), spec)
    _access(record.get("access"), spec)
    protocols = record.get("protocols") if isinstance(record.get("protocols"), dict) else {}
    stated = {
        "alias": _stated(record.get("alias")), "visible": _stated(record.get("isVisible")),
        "tags": isinstance(record.get("tags"), list), "security_policy": bool(spec.security_policy),
        "access_policy": isinstance(record.get("accessPolicy"), dict) and bool(record["accessPolicy"].get("mode")),
        "approval_mode": bool(spec.approval_mode), "access": isinstance(record.get("access"), list),
        "approvers": isinstance(record.get("approverGroups"), list),
    }
    if network_resource:
        stated.update({
            "icmp": _stated(protocols.get("allowIcmp")), "tcp": isinstance(protocols.get("tcp"), dict),
            "udp": isinstance(protocols.get("udp"), dict), "browser_shortcut": _stated(record.get("isBrowserShortcutEnabled")),
            "routing_mode": bool(spec.routing_mode),
        })
    else:
        stated.update({
            "gateway": bool(spec.gateway), "upstream": spec.upstream is not None, "downstream": spec.downstream is not None,
            "cluster_ref": bool(spec.cluster_ref), "headers": isinstance(record.get("requestHeaderRewrites"), list),
        })
    spec.given = {name for name, yes in stated.items() if yes}
    return spec


def _service_account(record: dict, source: str) -> ServiceAccountSpec:
    spec = ServiceAccountSpec(source=source, name=_text(record.get("name")))
    if not spec.name:
        spec.problems.append("has no name")
    keys = record.get("keys")
    spec.keys = len(keys) if isinstance(keys, list) else 0
    return spec


def _ca(record: dict, source: str) -> CaSpec:
    spec = CaSpec(source=source, name=_text(record.get("name")), type=_text(record.get("type")).lower(), fingerprint=_text(record.get("fingerprint")))
    if not spec.name:
        spec.problems.append("has no name")
    if spec.type not in ("x509", "ssh"):
        spec.problems.append(f"type '{record.get('type')}' is not x509 or ssh")
    return spec


def _ca_ref(value: Any) -> dict:
    """``{"name", "fingerprint"}`` from the reference a gateway holds; a bare string is a name."""
    if isinstance(value, dict):
        ref = {"name": _text(value.get("name")), "fingerprint": _text(value.get("fingerprint"))}
    else:
        ref = {"name": _text(value), "fingerprint": ""}
    return ref if ref["name"] or ref["fingerprint"] else {}


def _gateway(record: dict, source: str) -> GatewaySpec:
    spec = GatewaySpec(source=source, address=_text(record.get("address")), network=_name_of(record.get("remoteNetwork")))
    if not spec.address:
        spec.problems.append("has no address")
    if not spec.network:
        spec.problems.append("has no Remote Network")
    spec.x509_ca = _ca_ref(record.get("x509CA"))
    spec.ssh_ca = _ca_ref(record.get("sshCA"))
    if not spec.x509_ca:
        spec.problems.append("has no X.509 certificate authority (the API needs one for every Gateway)")
    return spec


CATEGORY_CONFIGS = ("contentCategoryConfig", "securityCategoryConfig", "privacyCategoryConfig")


def _domains(value: Any, label: str, problems: list) -> Optional[list]:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(d, str) for d in value):
        problems.append(f"{label} must be a list of domain names")
        return None
    return list(dict.fromkeys(d.strip() for d in value if d.strip()))


def _dns_profile(record: dict, source: str) -> DnsProfileSpec:
    spec = DnsProfileSpec(source=source, name=_text(record.get("name")))
    if not spec.name:
        spec.problems.append("has no name")
    priority = record.get("priority")
    if priority is not None:
        if isinstance(priority, bool) or not isinstance(priority, (int, float)):
            spec.problems.append(f"priority '{priority}' is not a number")
        else:
            spec.priority = float(priority)
    spec.fallback_method = _text(record.get("fallbackMethod")) or None
    spec.allowed_domains = _domains(record.get("allowedDomains"), "allowedDomains", spec.problems)
    spec.denied_domains = _domains(record.get("deniedDomains"), "deniedDomains", spec.problems)
    for key in CATEGORY_CONFIGS:
        config = record.get(key)
        if isinstance(config, dict):
            settings = {k: v for k, v in config.items() if isinstance(v, bool)}
            if settings:
                spec.categories[key] = settings
    for group in record.get("groups") or []:
        name = _name_of(group)
        if name and name not in spec.groups:
            spec.groups.append(name)
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


# What a network resource's columns say that the other types cannot take.
_NETWORK_ONLY_COLUMNS = ("tcp_ports", "udp_ports", "allow_icmp", "routing_mode")
_GATEWAY_ONLY_COLUMNS = ("gateway", "upstream_port", "downstream_port", "upstream_tls", "downstream_tls", "cluster_ref", "headers")


def _csv_headers(text: str, problems: list) -> list:
    """`Key=Value;Key2=Value2` as header rewrites. A value cannot contain `;` here (use a JSON file for that)."""
    rewrites = []
    for part in _split(text):
        key, sep, value = part.partition("=")
        if not sep or not key.strip():
            problems.append(f"headers '{part}' should look like Key=Value (separate several with ;)")
            continue
        rewrites.append({"key": key.strip(), "value": value.strip()})
    return rewrites


def _resource_from_csv(row: dict, source: str) -> ResourceSpec:
    kind = _resource_type(row.get("type"))
    record: dict = {
        "type": kind,
        "name": row.get("name"),
        "remoteNetwork": {"name": row.get("network")},
        "address": {"value": row.get("address")},
        "alias": row.get("alias"),
        "isVisible": row.get("visible"),
        "routingMode": row.get("routing_mode"),
        "protocols": {"allowIcmp": row.get("allow_icmp")},
        "access": [],
    }
    header_problems: list = []
    if kind != NETWORK_RESOURCE:
        record["gateway"] = _text(row.get("gateway"))
        record["upstream"] = {"port": row.get("upstream_port"), "tlsMode": row.get("upstream_tls")}
        record["downstream"] = {"port": row.get("downstream_port"), "tlsMode": row.get("downstream_tls")}
        record["clusterRef"] = row.get("cluster_ref")
        if _text(row.get("headers")):
            record["requestHeaderRewrites"] = _csv_headers(row["headers"], header_problems)
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
    spec.problems.extend(header_problems)
    if kind == NETWORK_RESOURCE:
        for column in _GATEWAY_ONLY_COLUMNS:
            if _text(row.get(column)):
                spec.problems.append(f"{column} only applies to SSH, web app and Kubernetes resources (set type to say which)")
        # Port lists in a CSV are written as text (`80;443;8000-8100`), so they are parsed here, not from the JSON shape.
        for proto in ("tcp", "udp"):
            spec.protocols[proto] = parse_ports(row.get(f"{proto}_ports", ""), f"{proto}_ports", spec.problems)
            if _text(row.get(f"{proto}_ports")):
                spec.given.add(proto)
    elif kind in RESOURCE_TYPES:
        for column in _NETWORK_ONLY_COLUMNS:
            if _text(row.get(column)):
                spec.problems.append(f"{column} only applies to network resources, not {kind} resources")
    approvers = _split(row.get("approver_groups", ""))
    if approvers:
        spec.approver_groups = list(dict.fromkeys(approvers))
        spec.given.add("approvers")
    if not record["access"]:
        spec.given.discard("access")  # no groups and no service accounts named: the cell is blank, not an empty list
    return spec


_CSV_ADAPTERS: dict = {
    NETWORKS: lambda row, source: _network(_csv_network(row), source),
    GROUPS: lambda row, source: _csv_group_spec(row, source),
    RESOURCES: _resource_from_csv,
    DEVICES: lambda row, source: _device({"serial_number": row.get("serial_number"), "trusted": row.get("trusted")}, source),
    SERVICE_ACCOUNTS: lambda row, source: _service_account({"name": row.get("name")}, source),
    GATEWAYS: lambda row, source: _gateway({
        "address": row.get("address"), "remoteNetwork": {"name": row.get("network")},
        "x509CA": {"name": row.get("x509_ca")}, "sshCA": {"name": row.get("ssh_ca")},
    }, source),
}
_JSON_PARSERS: dict = {
    NETWORKS: _network, GROUPS: _group, RESOURCES: _resource, DEVICES: _device, SERVICE_ACCOUNTS: _service_account,
    CERTIFICATE_AUTHORITIES: _ca, GATEWAYS: _gateway, DNS_PROFILES: _dns_profile,
}


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
    if is_csv and kind in JSON_ONLY:
        raise LoadError(f"{path.name} must be a .json file, in the shape `tgcli backup` writes {kind}.json.")
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
        f"Cannot tell what {path.name} holds. Name it {', '.join(k + '.json or .csv' for k in KINDS if k not in JSON_ONLY)}"
        f" ({', '.join(k + '.json' for k in JSON_ONLY)} are JSON only), or give the folder that contains them."
    )


def _count(path: Path) -> Optional[int]:
    """How many things a backup file lists, or None when it cannot be read as a list."""
    try:
        data = json.loads(read_text(path))
    except (OSError, TextFileError, ValueError):
        return None
    return len(data) if isinstance(data, list) else None


_TARGETS = {
    NETWORKS: "networks", GROUPS: "groups", RESOURCES: "resources", DEVICES: "devices", SERVICE_ACCOUNTS: "service_accounts",
    CERTIFICATE_AUTHORITIES: "certificate_authorities", GATEWAYS: "gateways", DNS_PROFILES: "dns_profiles",
}


def load(path: Path) -> Specs:
    """Read a folder (a backup, or one holding files named like the KINDS) or a single such file."""
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
        specs.counts = {name: _count(path / name) for name in specs.ignored if name != MANIFEST}
    if not found:
        raise LoadError(f"{path} has none of: {', '.join(k + '.json or .csv' for k in KINDS)}.")
    for kind, file in found.items():
        specs.files.append(file.name)
        getattr(specs, _TARGETS[kind]).extend(load_file(file, kind))
    return specs
