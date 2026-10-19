"""mappings user-network and user-resource must follow a user's groups, and each group's resources, to the end."""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
PAGE = 2


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def conn(all_edges: list[dict]) -> dict:
    more = len(all_edges) > PAGE
    return {"totalCount": len(all_edges), "pageInfo": {"hasNextPage": more, "endCursor": f"c{PAGE}" if more else None},
            "edges": all_edges[:PAGE]}


def resource(i: int, network: str) -> dict:
    return {"node": {"id": f"r{i}", "name": f"res{i}", "remoteNetwork": {"id": network, "name": network}}}


def group_edge(gid: str, resources: list[dict]) -> dict:
    return {"node": {"id": gid, "name": gid.upper(), "resources": conn(resources)}}


class Tenant:
    """Users -> groups -> resources, served in pages of 2 like the API would (at 50)."""

    def __init__(self, users: dict[str, list[str]], group_resources: dict[str, list[dict]]):
        self.users, self.group_resources = users, group_resources
        self.calls: list[tuple[str, dict]] = []
        self.fail_on: str | None = None

    def _group_edges(self, gids: list[str]) -> list[dict]:
        return [group_edge(g, self.group_resources[g]) for g in gids]

    def _page(self, all_edges: list[dict], cursor: str | None) -> dict:
        start = 0 if cursor is None else int(cursor[1:])
        more = start + PAGE < len(all_edges)
        return {"pageInfo": {"hasNextPage": more, "endCursor": f"c{start + PAGE}" if more else None}, "edges": all_edges[start : start + PAGE]}

    def execute(self, query: str, variables: dict | None = None) -> dict:
        variables = variables or {}
        self.calls.append((query, variables))
        if self.fail_on and self.fail_on in query:
            raise TwingateAPIError("boom")
        cont = re.match(r"query\(\$id: ID!, \$cursor: String\) \{ (\w+)\(id: \$id\) \{ (\w+)\(after", query)
        if cont:
            parent, field = cont.groups()
            if parent == "user":
                all_edges = self._group_edges(self.users[variables["id"]])
            else:
                all_edges = self.group_resources[variables["id"]]
            return {"data": {parent: {field: self._page(all_edges, variables["cursor"])}}}
        if "query getUsers" in query:
            nodes = [{"node": {"id": uid, "firstName": uid, "lastName": "X", "email": f"{uid}@x.io", "groups": conn(self._group_edges(gids))}}
                     for uid, gids in self.users.items()]
            return {"data": {"users": {"edges": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
        if "query listUsers" in query:
            uid, gids = next(iter(self.users.items()))
            node = {"id": uid, "firstName": uid, "lastName": "X", "email": f"{uid}@x.io", "groups": conn([{"node": {"id": g}} for g in gids])}
            return {"data": {"users": {"edges": [{"node": node}], "pageInfo": {"hasNextPage": False}}}}
        if "query getGroup" in query:
            gid = variables["groupID"]
            return {"data": {"group": {"id": gid, "name": gid.upper(), "resources": {"edges": self.group_resources[gid], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}
        raise AssertionError(query[:80])


def run(tenant: Tenant, *args: str):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.side_effect = tenant.execute
        return runner.invoke(app, ["-s", SESSION, "-f", "json", "mappings", *args])


def tenant(many_groups: bool = True) -> Tenant:
    big = [resource(i, "NetA") for i in range(5)] + [resource(i, "NetB") for i in range(5, 9)]
    return Tenant(
        users={"u1": ["g1", "g2", "g3", "g4", "g5"] if many_groups else ["g1"], "u2": ["g1"], "u3": ["g1", "g2"]},
        group_resources={"g1": big, "g2": [resource(20, "NetC")], "g3": [resource(21, "NetD")], "g4": [resource(22, "NetE")], "g5": [resource(23, "NetF")]},
    )


class TestUserNetwork:
    def test_counts_include_every_group_and_every_resource(self):
        result = run(tenant(), "user-network")
        assert result.exit_code == 0, result.output
        rows = {r["user.email"]: r for r in json.loads(result.output)}
        # u1: all five groups (3 are past the first page) -> 9 + 4 resources, 6 networks
        assert rows["u1@x.io"]["resources.count"] == 13 and rows["u1@x.io"]["networks.count"] == 6
        # u2: only g1, whose 9 resources span 5 pages of 2
        assert rows["u2@x.io"]["resources.count"] == 9 and rows["u2@x.io"]["networks.count"] == 2
        assert rows["u3@x.io"]["resources.count"] == 10 and rows["u3@x.io"]["networks.count"] == 3

    def test_a_group_shared_by_many_users_has_its_resources_read_once(self):
        t = tenant()
        run(t, "user-network")
        g1_resource_requests = [v for q, v in t.calls if "group(id: $id)" in q and v["id"] == "g1"]
        assert [v["cursor"] for v in g1_resource_requests] == ["c2", "c4", "c6", "c8"]  # one read, not one per user

    def test_a_users_groups_are_followed_with_the_user_query(self):
        t = tenant()
        run(t, "user-network")
        user_requests = [v for q, v in t.calls if "user(id: $id)" in q]
        assert [(v["id"], v["cursor"]) for v in user_requests] == [("u1", "c2"), ("u1", "c4")]

    def test_nothing_truncated_means_no_follow_up_requests(self):
        t = Tenant({"u1": ["g1"]}, {"g1": [resource(1, "NetA")]})
        result = run(t, "user-network")
        assert result.exit_code == 0 and len(t.calls) == 1
        assert json.loads(result.output)[0]["resources.count"] == 1

    def test_an_api_error_while_following_exits_nonzero(self):
        t = tenant()
        t.fail_on = "group(id: $id)"
        result = run(t, "user-network")
        assert result.exit_code == 1 and "API error: boom" in result.output


class TestUserResource:
    def test_resources_from_every_group_are_collected_not_just_the_first_page_of_groups(self):
        t = tenant()
        result = run(t, "user-resource", "-e", "u1@x.io")
        assert result.exit_code == 0, result.output
        asked = {v["groupID"] for q, v in t.calls if "query getGroup" in q}
        assert asked == {"g1", "g2", "g3", "g4", "g5"}

    def test_the_users_groups_are_completed_with_the_user_query(self):
        t = tenant()
        run(t, "user-resource", "-e", "u1@x.io")
        assert [(v["id"], v["cursor"]) for q, v in t.calls if "user(id: $id)" in q] == [("u1", "c2"), ("u1", "c4")]

    def test_a_user_in_few_groups_costs_no_extra_request(self):
        t = tenant(many_groups=False)
        run(t, "user-resource", "-e", "u1@x.io")
        assert not any("user(id: $id)" in q for q, _ in t.calls)
