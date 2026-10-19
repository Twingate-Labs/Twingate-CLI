"""Cursor pagination for nested GraphQL lists.

The API returns at most 50 items per page and silently clamps any larger ``first``. A list query that
selects a nested list (a group's users, a network's resources) without following its cursor therefore
drops everything past the 50th item.
"""

from __future__ import annotations

from typing import Any, NamedTuple


class PaginationError(Exception):
    """A connection could not be followed to its end."""


class NestedLists(NamedTuple):
    parent: str  # single-object query field, e.g. "group"
    continuations: dict[str, str]  # nested field -> query taking $id and $cursor that returns that field's next page


def _dig(data: Any, path: list[str]) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def fetch_connection(
    client: Any, query: str, variables: dict, path: list[str], cursor: str | None = None
) -> tuple[list[dict], int | None, bool]:
    """Follow a cursor-paginated connection to its end.

    Returns (edges, totalCount or None, found). ``found`` is False when the object at ``path`` is gone,
    e.g. a parent deleted while the command was running.
    """
    edges: list[dict] = []
    total: int | None = None
    while True:
        connection = _dig(client.execute(query, {**variables, "cursor": cursor}).get("data"), path)
        if connection is None:
            return edges, total, False
        edges.extend(connection["edges"])
        total = connection.get("totalCount", total)
        info = connection["pageInfo"]
        if not info["hasNextPage"]:
            return edges, total, True
        if info["endCursor"] == cursor:
            raise PaginationError("The API returned the same page cursor twice; stopping instead of looping forever.")
        cursor = info["endCursor"]


def complete_nested_lists(client: Any, nodes: list[dict], nested: NestedLists) -> list[str]:
    """Append the pages missing from each node's nested lists, in place, so every list is complete.

    A nested connection carries ``totalCount`` and ``pageInfo`` only so truncation can be seen; both are
    removed afterwards so the node keeps the shape the list query always produced. Returns problems
    (counts that still don't match the API's total, parents that vanished) for the caller to report.
    """
    problems: list[str] = []
    for node in nodes:
        for field, query in nested.continuations.items():
            connection = node.get(field)
            if not isinstance(connection, dict):
                continue
            info = connection.get("pageInfo") or {}
            if info.get("hasNextPage"):
                more, _, found = fetch_connection(
                    client, query, {"id": node["id"]}, [nested.parent, field], cursor=info.get("endCursor")
                )
                if found:
                    connection["edges"].extend(more)
                else:
                    problems.append(f"{node['id']}: disappeared while its {field} were being read")
            expected = connection.get("totalCount")
            if expected is not None and len(connection["edges"]) != expected:
                problems.append(f"{node['id']} {field}: API reports {expected}, listed {len(connection['edges'])}")
            connection.pop("pageInfo", None)
            connection.pop("totalCount", None)
    return problems
