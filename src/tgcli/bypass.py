"""Converting a Resource from routing through Twingate to bypassing it.

The API refuses ``BYPASS_TWINGATE`` for a Resource that has a Security Policy or any port or ICMP restriction, and keeps
everything else (per-group policies, auto-lock, expiry, approval, approver groups). So the conversion is one update that
clears the Security Policy and opens the protocols, plus the routing change. This module reads what is there, decides
what to clear, and builds that update; it never talks to the API.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

BYPASS = "BYPASS_TWINGATE"
THROUGH = "THROUGH_TWINGATE"

# Row statuses, in the order a run reports them.
WOULD_CONVERT = "would convert"
CONVERTED = "converted"
ALREADY = "already bypass"
BLOCKED = "blocked"
ERROR = "error"

COLUMNS = (
    "id", "name", "status", "detail", "securityPolicyId", "securityPolicyName",
    "allowIcmp", "tcpPolicy", "tcpPorts", "udpPolicy", "udpPorts", "error",
)

#: What the API accepts as "no restriction at all".
OPEN_PROTOCOLS = {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}


@dataclass
class Row:
    """One Resource's outcome. The columns after ``detail`` hold what the Resource had BEFORE, so a run is also an undo record."""

    id: str
    name: str = ""
    status: str = ""
    detail: str = ""
    securityPolicyId: str = ""
    securityPolicyName: str = ""
    allowIcmp: Optional[bool] = None
    tcpPolicy: str = ""
    tcpPorts: str = ""
    udpPolicy: str = ""
    udpPorts: str = ""
    error: str = ""
    variables: Optional[dict] = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return {column: getattr(self, column) for column in COLUMNS}


def _ports(protocol: Optional[dict]) -> str:
    """``443`` or ``8000-8100``, comma separated, from a protocol's port list."""
    ports = (protocol or {}).get("ports") or []
    return ",".join(str(p["start"]) if p["start"] == p["end"] else f"{p['start']}-{p['end']}" for p in ports)


def _restriction(label: str, protocol: Optional[dict]) -> Optional[str]:
    if (protocol or {}).get("policy") != "RESTRICTED":
        return None
    ports = _ports(protocol)
    return f"{label} is limited to {ports}" if ports else f"{label} is restricted (no ports)"


def plan_resource(node: Optional[dict], asked_for: str) -> Row:
    """What converting ``node`` (the API's answer for ``asked_for``) would do, as a Row; ``variables`` is the update to send."""
    if not node:
        return Row(asked_for, status=BLOCKED, detail="no Resource with this ID")
    row = Row(node.get("id") or asked_for, node.get("name") or "")
    policy = node.get("securityPolicy") or {}
    protocols = node.get("protocols") or {}
    row.securityPolicyId, row.securityPolicyName = policy.get("id") or "", policy.get("name") or ""
    row.allowIcmp = protocols.get("allowIcmp")
    row.tcpPolicy, row.tcpPorts = (protocols.get("tcp") or {}).get("policy") or "", _ports(protocols.get("tcp"))
    row.udpPolicy, row.udpPorts = (protocols.get("udp") or {}).get("policy") or "", _ports(protocols.get("udp"))
    routing = node.get("routingMode")
    if routing is None:
        row.status = BLOCKED
        row.detail = f"a {node.get('__typename') or 'non-network'} has no routing mode; only network Resources can bypass Twingate"
        return row
    if routing == BYPASS:
        row.status, row.detail = ALREADY, "nothing to do"
        return row

    clears = []
    variables: dict = {"id": row.id}
    if row.securityPolicyId:
        clears.append(f"Security Policy '{row.securityPolicyName or row.securityPolicyId}' is removed")
        variables["securityPolicyId"] = None
    restricted = [text for text in (_restriction("TCP", protocols.get("tcp")), _restriction("UDP", protocols.get("udp"))) if text]
    if protocols.get("allowIcmp") is False:
        restricted.append("ICMP is blocked")
    if restricted:
        clears.append("; ".join(restricted) + ", so all ports and ICMP are opened")
        variables["protocols"] = copy.deepcopy(OPEN_PROTOCOLS)
    row.status = WOULD_CONVERT
    row.detail = "; ".join(clears) if clears else "only the routing mode changes"
    row.variables = variables
    return row


def counts(rows: list) -> dict:
    done: dict = {}
    for row in rows:
        done[row.status] = done.get(row.status, 0) + 1
    return done
