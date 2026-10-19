"""Tenant backup: collect groups, users, resources, connectors and remote networks and write them to disk."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from tgcli import VERSION
from tgcli.pagination import PaginationError, fetch_connection
from tgcli.output.transformers.resources import TYPE_LABELS
from tgcli.queries import backup as q

MANIFEST_FILE = "manifest.json"
MANIFEST_FORMAT = 1
MAX_PROBLEMS_SHOWN = 10


class BackupError(Exception):
    """A backup could not be completed (as opposed to an API or authentication failure)."""


@dataclass
class Collected:
    items: dict[str, list[dict]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


@dataclass
class BackupResult:
    path: Path
    counts: dict[str, int]
    problems: list[str]


def _fetch_connection(
    client: Any, query: str, variables: dict, path: list[str], cursor: str | None = None
) -> tuple[list[dict], int | None, bool]:
    try:
        return fetch_connection(client, query, variables, path, cursor)
    except PaginationError as exc:
        raise BackupError(str(exc)) from exc


def _flatten_edge(entity: str, name: str, edge: dict) -> dict:
    node = edge["node"]
    if (entity, name) != ("resources", "access"):
        return node
    principal = {"type": node.get("__typename"), **{k: v for k, v in node.items() if k != "__typename"}}
    return {
        "principal": principal,
        "securityPolicy": edge.get("securityPolicy"),
        "accessPolicy": edge.get("accessPolicy"),
        "approvalMode": edge.get("approvalMode"),
        "expiresAt": edge.get("expiresAt"),
    }


def _complete_nested(client: Any, entity: q.Entity, item: dict, name: str, problems: list[str]) -> None:
    """Replace a nested connection with the full list of its items, following pages past the first."""
    connection = item[name]
    edges = list(connection["edges"])
    expected = connection["totalCount"]
    if connection["pageInfo"]["hasNextPage"]:
        more, _, found = _fetch_connection(
            client, q.CONTINUATION_QUERIES[(entity.key, name)], {"id": item["id"]}, [entity.parent, name],
            cursor=connection["pageInfo"]["endCursor"],
        )
        if not found:
            problems.append(f"{entity.label} {item['id']}: disappeared while its {name} were being read")
        edges.extend(more)
    if len(edges) != expected:
        problems.append(f"{entity.label} {item['id']} {name}: API reports {expected}, backed up {len(edges)}")
    item[name] = [_flatten_edge(entity.key, name, edge) for edge in edges]


def collect(client: Any, progress: Callable[[str], None] = lambda message: None) -> Collected:
    """Read every entity in full. Nothing is written; mismatches against the API's own counts become problems."""
    collected = Collected()
    for entity in q.ENTITIES:
        progress(f"Reading {entity.label}...")
        edges, expected, _ = _fetch_connection(client, q.LIST_QUERIES[entity.key], {}, [entity.root])
        items = [edge["node"] for edge in edges if edge.get("node")]
        if expected is not None and len(items) != expected:
            collected.problems.append(f"{entity.label}: API reports {expected}, backed up {len(items)}")
        for item in items:
            for name in entity.nested:
                _complete_nested(client, entity, item, name, collected.problems)
            if entity.key == "resources":
                typename = item.pop("__typename", None)
                item["type"] = TYPE_LABELS.get(typename, typename)
        collected.items[entity.key] = items
        progress(f"  {len(items)} {entity.label}")
    return collected


def _tenant_of(client: Any) -> str:
    return (urlparse(client.url).hostname or "").split(".")[0] or "unknown"


def default_output_path(client: Any, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"twingate-backup-{_tenant_of(client)}-{stamp}")


def _write_private(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)


def write_backup(
    collected: Collected, out_dir: Path, session: str, tenant: str, now: datetime | None = None
) -> BackupResult:
    """Write the files into ``<out_dir>.partial`` and rename it into place only once everything is on disk."""
    if out_dir.exists():
        raise BackupError(f"{out_dir} already exists; choose another --output or remove it first.")
    partial = out_dir.with_name(out_dir.name + ".partial")
    if partial.exists():
        raise BackupError(f"{partial} is left over from an interrupted backup; delete it and try again.")

    partial.mkdir(parents=True, mode=0o700)
    try:
        files: dict[str, dict] = {}
        counts: dict[str, int] = {}
        for entity in q.ENTITIES:
            items = collected.items[entity.key]
            data = (json.dumps(items, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            _write_private(partial / entity.file, data)
            files[entity.file] = {"count": len(items), "sha256": hashlib.sha256(data).hexdigest()}
            counts[entity.key] = len(items)
        manifest = {
            "format": MANIFEST_FORMAT,
            "tool": "tgcli",
            "tgcliVersion": VERSION,
            "tenant": tenant,
            "session": session,
            "createdAt": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "files": files,
            "verification": {"complete": not collected.problems, "problems": collected.problems},
            "notes": [
                "Pages are read one after another, not as a single transaction, so changes made while the backup "
                "ran may or may not be included.",
                "Secrets are never included: the API does not return connector tokens or service account keys.",
                "Not included: devices, service accounts and keys, security policies, DNS filtering profiles, "
                "gateways and certificate authorities (gateways appear only as references on remote networks).",
            ],
        }
        _write_private(partial / MANIFEST_FILE, (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode())
        partial.rename(out_dir)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return BackupResult(out_dir, counts, collected.problems)
