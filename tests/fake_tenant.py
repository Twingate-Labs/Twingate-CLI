"""A fake Twingate API for backup tests: serves tiny pages (2 items) so pagination is always exercised."""

from __future__ import annotations

import re
from typing import Any

from tgcli.queries import backup as q

PAGE = 2
ROOTS = {e.root: e.key for e in q.ENTITIES}
PARENTS = {e.parent: e.key for e in q.ENTITIES}
NESTED = {e.key: e.nested for e in q.ENTITIES}


def edge(node: dict, **extra: Any) -> dict:
    return {"node": node, **extra}


class FakeTenant:
    """``data`` maps entity key -> list of items whose nested lists are plain lists of *edges*."""

    def __init__(self, data: dict[str, list[dict]]) -> None:
        self.data = {e.key: [dict(i) for i in data.get(e.key, [])] for e in q.ENTITIES}
        self.calls: list[tuple[str, dict]] = []
        self.total_override: dict[str, int] = {}
        self.nested_total_override: dict[tuple[str, str], int] = {}
        self.vanished: set[str] = set()
        self.stuck_cursor = False
        self.error: Exception | None = None
        self.fail_after: int | None = None

    @staticmethod
    def _offset(cursor: str | None) -> int:
        return 0 if cursor is None else int(cursor[1:])

    def _page(self, edges: list[dict], cursor: str | None) -> tuple[list[dict], dict]:
        start = self._offset(cursor)
        chunk = edges[start : start + PAGE]
        more = start + PAGE < len(edges)
        end = "c0" if self.stuck_cursor else f"c{start + PAGE}"
        return chunk, {"hasNextPage": more, "endCursor": end if more else None}

    def _connection(self, key: str, field: str, edges: list[dict], cursor: str | None, with_total: bool) -> dict:
        chunk, info = self._page(edges, cursor)
        out = {"pageInfo": info, "edges": chunk}
        if with_total:
            out["totalCount"] = self.nested_total_override.get((key, field), len(edges))
        return out

    def execute(self, query: str, variables: dict | None = None) -> dict:
        variables = variables or {}
        self.calls.append((query, variables))
        if self.error is not None and (self.fail_after is None or len(self.calls) > self.fail_after):
            raise self.error
        cursor = variables.get("cursor")

        top = re.match(r"query\(\$cursor: String\) \{ (\w+)\(after: \$cursor\)", query)
        if top:
            key = ROOTS[top.group(1)]
            items = self.data[key]
            chunk, info = self._page(items, cursor)
            nodes = []
            for item in chunk:
                node = {k: v for k, v in item.items() if k not in NESTED[key]}
                for name in NESTED[key]:
                    node[name] = self._connection(key, name, item.get(name, []), None, True)
                nodes.append({"node": node})
            total = self.total_override.get(key, len(items))
            return {"data": {top.group(1): {"totalCount": total, "pageInfo": info, "edges": nodes}}}

        cont = re.match(r"query\(\$id: ID!, \$cursor: String\) \{ (\w+)\(id: \$id\)", query)
        assert cont, f"unrecognised query: {query[:80]}"
        key = PARENTS[cont.group(1)]
        name = re.search(r"(\w+)\(after: \$cursor\)", query[cont.end():]).group(1)
        if variables["id"] in self.vanished:
            return {"data": {cont.group(1): None}}
        item = next(i for i in self.data[key] if i["id"] == variables["id"])
        connection = self._connection(key, name, item.get(name, []), cursor, False)
        return {"data": {cont.group(1): {name: connection}}}


def many(prefix: str, n: int, **extra: Any) -> list[dict]:
    return [{"id": f"{prefix}{i}", "name": f"{prefix} {i}", **extra} for i in range(n)]
