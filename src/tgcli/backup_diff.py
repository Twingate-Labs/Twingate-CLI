"""Compare two `tgcli backup` folders: what was added, removed or changed between them. Offline, no API calls.

Objects are matched by ID. Inside an object, lists of things that have an ID (group members, a resource's access, tags
by key) are matched the same way, so a reordering is not a change and a changed setting is reported on the thing it
belongs to. Fields that change on their own (last heartbeat, last login, ``updatedAt``) are left out unless asked for,
because they would drown out everything else; a real change always shows in some other field.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from tgcli.backup import MANIFEST_FILE, MANIFEST_FORMAT
from tgcli.queries import backup as q
from tgcli.textio import TextFileError, read_text

# Fields skipped everywhere in an entity, and fields skipped only in one (by entity key).
VOLATILE_EVERYWHERE = frozenset({"updatedAt"})
VOLATILE = {
    "connectors": frozenset({"lastHeartbeatAt"}),
    "devices": frozenset({"lastSuccessfulLoginAt", "lastFailedLoginAt"}),
}


class DiffError(Exception):
    """The two folders cannot be compared (not backups, different tenants, unreadable files)."""


@dataclass
class Backup:
    path: Path
    manifest: dict
    items: dict[str, list]  # entity key -> the objects in its file
    warnings: list[str] = field(default_factory=list)

    @property
    def tenant(self) -> str:
        return self.manifest.get("tenant") or "unknown"

    @property
    def created(self) -> str:
        return self.manifest.get("createdAt") or "unknown time"


@dataclass
class Change:
    kind: str  # "added" | "removed" | "changed"
    path: str  # where inside the object, e.g. "access[Eng].approvalMode"; "" for the whole object
    old: str = ""
    new: str = ""


@dataclass
class ObjectChange:
    id: str
    label: str
    changes: list[Change] = field(default_factory=list)


@dataclass
class TypeDiff:
    key: str
    label: str
    added: list[ObjectChange] = field(default_factory=list)
    removed: list[ObjectChange] = field(default_factory=list)
    changed: list[ObjectChange] = field(default_factory=list)
    ambiguous: set[str] = field(default_factory=set)  # labels shared by several objects, so their IDs are shown

    @property
    def total(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)


@dataclass
class BackupDiff:
    old: Backup
    new: Backup
    types: list[TypeDiff] = field(default_factory=list)
    not_compared: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def differences(self) -> int:
        return sum(t.total for t in self.types)


# ---------------------------------------------------------------- loading


def load_backup(path: Path) -> Backup:
    """Read a backup folder. Raises DiffError when it is not one; a damaged or unverified one only produces warnings."""
    if not path.is_dir():
        raise DiffError(f"{path} is not a folder; give the folders `tgcli backup` wrote.")
    manifest_path = path / MANIFEST_FILE
    if not manifest_path.is_file():
        raise DiffError(f"{path} has no {MANIFEST_FILE}, so it is not a `tgcli backup` folder.")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("format") != MANIFEST_FORMAT:
        raise DiffError(f"{manifest_path} is not a backup manifest this version understands (format {MANIFEST_FORMAT}).")

    backup = Backup(path, manifest, {})
    problems = (manifest.get("verification") or {}).get("problems") or []
    if problems:
        backup.warnings.append(
            f"{path} was not fully verified when it was made ({len(problems)} problem(s), see its {MANIFEST_FILE}); "
            "something may be missing from it."
        )
    for entity in q.ENTITIES:
        file = path / entity.file
        if not file.is_file():
            continue
        data = file.read_bytes()
        recorded = (manifest.get("files") or {}).get(entity.file, {}).get("sha256")
        if recorded and recorded != hashlib.sha256(data).hexdigest():
            backup.warnings.append(
                f"{file} does not match the checksum in its manifest, so it may have been changed since the backup was made."
            )
        items = _read_json(file)
        if not isinstance(items, list) or not all(isinstance(i, dict) and "id" in i for i in items):
            raise DiffError(f"{file} must hold a list of objects that each have an id, like the files `tgcli backup` writes.")
        backup.items[entity.key] = items
    return backup


def _read_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except (OSError, TextFileError) as exc:
        raise DiffError(f"Cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DiffError(f"{path} is not valid JSON: {exc}") from exc


# ---------------------------------------------------------------- labels


def _name(value: Any) -> str:
    """What to call an object or list element: its name, email, address, key or, failing those, its id."""
    if isinstance(value, dict):
        principal = value.get("principal")
        if isinstance(principal, dict):
            return _name(principal)
        for key in ("name", "email", "address", "key", "id"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _text(value: Any) -> str:
    """A value as it is printed in a change."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        if set(value) == {"key", "value"}:
            return f"{value['key']}={value['value']}"
        if set(value) == {"start", "end"}:
            return f"{value['start']}-{value['end']}"
        return _name(value)
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value) if value else "none"
    return str(value)


def _identity(element: Any) -> Optional[str]:
    """What identifies a list element across two backups, or None when it has nothing to match on (ports, plain strings)."""
    if not isinstance(element, dict):
        return None
    principal = element.get("principal")
    if isinstance(principal, dict) and principal.get("id") is not None:
        return str(principal["id"])
    for key in ("id", "key"):
        if element.get(key) is not None:
            return str(element[key])
    return None


# ---------------------------------------------------------------- comparing values


def _diff_value(path: str, old: Any, new: Any, skip: frozenset, out: list[Change]) -> None:
    if old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        if "id" in old and "id" in new and old["id"] != new["id"]:
            out.append(Change("changed", path, _text(old), _text(new)))  # a different thing, not an edit of the same one
            return
        for key in [*old, *(k for k in new if k not in old)]:
            if key not in skip:
                _diff_value(f"{path}.{key}" if path else key, old.get(key), new.get(key), skip, out)
    elif isinstance(old, list) and isinstance(new, list):
        _diff_list(path, old, new, skip, out)
    else:
        out.append(Change("changed", path, _text(old), _text(new)))


def _diff_list(path: str, old: list, new: list, skip: frozenset, out: list[Change]) -> None:
    old_ids, new_ids = [_identity(e) for e in old], [_identity(e) for e in new]
    matchable = (
        all(i is not None for i in old_ids + new_ids) and len(set(old_ids)) == len(old_ids) and len(set(new_ids)) == len(new_ids)
    )
    if matchable:
        old_by, new_by = dict(zip(old_ids, old)), dict(zip(new_ids, new))
        for ident, element in new_by.items():
            if ident not in old_by:
                out.append(Change("added", path, new=_text(element)))
        for ident, element in old_by.items():
            if ident not in new_by:
                out.append(Change("removed", path, old=_text(element)))
        for ident, element in new_by.items():
            if ident in old_by:
                _diff_value(f"{path}[{_name(element)}]", old_by[ident], element, skip, out)
        return
    # Nothing to match on: compare as sets of whatever the elements are.
    canonical = lambda e: json.dumps(e, sort_keys=True, ensure_ascii=False)  # noqa: E731
    old_set, new_set = {canonical(e) for e in old}, {canonical(e) for e in new}
    for element in new:
        if canonical(element) not in old_set:
            out.append(Change("added", path, new=_text(element)))
    for element in old:
        if canonical(element) not in new_set:
            out.append(Change("removed", path, old=_text(element)))


# ---------------------------------------------------------------- comparing backups


def compare(old: Backup, new: Backup, include_volatile: bool = False) -> BackupDiff:
    """What changed between two backups of the same tenant."""
    if old.tenant != new.tenant:
        raise DiffError(
            f"These are backups of different tenants ({old.tenant} and {new.tenant}); their IDs differ, so nothing would match."
        )
    result = BackupDiff(old, new, warnings=[*old.warnings, *new.warnings])
    if old.created > new.created and "unknown" not in (old.created, new.created):
        result.warnings.append(f"The first backup ({old.created}) is newer than the second ({new.created}); the comparison runs the other way round.")

    for entity in q.ENTITIES:
        in_old, in_new = entity.key in old.items, entity.key in new.items
        if not (in_old and in_new):
            if in_old or in_new:
                result.not_compared.append(f"{entity.label} (only in the {'first' if in_old else 'second'} backup)")
            continue
        skip = frozenset() if include_volatile else VOLATILE_EVERYWHERE | VOLATILE.get(entity.key, frozenset())
        result.types.append(_compare_type(entity, old.items[entity.key], new.items[entity.key], skip))
    return result


def _compare_type(entity: q.Entity, old_items: list, new_items: list, skip: frozenset) -> TypeDiff:
    diff = TypeDiff(entity.key, entity.label)
    old_by, new_by = {str(i["id"]): i for i in old_items}, {str(i["id"]): i for i in new_items}
    labels = Counter(_name(i) for i in [*old_items, *(n for ident, n in new_by.items() if ident not in old_by)])
    diff.ambiguous = {label for label, count in labels.items() if count > 1}
    for ident, item in new_by.items():
        if ident not in old_by:
            diff.added.append(ObjectChange(ident, _name(item)))
    for ident, item in old_by.items():
        if ident not in new_by:
            diff.removed.append(ObjectChange(ident, _name(item)))
    for ident, item in new_by.items():
        if ident in old_by:
            changes: list[Change] = []
            _diff_value("", old_by[ident], item, skip, changes)
            if changes:
                diff.changed.append(ObjectChange(ident, _name(item), changes))
    return diff


# ---------------------------------------------------------------- reporting


def to_dict(diff: BackupDiff) -> dict:
    """The comparison as plain data, for --json."""
    def objects(items: list[ObjectChange]) -> list[dict]:
        return [
            {"id": o.id, "name": o.label, "changes": [{"kind": c.kind, "path": c.path, "old": c.old, "new": c.new} for c in o.changes]}
            for o in items
        ]

    return {
        "tenant": diff.new.tenant,
        "old": {"path": str(diff.old.path), "createdAt": diff.old.created},
        "new": {"path": str(diff.new.path), "createdAt": diff.new.created},
        "differences": diff.differences,
        "warnings": diff.warnings,
        "notCompared": diff.not_compared,
        "types": {
            t.key: {"added": objects(t.added), "removed": objects(t.removed), "changed": objects(t.changed)} for t in diff.types
        },
    }


def _line(change: Change) -> str:
    where = f" {change.path}" if change.path else ""
    if change.kind == "added":
        return f"+{where}: {change.new}"
    if change.kind == "removed":
        return f"-{where}: {change.old}"
    return f"~{where}: {change.old} -> {change.new}"


def render(diff: BackupDiff) -> str:
    """The comparison as text for a person."""
    lines = [
        f"Comparing backups of {diff.new.tenant}",
        f"  first   {diff.old.path}  ({diff.old.created})",
        f"  second  {diff.new.path}  ({diff.new.created})",
    ]
    for entry in diff.types:
        if not entry.total:
            continue
        lines.append("")
        lines.append(f"{entry.label}: {len(entry.added)} added, {len(entry.removed)} removed, {len(entry.changed)} changed")

        def name(o: ObjectChange) -> str:
            return f"{o.label}  ({o.id})" if o.label in entry.ambiguous else o.label

        for marker, objects in (("+", entry.added), ("-", entry.removed)):
            lines.extend(f"  {marker} {name(o)}" for o in objects)
        for o in entry.changed:
            lines.append(f"  ~ {name(o)}")
            lines.extend(f"      {_line(c)}" for c in o.changes)
    lines.append("")
    if diff.differences:
        counted = sum(1 for t in diff.types if t.total)
        lines.append(f"{diff.differences} object(s) differ, in {counted} type(s).")
    else:
        lines.append("No differences.")
    if diff.not_compared:
        lines.append(f"Not compared: {'; '.join(diff.not_compared)}.")
    return "\n".join(lines)
