"""Tests for following nested GraphQL lists past the API's 50-item page limit."""

from __future__ import annotations

import pytest

from tgcli.pagination import NestedLists, PaginationError, complete_nested_lists, fetch_connection

QUERY = "query($id: ID!, $cursor: String) { ... }"
NESTED = NestedLists("group", {"users": QUERY, "resources": QUERY})


class FakeClient:
    """Serves ``items`` for any continuation query in pages of ``page`` items, as the real API would."""

    def __init__(self, items: dict[tuple[str, str], list[dict]], page: int = 2) -> None:
        self.items, self.page, self.calls = items, page, []
        self.vanished: set[str] = set()
        self.stuck = False

    def execute(self, query: str, variables: dict) -> dict:
        self.calls.append(variables)
        parent_id, cursor = variables["id"], variables["cursor"]
        if parent_id in self.vanished:
            return {"data": {"group": None}}
        edges = self.items[(parent_id, self.field)]
        start = 0 if cursor is None else int(cursor[1:])
        more = start + self.page < len(edges)
        end = "c0" if self.stuck else f"c{start + self.page}"
        return {"data": {"group": {self.field: {
            "totalCount": len(edges), "pageInfo": {"hasNextPage": more, "endCursor": end if more else None},
            "edges": edges[start : start + self.page],
        }}}}


def edges(prefix: str, n: int) -> list[dict]:
    return [{"node": {"id": f"{prefix}{i}"}} for i in range(n)]


def first_page(all_edges: list[dict], page: int = 2, total: int | None = None) -> dict:
    more = len(all_edges) > page
    return {
        "totalCount": len(all_edges) if total is None else total,
        "pageInfo": {"hasNextPage": more, "endCursor": f"c{page}" if more else None},
        "edges": all_edges[:page],
    }


def client_for(field: str, items: dict, page: int = 2) -> FakeClient:
    client = FakeClient(items, page)
    client.field = field
    return client


class TestFetchConnection:
    def test_single_page(self):
        client = client_for("users", {("g", "users"): edges("u", 2)})
        got, total, found = fetch_connection(client, QUERY, {"id": "g"}, ["group", "users"])
        assert [e["node"]["id"] for e in got] == ["u0", "u1"] and total == 2 and found is True
        assert len(client.calls) == 1

    def test_follows_every_page_in_order(self):
        client = client_for("users", {("g", "users"): edges("u", 7)})
        got, total, _ = fetch_connection(client, QUERY, {"id": "g"}, ["group", "users"])
        assert [e["node"]["id"] for e in got] == [f"u{i}" for i in range(7)] and total == 7
        assert [c["cursor"] for c in client.calls] == [None, "c2", "c4", "c6"]

    def test_can_start_from_a_given_cursor(self):
        client = client_for("users", {("g", "users"): edges("u", 7)})
        got, _, _ = fetch_connection(client, QUERY, {"id": "g"}, ["group", "users"], cursor="c4")
        assert [e["node"]["id"] for e in got] == ["u4", "u5", "u6"]

    def test_missing_parent_is_reported_not_raised(self):
        client = client_for("users", {})
        client.vanished.add("g")
        assert fetch_connection(client, QUERY, {"id": "g"}, ["group", "users"]) == ([], None, False)

    def test_repeated_cursor_raises_instead_of_looping(self):
        client = client_for("users", {("g", "users"): edges("u", 9)})
        client.stuck = True
        with pytest.raises(PaginationError, match="same page cursor"):
            fetch_connection(client, QUERY, {"id": "g"}, ["group", "users"])


class TestCompleteNestedLists:
    def node(self, pid: str, **lists) -> dict:
        return {"id": pid, "name": pid, **lists}

    def run(self, nodes, items, field="users", page=2, nested=NESTED):
        client = client_for(field, items, page)
        problems = complete_nested_lists(client, nodes, nested)
        return client, problems

    def test_appends_the_missing_items_after_the_first_page_in_order(self):
        all_edges = edges("u", 5)
        node = self.node("g", users=first_page(all_edges))
        client, problems = self.run([node], {("g", "users"): all_edges})
        assert [e["node"]["id"] for e in node["users"]["edges"]] == [f"u{i}" for i in range(5)]
        assert problems == []
        assert client.calls[0] == {"id": "g", "cursor": "c2"}

    def test_removes_the_count_and_cursor_it_asked_for_so_the_shape_is_unchanged(self):
        node = self.node("g", users=first_page(edges("u", 5)))
        self.run([node], {("g", "users"): edges("u", 5)})
        assert set(node["users"]) == {"edges"}

    def test_a_complete_list_costs_no_extra_request_but_is_still_cleaned(self):
        node = self.node("g", users=first_page(edges("u", 2)))
        client, problems = self.run([node], {})
        assert client.calls == [] and problems == [] and set(node["users"]) == {"edges"}

    def test_only_truncated_parents_cost_a_request(self):
        long_edges = edges("u", 5)
        nodes = [self.node("a", users=first_page(edges("x", 1))), self.node("b", users=first_page(long_edges)),
                 self.node("c", users=first_page(edges("y", 2)))]
        client, _ = self.run(nodes, {("b", "users"): long_edges})
        assert {c["id"] for c in client.calls} == {"b"}

    def test_each_nested_field_is_completed_with_its_own_query(self):
        seen = []

        class TwoFields(FakeClient):
            def execute(self, query, variables):
                seen.append(query)
                self.field = "users" if query == "Q-users" else "resources"
                return super().execute(query, variables)

        users, resources = edges("u", 5), edges("r", 4)
        client = TwoFields({("g", "users"): users, ("g", "resources"): resources})
        node = self.node("g", users=first_page(users), resources=first_page(resources))
        problems = complete_nested_lists(client, [node], NestedLists("group", {"users": "Q-users", "resources": "Q-resources"}))
        assert problems == [] and len(node["users"]["edges"]) == 5 and len(node["resources"]["edges"]) == 4
        assert set(seen) == {"Q-users", "Q-resources"}

    def test_old_shaped_nodes_without_counts_or_cursors_are_left_alone(self):
        node = self.node("g", users={"edges": edges("u", 3)})
        client, problems = self.run([node], {})
        assert client.calls == [] and problems == [] and len(node["users"]["edges"]) == 3

    def test_null_or_missing_nested_lists_are_skipped(self):
        nodes = [self.node("a", users=None), self.node("b")]
        client, problems = self.run(nodes, {})
        assert client.calls == [] and problems == []

    def test_a_count_that_still_disagrees_is_reported(self):
        all_edges = edges("u", 5)
        node = self.node("g", users=first_page(all_edges, total=6))
        _, problems = self.run([node], {("g", "users"): all_edges})
        assert problems == ["g users: API reports 6, listed 5"]

    def test_a_parent_deleted_midway_is_reported_not_raised(self):
        node = self.node("g", users=first_page(edges("u", 5)))
        client = client_for("users", {})
        client.vanished.add("g")
        problems = complete_nested_lists(client, [node], NESTED)
        assert any("g" in p and "disappeared" in p for p in problems)
        assert len(node["users"]["edges"]) == 2  # what was already fetched is kept
