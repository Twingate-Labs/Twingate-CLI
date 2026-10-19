"""Every read command that selects a nested list must show all of it, not just the API's first page of 50."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
PAGE = 2
LONG = 5  # more than one page of PAGE


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


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


@dataclass
class Case:
    id: str
    argv: list[str]
    kind: str  # "show": prints {"data": {parent: node}}; "list": prints [[{"node": ...}]]
    parent: str  # single-object query field the follow-ups use
    fields: dict[str, list[dict]]  # nested field -> its full list of edges
    scalars: dict[str, Any]

    def node(self, truncated: bool = True) -> dict:
        return {"id": "p1", "name": "P", **self.scalars,
                **{f: first_page(e) if truncated else {"edges": e} for f, e in self.fields.items()}}

    def backend(self) -> Backend:
        node = self.node()
        full = {("p1", f): e for f, e in self.fields.items()}
        main = (lambda: {"data": {self.parent: node}}) if self.kind == "show" else (lambda: [[{"node": node}]])
        return Backend(main, full)

    def result_node(self, output: str) -> dict:
        data = json.loads(output[output.index("[" if self.kind == "list" else "{"):])
        return data["data"][self.parent] if self.kind == "show" else data[0][0]["node"]


R = lambda p, n: edges(p, n)
CASES = [
    Case("group show", ["group", "show", "-i", "p1"], "show", "group", {"users": R("u", LONG), "resources": R("r", 3)}, {}),
    Case("network show", ["network", "show", "-i", "p1"], "show", "remoteNetwork", {"connectors": R("c", LONG), "resources": R("r", 4)}, {}),
    Case("user list", ["user", "list"], "list", "user", {"groups": R("g", LONG)}, {"email": "a@b.io"}),
    Case("user show", ["user", "show", "-i", "p1"], "show", "user", {"groups": R("g", LONG)}, {"email": "a@b.io"}),
    Case("policy show", ["policy", "show", "-i", "p1"], "show", "securityPolicy", {"groups": R("g", LONG)}, {"policyType": "RESOURCE"}),
    Case("account show", ["account", "show", "-i", "p1"], "show", "serviceAccount", {"resources": R("r", LONG), "keys": R("k", 3)}, {}),
    Case("account listKeys", ["account", "listKeys", "-i", "p1"], "show", "serviceAccount", {"keys": R("k", LONG)}, {}),
    Case("dns-profile show", ["dns-profile", "show", "-i", "p1"], "show", "dnsFilteringProfile", {"groups": R("g", LONG)}, {}),
    Case("key list", ["key", "list"], "list", "serviceAccount", {"keys": R("k", LONG)}, {}),
    Case("key expiring", ["key", "expiring"], "list", "serviceAccount", {"keys": R("k", LONG)}, {}),
    Case("resource list", ["resource", "list"], "list", "resource", {"access": edges("a", LONG, securityPolicy={"id": "sp", "name": "S"})}, {}),
    Case("resource list --detail", ["resource", "list", "--detail"], "list", "resource",
         {"access": edges("a", LONG, securityPolicy={"id": "sp", "name": "S"}), "approverGroups": R("g", LONG)}, {}),
    Case("resource show", ["resource", "show", "-i", "p1"], "show", "resource", {"approverGroups": R("g", LONG)}, {"__typename": "SSHResource"}),
]
ids = [c.id for c in CASES]


def run(case: Case, backend: Backend, *extra: str):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.paginate.side_effect = backend.paginate
        inst.execute.side_effect = backend.execute
        return runner.invoke(app, ["-s", SESSION, *extra, *case.argv])


@pytest.mark.parametrize("case", CASES, ids=ids)
class TestEveryCommand:
    def test_every_nested_item_is_shown_in_order(self, case):
        result = run(case, case.backend())
        assert result.exit_code == 0, result.output
        node = case.result_node(result.output)
        for field, full in case.fields.items():
            assert [e["node"]["id"] for e in node[field]["edges"]] == [e["node"]["id"] for e in full], field

    def test_edges_keep_everything_they_carry(self, case):
        node = case.result_node(run(case, case.backend()).output)
        for field, full in case.fields.items():
            assert node[field]["edges"] == full, field

    def test_no_count_or_cursor_leaks_into_the_output(self, case):
        node = case.result_node(run(case, case.backend()).output)
        for field in case.fields:
            assert set(node[field]) == {"edges"}, field

    def test_other_fields_are_untouched(self, case):
        node = case.result_node(run(case, case.backend()).output)
        assert {k: v for k, v in node.items() if k not in case.fields} == {k: v for k, v in case.node().items() if k not in case.fields}

    def test_follow_ups_target_the_right_parent_and_field_and_stop_when_done(self, case):
        backend = case.backend()
        run(case, backend)
        expected = sum(math.ceil((len(e) - PAGE) / PAGE) for e in case.fields.values() if len(e) > PAGE)
        assert len(backend.followups) == expected
        assert {(p, i) for p, i, _, _ in backend.followups} == {(case.parent, "p1")}
        assert {f for _, _, f, _ in backend.followups} == {f for f, e in case.fields.items() if len(e) > PAGE}
        for field in case.fields:
            cursors = [c for _, _, f, c in backend.followups if f == field]
            assert cursors == [f"c{n}" for n in range(PAGE, len(case.fields[field]), PAGE)] or not cursors

    def test_a_list_that_fits_in_one_page_costs_no_extra_request(self, case):
        short = Case(case.id, case.argv, case.kind, case.parent, {f: e[:PAGE] for f, e in case.fields.items()}, case.scalars)
        backend = short.backend()
        result = run(short, backend)
        assert result.exit_code == 0 and backend.followups == []
        node = short.result_node(result.output)
        assert all(set(node[f]) == {"edges"} for f in short.fields)

    def test_an_api_error_in_a_follow_up_exits_nonzero(self, case):
        backend = case.backend()
        real = backend.execute

        def failing(query, variables):
            if query.startswith("query($id: ID!"):
                raise TwingateAPIError("boom")
            return real(query, variables)

        backend.execute = failing
        result = run(case, backend)
        assert result.exit_code == 1 and "API error: boom" in result.output

    def test_an_authentication_error_in_a_follow_up_exits_nonzero(self, case):
        backend = case.backend()
        real = backend.execute

        def failing(query, variables):
            if query.startswith("query($id: ID!"):
                raise TwingateAuthError("Bad token")
            return real(query, variables)

        backend.execute = failing
        result = run(case, backend)
        assert result.exit_code == 1 and "Authentication error: Bad token" in result.output

    def test_csv_and_df_formats_still_work(self, case):
        for fmt in ("csv", "df"):
            result = run(case, case.backend(), "-f", fmt)
            assert result.exit_code == 0, (fmt, result.output)


def test_a_missing_object_prints_as_before_and_makes_no_follow_up():
    case = CASES[0]
    backend = Backend(lambda: {"data": {"group": None}}, {})
    assert run(case, backend).exit_code == 0 and backend.followups == []
