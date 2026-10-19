"""A fake API for tests that follow nested lists: serves the command's own query, and every follow-up page."""

from __future__ import annotations

import re
from typing import Any, Callable

PAGE = 2
LONG = 5  # more than one page of PAGE


def edges(prefix: str, n: int, **extra: Any) -> list[dict]:
    return [{"node": {"id": f"{prefix}{i}", "name": f"{prefix} {i}"}, **extra} for i in range(n)]


def first_page(all_edges: list[dict]) -> dict:
    more = len(all_edges) > PAGE
    return {"totalCount": len(all_edges), "pageInfo": {"hasNextPage": more, "endCursor": f"c{PAGE}" if more else None},
            "edges": all_edges[:PAGE]}


class Backend:
    """Serves the command's own query, and every follow-up query from the full lists it was given."""

    def __init__(self, main: Callable[[], Any], full: dict[tuple[str, str], list[dict]]):
        self.main, self.full, self.followups = main, full, []

    def paginate(self, query, make_vars, data_key):
        return self.main()

    def execute(self, query, variables):
        m = re.match(r"query\(\$id: ID!, \$cursor: String\) \{ (\w+)\(id: \$id\) \{ (.*) \} \}$", query)
        if not m:
            return self.main()
        parent, field = m.group(1), re.search(r"(\w+)\(after: \$cursor\)", m.group(2)).group(1)
        self.followups.append((parent, variables["id"], field, variables["cursor"]))
        all_edges = self.full[(variables["id"], field)]
        start = int(variables["cursor"][1:])
        more = start + PAGE < len(all_edges)
        return {"data": {parent: {field: {
            "pageInfo": {"hasNextPage": more, "endCursor": f"c{start + PAGE}" if more else None},
            "edges": all_edges[start : start + PAGE],
        }}}}
