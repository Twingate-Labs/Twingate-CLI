"""Who has access to a resource, and when each grant expires, can be seen in `resource show` and `resource list --detail`.

Issue #30: the CLI could set an expiry on a group's access (`access add -e`) but nowhere showed it.
"""

from __future__ import annotations

import ast
import csv
import io
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.session import SessionManager
from tgcli.main import app
from tgcli.queries import resources as q

runner = CliRunner()
SESSION = "TestSess"
SOON = "2999-01-01T00:00:00+00:00"
LATER = "2999-06-30T12:30:00+00:00"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def grant(kind_id, name, expires=None):
    return {"node": {"id": kind_id, "name": name}, "securityPolicy": None, "expiresAt": expires}


def resource(access, rid="res-1", typename="NetworkResource"):
    return {
        "__typename": typename, "id": rid, "name": "App", "isActive": True, "remoteNetwork": {"id": "net-1", "name": "N"},
        "address": {"type": "DNS", "value": "app.example.com"}, "isVisible": True, "isBrowserShortcutEnabled": False,
        "routingMode": "THROUGH_TWINGATE", "alias": None, "tags": [], "securityPolicy": {"id": "sp-1"},
        "protocols": {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}},
        "accessPolicy": {"mode": "MANUAL", "durationSeconds": None}, "approvalMode": "MANUAL", "approverGroups": {"edges": []},
        "access": {"totalCount": len(access), "pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": access},
    }


MIXED = [grant("g-eng", "Engineering", SOON), grant("g-ops", "Ops"), grant("sa-ci", "ci-bot"), grant("g-con", "Contractors", LATER)]


def show(res, fmt="csv"):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.return_value = {"data": {"resource": res}}
        return runner.invoke(app, ["-s", SESSION, "-f", fmt, "resource", "show", "-i", "res-1"])


def list_detail(nodes):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.paginate.return_value = [[{"node": n} for n in nodes]]
        return runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "list", "--detail"])


def one_row(result):
    (row,) = list(csv.DictReader(io.StringIO(result.stdout)))
    return row


class TestShow:
    def test_who_has_access_and_when_it_expires_are_three_lists_in_the_same_order(self):
        row = one_row(show(resource(MIXED)))
        edges = ast.literal_eval(row["access.edges"])  # the same grants `resource list` prints, each with its own expiry
        assert [(e["node"]["id"], e["expiresAt"]) for e in edges] == [("g-eng", SOON), ("g-ops", None), ("sa-ci", None), ("g-con", LATER)]
        assert row["accessNames"] == "['Engineering', 'Ops', 'ci-bot', 'Contractors']"
        assert row["accessExpiresAt"] == f"['{SOON}', None, None, '{LATER}']"

    def test_a_resource_nobody_can_reach_shows_empty_lists(self):
        row = one_row(show(resource([])))
        assert (row["access.edges"], row["accessNames"], row["accessExpiresAt"]) == ("[]", "[]", "[]")

    def test_a_grant_that_never_expires_is_none_not_a_date(self):
        assert one_row(show(resource([grant("g1", "A")])))["accessExpiresAt"] == "[None]"

    def test_the_new_columns_come_after_all_the_old_ones(self):
        header = next(csv.reader(io.StringIO(show(resource(MIXED)).stdout)))
        assert header[-4:] == ["approverGroupNames", "access.edges", "accessNames", "accessExpiresAt"]

    def test_json_carries_the_expiry_on_each_grant(self):
        data = json.loads(show(resource(MIXED), fmt="json").stdout)["data"]["resource"]
        assert [e["expiresAt"] for e in data["access"]["edges"]] == [SOON, None, None, LATER]

    def test_a_missing_resource_is_still_a_blank_row(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {"data": {"resource": None}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "show", "-i", "nope"])
        row = one_row(result)
        assert result.exit_code == 0 and (row["access.edges"], row["accessNames"], row["accessExpiresAt"]) == ("", "", "")


class TestListDetail:
    def test_each_row_has_its_own_names_and_expiries(self):
        a = resource([grant("g1", "A", SOON), grant("g2", "B")], rid="r-a")
        b = resource([], rid="r-b")
        c = resource([grant("g3", "C", LATER)], rid="r-c")
        rows = list(csv.DictReader(io.StringIO(list_detail([a, b, c]).stdout)))
        assert [(r["id"], r["accessNames"], r["accessExpiresAt"]) for r in rows] == [
            ("r-a", "['A', 'B']", f"['{SOON}', None]"), ("r-b", "[]", "[]"), ("r-c", "['C']", f"['{LATER}']")]
        assert [e["node"]["id"] for e in ast.literal_eval(rows[0]["access.edges"])] == ["g1", "g2"]  # the original column keeps its shape

    def test_a_null_node_in_the_list_gives_a_blank_row_and_does_not_shift_the_others(self):
        rows = list(csv.DictReader(io.StringIO(list_detail([None, resource([grant("g1", "A", SOON)], rid="ok")]).stdout)))
        assert rows[0]["id"] == "" and rows[0]["accessNames"] == "" and rows[0]["accessExpiresAt"] == ""
        assert rows[1]["id"] == "ok" and rows[1]["accessExpiresAt"] == f"['{SOON}']"


class TestQueries:
    @pytest.mark.parametrize("name", ["LIST_RESOURCES", "LIST_RESOURCES_DETAIL", "SHOW_RESOURCE"])
    def test_every_resource_query_asks_for_the_expiry_of_each_grant(self, name):
        text = " ".join(getattr(q, name).split())
        assert "access" in text and "expiresAt }" in text.split("access", 1)[1]

    def test_show_follows_the_access_list_past_the_first_page(self):
        assert set(q.RESOURCE_SHOW_CONTINUATIONS) == {"access", "approverGroups"}
        assert "expiresAt" in q.RESOURCE_SHOW_CONTINUATIONS["access"]

    def test_the_default_list_keeps_its_original_columns_and_now_shows_each_grants_expiry_inside_access_edges(self):
        node = resource([grant("g1", "A", SOON)])
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[{"node": node}]]
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "list"])
        header = next(csv.reader(io.StringIO(result.stdout)))
        assert "accessExpiresAt" not in header and "accessNames" not in header and header[-1] == "type"
        assert ast.literal_eval(one_row(result)["access.edges"])[0]["expiresAt"] == SOON


class TestExpiryHelp:
    @pytest.mark.parametrize("sub", [["access", "add"], ["access", "set"]])
    def test_the_expiry_option_states_the_apis_rules(self, sub):
        text = " ".join(runner.invoke(app, ["resource", *sub, "--help"]).stdout.split())
        assert "less than a year away" in text and "service account" in text
