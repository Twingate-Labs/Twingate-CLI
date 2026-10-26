"""A write command echoes the object it changed. Lists in that echo are cut at 50 like any other, so they are completed
too, and reading the rest back must never repeat the write or make a successful write look like it failed."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

from ..nested_fakes import LONG, PAGE, Backend, edges, first_page

runner = CliRunner()
SESSION = "TestSess"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


@dataclass
class Case:
    id: str
    argv: list[str]
    mutation: str  # the write's field under data
    parent: str  # the object type's single-object query field (used by the follow-ups)
    fields: dict[str, list[dict]]  # nested field -> its full list of edges in the echo
    scalars: dict[str, Any]

    def entity(self, truncated: bool = True) -> dict:
        return {"id": "p1", "name": "P", **self.scalars, **{f: first_page(e) for f, e in self.fields.items()}}

    def backend(self, response: dict | None = None) -> Backend:
        sent = []
        full = {("p1", f): e for f, e in self.fields.items()}

        def main():
            sent.append(1)
            return response if response is not None else {"data": {self.mutation: {"ok": True, "error": None, "entity": self.entity()}}}

        backend = Backend(main, full)
        backend.writes = sent
        return backend

    def echoed(self, output: str) -> dict:
        return json.loads(output[output.index("{"):])["data"][self.mutation]


def refs(prefix: str, n: int) -> list[dict]:
    return edges(prefix, n)


CASES = [
    Case("group create", ["group", "create", "-g", "G"], "groupCreate", "group", {"users": refs("u", LONG), "resources": refs("r", 4)}, {"type": "MANUAL"}),
    Case("group addUsers", ["group", "addUsers", "-g", "p1", "-u", "u9"], "groupUpdate", "group", {"users": refs("u", LONG)}, {}),
    Case("group removeUsers", ["group", "removeUsers", "-g", "p1", "-u", "u9"], "groupUpdate", "group", {"users": refs("u", LONG)}, {}),
    Case("group addResources", ["group", "addResources", "-g", "p1", "-r", "r9"], "groupUpdate", "group", {"resources": refs("r", LONG)}, {}),
    Case("group removeResources", ["group", "removeResources", "-g", "p1", "-r", "r9"], "groupUpdate", "group", {"resources": refs("r", LONG)}, {}),
    Case("group assignPolicy", ["group", "assignPolicy", "-g", "p1", "-p", "pol1"], "groupUpdate", "group", {"users": refs("u", LONG)}, {"securityPolicy": {"id": "pol1"}}),
    Case("account addResources", ["account", "addResources", "-i", "p1", "-r", "r9"], "serviceAccountUpdate", "serviceAccount", {"resources": refs("r", LONG)}, {}),
    Case("account removeResources", ["account", "removeResources", "-i", "p1", "-r", "r9"], "serviceAccountUpdate", "serviceAccount", {"resources": refs("r", LONG)}, {}),
    Case("policy update", ["policy", "update", "-i", "p1", "--add-groups", "g9"], "securityPolicyUpdate", "securityPolicy", {"groups": refs("g", LONG)}, {"policyType": "RESOURCE"}),
    Case("user role", ["user", "role", "-i", "p1", "-r", "MEMBER"], "userRoleUpdate", "user", {"groups": refs("g", LONG)}, {"role": "MEMBER"}),
]
ids = [c.id for c in CASES]


def run(case: Case, backend: Backend, *extra: str):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.paginate.side_effect = backend.paginate
        inst.execute.side_effect = backend.execute
        return runner.invoke(app, ["-s", SESSION, *extra, *case.argv])


@pytest.mark.parametrize("case", CASES, ids=ids)
class TestEveryWriteCommand:
    def test_every_item_of_the_echoed_lists_is_shown_in_order(self, case):
        result = run(case, case.backend())
        assert result.exit_code == 0, result.output
        entity = case.echoed(result.output)["entity"]
        for field, full in case.fields.items():
            assert entity[field]["edges"] == full, field

    def test_the_write_is_sent_exactly_once(self, case):
        backend = case.backend()
        run(case, backend)
        assert len(backend.writes) == 1

    def test_no_count_or_cursor_leaks_into_the_output(self, case):
        entity = case.echoed(run(case, case.backend()).output)["entity"]
        for field in case.fields:
            assert set(entity[field]) == {"edges"}, field

    def test_the_rest_of_the_response_is_untouched(self, case):
        echoed = case.echoed(run(case, case.backend()).output)
        assert (echoed["ok"], echoed["error"]) == (True, None)
        expected = {k: v for k, v in case.entity().items() if k not in case.fields}
        assert {k: v for k, v in echoed["entity"].items() if k not in case.fields} == expected

    def test_follow_ups_target_the_changed_object_and_stop_when_done(self, case):
        backend = case.backend()
        run(case, backend)
        expected = sum(math.ceil((len(e) - PAGE) / PAGE) for e in case.fields.values() if len(e) > PAGE)
        assert len(backend.followups) == expected
        assert {(p, i) for p, i, _, _ in backend.followups} == {(case.parent, "p1")}
        assert {f for _, _, f, _ in backend.followups} == set(case.fields)

    def test_a_list_that_fits_in_one_page_costs_no_extra_request(self, case):
        short = Case(case.id, case.argv, case.mutation, case.parent, {f: e[:PAGE] for f, e in case.fields.items()}, case.scalars)
        backend = short.backend()
        result = run(short, backend)
        assert result.exit_code == 0 and backend.followups == [] and len(backend.writes) == 1
        assert all(set(short.echoed(result.output)["entity"][f]) == {"edges"} for f in short.fields)

    def test_a_write_that_reports_failure_has_nothing_to_complete(self, case):
        backend = case.backend({"data": {case.mutation: {"ok": False, "error": "nope", "entity": None}}})
        result = run(case, backend)
        # The refusal is still printed in full on stdout, nothing is fetched to complete it, and the exit code says it failed.
        assert result.exit_code == 1 and backend.followups == []
        assert case.echoed(result.stdout) == {"ok": False, "error": "nope", "entity": None}
        assert "Error: nope" in result.stderr

    @pytest.mark.parametrize("error", [TwingateAPIError("boom"), TwingateAuthError("Bad token")], ids=["api error", "auth error"])
    def test_failing_to_read_back_the_rest_warns_but_the_write_still_counts_as_done(self, case, error):
        backend = case.backend()
        real = backend.execute

        def failing(query, variables):
            if query.startswith("query($id: ID!"):
                raise error
            return real(query, variables)

        backend.execute = failing
        result = run(case, backend)
        assert result.exit_code == 0, result.output
        assert "the change was made" in result.output and str(error) in result.output
        entity = case.echoed(result.output)["entity"]
        for field in case.fields:
            assert len(entity[field]["edges"]) == PAGE and set(entity[field]) == {"edges"}  # what the API returned, cleaned
        assert len(backend.writes) == 1

    def test_a_failing_write_still_exits_nonzero_as_before(self, case):
        backend = case.backend()
        real = backend.execute

        def failing(query, variables):
            if not query.startswith("query($id: ID!"):
                raise TwingateAPIError("write failed")
            return real(query, variables)

        backend.execute = failing
        result = run(case, backend)
        assert result.exit_code == 1 and "API error: write failed" in result.output

    def test_csv_and_df_formats_still_work(self, case):
        for fmt in ("csv", "df"):
            result = run(case, case.backend(), "-f", fmt)
            assert result.exit_code == 0, (fmt, result.output)
