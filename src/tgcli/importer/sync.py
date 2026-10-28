"""What `--sync` changes on something that already exists. Pure: it compares the file with what the tenant holds.

Only what the file actually states is compared (``given`` on each spec): a blank CSV cell or a missing JSON key says
nothing, so it is never "fixed". A setting is only ever set to what the file says, never cleared: the file having no
Security Policy or alias is not a request to take one away.

Each function returns the changed values in the shape the API takes, plus short words for the plan and the report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

MANUAL = {"mode": "MANUAL"}


def _ports(protocol: dict) -> tuple:
    return protocol.get("policy"), sorted((p["start"], p["end"]) for p in protocol.get("ports") or [])


def _protocol(protocol: dict) -> dict:
    return {"policy": protocol.get("policy"), "ports": [{"start": p["start"], "end": p["end"]} for p in protocol.get("ports") or []]}


def _same_access_policy(wanted: Optional[dict], have: Optional[dict]) -> bool:
    wanted, have = wanted or MANUAL, have or MANUAL
    if wanted.get("mode") != have.get("mode"):
        return False
    return wanted["mode"] == "MANUAL" or wanted.get("durationSeconds") == have.get("durationSeconds")


def _when(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def is_past(text: Optional[str]) -> bool:
    """True when an expiry time has already gone by."""
    when = _when(text)
    return when is not None and when <= datetime.now(timezone.utc)


def _same_time(wanted: Optional[str], have: Optional[str]) -> bool:
    a, b = _when(wanted), _when(have)
    return a == b if a and b else wanted == have


def resource_changes(spec: Any, node: dict, policy_id: Optional[str], prune: bool) -> tuple:
    """(variables for resourceUpdate, words describing the changes) for an existing resource. Both empty when it already matches."""
    given = spec.given
    changes: dict = {}
    words: list = []

    if "alias" in given and spec.alias != (node.get("alias") or ""):
        changes["alias"] = spec.alias
        words.append("alias")

    current = node.get("protocols") or {}
    if current:
        wanted = {
            "allowIcmp": spec.protocols["allowIcmp"] if "icmp" in given else current["allowIcmp"],
            "tcp": spec.protocols["tcp"] if "tcp" in given else current["tcp"],
            "udp": spec.protocols["udp"] if "udp" in given else current["udp"],
        }
        parts = []
        if wanted["allowIcmp"] != current["allowIcmp"]:
            parts.append("ICMP")
        if _ports(wanted["tcp"]) != _ports(current["tcp"]):
            parts.append("TCP ports")
        if _ports(wanted["udp"]) != _ports(current["udp"]):
            parts.append("UDP ports")
        if parts:
            changes["protocols"] = {"allowIcmp": wanted["allowIcmp"], "tcp": _protocol(wanted["tcp"]), "udp": _protocol(wanted["udp"])}
            words.extend(parts)

    if "visible" in given and spec.is_visible != node.get("isVisible"):
        changes["isVisible"] = spec.is_visible
        words.append("visibility")
    if "browser_shortcut" in given and spec.browser_shortcut != node.get("isBrowserShortcutEnabled"):
        changes["isBrowserShortcutEnabled"] = spec.browser_shortcut
        words.append("browser shortcut")
    if "security_policy" in given and policy_id != (node.get("securityPolicy") or {}).get("id"):
        changes["securityPolicyId"] = policy_id
        words.append("Security Policy")
    if "routing_mode" in given and spec.routing_mode != node.get("routingMode"):
        changes["routingMode"] = spec.routing_mode
        words.append("routing")

    if "access_policy" in given and not _same_access_policy(spec.access_policy, node.get("accessPolicy")):
        changes["accessPolicy"] = spec.access_policy or dict(MANUAL)
        words.append("access policy")
    if "approval_mode" in given and spec.approval_mode != (node.get("approvalMode") or "MANUAL"):
        changes["approvalMode"] = spec.approval_mode
        words.append("approval mode")
    if "accessPolicy" in changes and "approvalMode" not in changes:
        # Changing the access policy alone can reset the approval mode to MANUAL, so the current one is sent along.
        changes["approvalMode"] = node.get("approvalMode") or "MANUAL"

    if "tags" in given:
        have = {t["key"]: t["value"] for t in node.get("tags") or []}
        file = {t["key"]: t["value"] for t in spec.tags}
        wanted = file if prune else {**have, **file}
        if wanted != have:
            changes["tags"] = [{"key": k, "value": v} for k, v in wanted.items()]
            words.append("tags")
    return changes, words


def grant_changes(entry: Any, edge: dict, policy_id: Optional[str], expired: bool) -> tuple:
    """(settings to send with resourceAccessAdd, words, warning or None) for a group that already has access.

    The settings carry only what differs. A changed access policy also carries the approval mode, for the reason above.
    """
    given = entry.given
    settings: dict = {}
    words: list = []
    warning = None
    if "security_policy" in given and policy_id != edge.get("policy_id"):
        settings["policy_id"] = policy_id
        words.append("Security Policy")
    if "access_policy" in given and not _same_access_policy(entry.access_policy, edge.get("access_policy")):
        settings["access_policy"] = entry.access_policy or dict(MANUAL)
        words.append("access policy")
    if "approval_mode" in given and entry.approval_mode != (edge.get("approval_mode") or "MANUAL"):
        settings["approval_mode"] = entry.approval_mode
        words.append("approval mode")
    if "expires_at" in given and not _same_time(entry.expires_at, edge.get("expires_at")):
        if expired:
            warning = f"expiry of access for group '{entry.group}' not changed: it expired on {entry.expires_at}"
        else:
            settings["expires_at"] = entry.expires_at
            words.append("expiry")
    if "access_policy" in settings and "approval_mode" not in settings:
        settings["approval_mode"] = edge.get("approval_mode") or "MANUAL"
    return settings, words, warning
