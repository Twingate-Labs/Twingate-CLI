"""group list and network list must show every item of a nested list, not just the API's first 50."""

from __future__ import annotations

import copy
import csv
import io
import json
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError
from tgcli.client.session import SessionManager
from tgcli.main import app
from tgcli.queries import groups as gq
from tgcli.queries import networks as nq

runner = CliRunner()
SESSION = "TestSess"
PAGE = 2


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def ref_edges(prefix: str, n: int) -> list[dict]:
    return [{"node": {"id": f"{prefix}{i}", "name": f"{prefix} {i}"}} for i in range(n)]


def first_page(all_edges: list[dict], total: int | None = None) -> dict:
    more = len(all_edges) > PAGE
    return {
        "totalCount": len(all_edges) if total is None else total,
        "pageInfo": {"hasNextPage": more, "endCursor": f"c{PAGE}" if more else None},
        "edges": all_edges[:PAGE],
    }


class Api:
    """A fake client whose paginate() returns top-level pages and whose execute() serves continuations."""

    def __init__(self, top_key: str, parent_field: str, nodes: list[dict], full: dict[tuple[str, str], list[dict]]):
        self.top_key, self.parent_field, self.nodes, self.full = top_key, parent_field, nodes, full
        self.executed: list[tuple[str, dict]] = []
        self.error: Exception | None = None
        self.vanished: set[str] = set()
        self.stuck = False

    def paginate(self, query, make_vars, data_key):
        assert data_key == self.top_key
        return [[{"node": n} for n in self.nodes]]

    def execute(self, query, variables):
        self.executed.append((query, variables))
        if self.error:
            raise self.error
        field = re.search(r"(\w+)\(after: \$cursor\)", query).group(1)
        assert re.search(rf"\{{ {self.parent_field}\(id: \$id\)", query), query
        if variables["id"] in self.vanished:
            return {"data": {self.parent_field: None}}
        all_edges = self.full[(variables["id"], field)]
        start = int(variables["cursor"][1:])
        if self.stuck:
            return {"data": {self.parent_field: {field: {
                "pageInfo": {"hasNextPage": True, "endCursor": variables["cursor"]}, "edges": all_edges[start : start + PAGE],
            }}}}
        more = start + PAGE < len(all_edges)
        return {"data": {self.parent_field: {field: {
            "pageInfo": {"hasNextPage": more, "endCursor": f"c{start + PAGE}" if more else None},
            "edges": all_edges[start : start + PAGE],
        }}}}


def run(api: Api, *args: str):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.paginate.side_effect = api.paginate
        inst.execute.side_effect = api.execute
        return runner.invoke(app, ["-s", SESSION, *args])


def group_api(n_users=5, n_resources=3, total_users: int | None = None) -> Api:
    users = [{"node": {"id": f"u{i}", "email": f"u{i}@x.io", "firstName": "A", "lastName": "B"}} for i in range(n_users)]
    resources = [{"node": {"id": f"r{i}", "name": f"R{i}", "address": {"type": "DNS", "value": "x"}, "isActive": True}} for i in range(n_resources)]
    node = {"id": "g1", "name": "Admins", "createdAt": "t", "updatedAt": "t", "isActive": True, "type": "MANUAL",
            "users": first_page(users, total_users), "resources": first_page(resources)}
    return Api("groups", "group", [node], {("g1", "users"): users, ("g1", "resources"): resources})


def network_api(n_resources=5, n_connectors=1) -> Api:
    resources, connectors = ref_edges("r", n_resources), ref_edges("c", n_connectors)
    node = {"id": "rn1", "name": "VPC", "updatedAt": "t", "createdAt": "t", "isActive": True,
            "connectors": first_page(connectors), "resources": first_page(resources)}
    return Api("remoteNetworks", "remoteNetwork", [node], {("rn1", "connectors"): connectors, ("rn1", "resources"): resources})


class TestGroupList:
    def test_json_lists_every_user_and_resource(self):
        result = run(group_api(), "group", "list")
        assert result.exit_code == 0, result.output
        node = json.loads(result.output)[0][0]["node"]
        assert [e["node"]["id"] for e in node["users"]["edges"]] == [f"u{i}" for i in range(5)]
        assert [e["node"]["id"] for e in node["resources"]["edges"]] == ["r0", "r1", "r2"]

    def test_added_items_have_the_same_fields_as_the_first_page(self):
        node = json.loads(run(group_api(), "group", "list").output)[0][0]["node"]
        assert {tuple(sorted(e["node"])) for e in node["users"]["edges"]} == {("email", "firstName", "id", "lastName")}
        assert {tuple(sorted(e["node"])) for e in node["resources"]["edges"]} == {("address", "id", "isActive", "name")}

    def test_output_shape_is_unchanged_no_count_or_cursor_leaks_into_json(self):
        node = json.loads(run(group_api(), "group", "list").output)[0][0]["node"]
        assert set(node["users"]) == {"edges"} and set(node["resources"]) == {"edges"}

    def test_csv_shows_every_id(self):
        result = run(group_api(), "-f", "csv", "group", "list")
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["users"] == str([f"u{i}" for i in range(5)])
        assert row["resources"] == "['r0', 'r1', 'r2']"

    def test_follow_up_requests_are_made_only_for_truncated_lists(self):
        api = group_api(n_users=5, n_resources=2)
        run(api, "group", "list")
        assert len(api.executed) == 2
        assert all("group(id: $id)" in q and "users(after: $cursor)" in q for q, _ in api.executed)
        assert api.executed[0][1] == {"id": "g1", "cursor": "c2"}

    def test_nothing_truncated_means_no_extra_requests(self):
        api = group_api(n_users=2, n_resources=1)
        result = run(api, "group", "list")
        assert result.exit_code == 0 and api.executed == []

    def test_a_count_mismatch_warns_on_stderr_but_still_lists(self):
        result = run(group_api(total_users=9), "group", "list")
        assert result.exit_code == 0
        assert "Warning: g1 users: API reports 9, listed 5" in result.output
        assert json.loads(result.output[result.output.index("["):])

    def test_many_problems_are_capped_on_screen(self):
        api = group_api(total_users=9)
        first = api.nodes[0]
        api.nodes = [{**copy.deepcopy(first), "id": f"g{i}"} for i in range(7)]  # separate dicts, as in a real response
        api.full = {(f"g{i}", f): v for i in range(7) for (_, f), v in group_api().full.items()}
        result = run(api, "group", "list")
        assert result.exit_code == 0
        assert result.output.count("Warning: g") == 5 and "Warning: ... and 2 more" in result.output

    def test_a_vanished_group_warns_but_does_not_fail(self):
        api = group_api()
        api.vanished.add("g1")
        result = run(api, "group", "list")
        assert result.exit_code == 0 and "disappeared" in result.output

    def test_a_cursor_that_never_advances_stops_with_a_clear_error(self):
        api = group_api()
        api.stuck = True
        result = run(api, "group", "list")
        assert result.exit_code == 1 and "same page cursor" in result.output

    def test_api_error_during_follow_up_exits_nonzero(self):
        api = group_api()
        api.error = TwingateAPIError("boom")
        result = run(api, "group", "list")
        assert result.exit_code == 1 and "API error: boom" in result.output


class TestNetworkList:
    def test_json_lists_every_resource_and_connector(self):
        result = run(network_api(n_resources=5, n_connectors=3), "network", "list")
        assert result.exit_code == 0, result.output
        node = json.loads(result.output)[0][0]["node"]
        assert [e["node"]["id"] for e in node["resources"]["edges"]] == [f"r{i}" for i in range(5)]
        assert [e["node"]["id"] for e in node["connectors"]["edges"]] == ["c0", "c1", "c2"]
        assert set(node["resources"]) == {"edges"}

    def test_csv_shows_every_id(self):
        (row,) = list(csv.DictReader(io.StringIO(run(network_api(), "-f", "csv", "network", "list").output)))
        assert row["resources"] == str([f"r{i}" for i in range(5)])

    def test_follow_up_uses_the_remote_network_query(self):
        api = network_api()
        run(api, "network", "list")
        assert len(api.executed) == 2  # 5 resources in pages of 2: the first page, then cursors c2 and c4
        assert all("remoteNetwork(id: $id)" in q and "resources(after: $cursor)" in q for q, _ in api.executed)
        assert [v["cursor"] for _, v in api.executed] == ["c2", "c4"]

    def test_nothing_truncated_means_no_extra_requests(self):
        api = network_api(n_resources=2, n_connectors=1)
        run(api, "network", "list")
        assert api.executed == []

    def test_api_error_during_follow_up_exits_nonzero(self):
        api = network_api()
        api.error = TwingateAPIError("boom")
        assert run(api, "network", "list").exit_code == 1


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize(
    "module,list_query,continuations",
    [(gq, gq.LIST_GROUPS, gq.LIST_GROUPS_CONTINUATIONS), (nq, nq.LIST_NETWORKS, nq.LIST_NETWORKS_CONTINUATIONS)],
)
class TestQueriesStayInSync:
    def test_each_follow_up_selects_exactly_the_fields_the_list_selects(self, module, list_query, continuations):
        for field, edge in module._LIST_NESTED.items():
            assert edge in squash(list_query), field
            assert edge in squash(continuations[field]), field

    def test_list_query_asks_for_the_counts_needed_to_notice_truncation(self, module, list_query, continuations):
        for field in module._LIST_NESTED:
            assert f"{field} {{ totalCount pageInfo {{ hasNextPage endCursor }}" in squash(list_query)

    def test_follow_ups_take_an_id_and_a_cursor_that_may_be_null(self, module, list_query, continuations):
        for query in continuations.values():
            assert query.startswith("query($id: ID!, $cursor: String)")
