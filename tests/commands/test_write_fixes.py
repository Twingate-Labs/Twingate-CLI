"""Five bugs found by running every write command against a real tenant.

1. `key create` in CSV/table form printed its values one column to the left of their headers.
2. A write the API refused (`ok: false`) exited 0, so a script could not tell it from a write that was made.
3. `key rotate` printed progress text on stdout, so its JSON/CSV output could not be parsed.
4. `resource create` required a Security Policy, so a bypass Resource (which may not have one) could not be created.
5. `policy update` had no way to remove every group from a policy.
"""

from __future__ import annotations

import csv
import io
import json
import re
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app  # must come before tgcli.commands._common (circular import otherwise)
from tgcli.commands._common import write_refused
from tgcli.output.transformers import generic
from tgcli.output.transformers import keys as key_transformers
from tgcli.queries import resources as resource_queries

runner = CliRunner()
SESSION = "TestSess"
NET = "UmVtb3RlTmV0d29yazox"
POLICY = "U2VjdXJpdHlQb2xpY3k6MQ=="
GROUP = "R3JvdXA6MQ=="


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def mutation_name(query: str) -> str:
    return re.search(r"\)\s*\{\s*(\w+)", query).group(1)


class FakeApi:
    """Answers any single mutation with ``ok`` true or false, and records every request."""

    def __init__(self, ok: bool = True, error: str = "nope"):
        self.ok, self.error = ok, error
        self.requests: list[tuple[str, dict]] = []

    def execute(self, query, variables=None):
        self.requests.append((query, variables or {}))
        entity = {"id": "obj-1", "name": "n", "routingMode": "THROUGH_TWINGATE", "isVisible": True, "securityPolicy": None}
        payload = {"ok": self.ok, "error": None if self.ok else self.error, "entity": entity if self.ok else None}
        return {"data": {mutation_name(query): payload}}


def invoke(api, *args, fmt="csv"):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.side_effect = api.execute
        return runner.invoke(app, ["-s", SESSION, "-f", fmt, *args])


# ---------------------------------------------------------------------------------------------------------------- 1

CREATE_KEY_RESPONSE = {"data": {"serviceAccountKeyCreate": {
    "ok": True, "error": None, "token": "tgp_secret",
    "entity": {"id": "key-new", "name": "ci key", "expiresAt": "2027-01-01T00:00:00Z", "createdAt": "2026-01-01T00:00:00Z", "status": "ACTIVE"},
}}}


class TestKeyCreateAlignment:
    def test_every_value_is_under_its_own_header(self):
        row = key_transformers.get_create_as_csv(CREATE_KEY_RESPONSE).iloc[0].to_dict()
        assert row == {"ok": True, "error": None, "token": "tgp_secret", "id": "key-new", "name": "ci key",
                       "expiresAt": "2027-01-01T00:00:00Z", "status": "ACTIVE"}

    def test_the_csv_the_command_prints_has_the_id_in_the_id_column(self):
        api = type("A", (), {"execute": staticmethod(lambda q, v=None: CREATE_KEY_RESPONSE)})
        result = invoke(api, "key", "create", "-n", "ci key", "-i", "sa-1", "-e", "30")
        (row,) = list(csv.DictReader(io.StringIO(result.stdout)))
        assert (row["id"], row["name"], row["token"], row["status"]) == ("key-new", "ci key", "tgp_secret", "ACTIVE")

    def test_the_table_form_is_aligned_too(self):
        api = type("A", (), {"execute": staticmethod(lambda q, v=None: CREATE_KEY_RESPONSE)})
        result = invoke(api, "key", "create", "-n", "ci key", "-i", "sa-1", "-e", "30", fmt="df")
        header, values = result.stdout.splitlines()[:2]
        assert header.split() == ["ok", "error", "token", "id", "name", "expiresAt", "status"]
        cells = values.split()  # the row, in header order: token comes before id, id before the expiry, the status is last
        assert cells.index("tgp_secret") < cells.index("key-new") < cells.index("2027-01-01T00:00:00Z") < cells.index("ACTIVE") == len(cells) - 1

    @pytest.mark.parametrize("columns,expected", [
        (["ok", "error", "token", "id"], [True, "", "t0k", "e1"]),
        (["ok", "error", "id", "token"], [True, "", "e1", "t0k"]),
        (["ok", "error", "id", "token", "name"], [True, "", "e1", "t0k", "e2"]),
        (["ok", "error", "token"], [True, "", "t0k"]),
    ])
    def test_a_token_column_keeps_its_own_position_wherever_the_header_puts_it(self, columns, expected):
        data = {"data": {"m": {"ok": True, "error": "", "token": "t0k", "entity": {"id": "e1", "name": "e2"}}}}
        assert generic.get_update_as_csv_no_nesting(data, "m", columns).iloc[0].tolist() == expected

    def test_a_refused_create_has_no_values_and_no_token(self):
        data = {"data": {"m": {"ok": False, "error": "no", "token": None, "entity": None}}}
        row = generic.get_update_as_csv_no_nesting(data, "m", ["ok", "error", "token", "id"]).iloc[0].tolist()
        assert row[:2] == [False, "no"] and pd.isna(row[2]) and pd.isna(row[3])

    def test_json_output_is_untouched(self):
        api = type("A", (), {"execute": staticmethod(lambda q, v=None: CREATE_KEY_RESPONSE)})
        assert json.loads(invoke(api, "key", "create", "-n", "x", "-i", "sa", "-e", "1", fmt="json").stdout) == CREATE_KEY_RESPONSE


# ---------------------------------------------------------------------------------------------------------------- 2

REFUSED_COMMANDS = [
    ["network", "updateName", "-i", "n1", "-n", "x"],
    ["network", "delete", "-i", "n1", "--yes"],
    ["resource", "delete", "-i", "r1", "--yes"],
    ["resource", "disable", "-i", "r1"],
    ["resource", "alias", "-i", "r1", "-a", "a.example"],
    ["resource", "create", "-a", "a.example", "-n", "x", "-r", NET, "-p", POLICY],
    ["resource", "access", "add", "-i", "r1", "-g", GROUP],
    ["group", "delete", "-i", "g1", "--yes"],
    ["group", "addUsers", "-g", "g1", "-u", "u1"],
    ["key", "delete", "-i", "k1", "--yes"],
    ["key", "revoke", "-i", "k1", "--yes"],
    ["user", "role", "-i", "u1", "-r", "MEMBER"],
    ["user", "state", "-i", "u1", "-s", "ACTIVE"],
    ["connector", "rename", "-i", "c1", "-n", "x"],
    ["device", "block", "-i", "d1"],
    ["device", "updateTrust", "-i", "d1", "-t", "True"],
    ["account", "rename", "-i", "a1", "-n", "x"],
    ["policy", "update", "-i", "p1", "-a", "g1"],
    ["dns-profile", "delete", "-i", "p1", "--yes"],
]


class TestRefusedWritesExitNonZero:
    @pytest.mark.parametrize("argv", REFUSED_COMMANDS, ids=lambda a: " ".join(a[:3]))
    def test_a_refused_write_exits_1_with_the_reason_on_stderr_and_the_row_still_on_stdout(self, argv):
        api = FakeApi(ok=False, error="API says no")
        result = invoke(api, *argv)
        assert result.exit_code == 1, result.output
        assert "Error:" in result.stderr and "API says no" in result.stderr  # (device updateTrust names the device first)
        assert "False" in result.stdout and "API says no" in result.stdout  # the row is still printed

    @pytest.mark.parametrize("argv", REFUSED_COMMANDS, ids=lambda a: " ".join(a[:3]))
    def test_the_same_write_accepted_exits_0_with_nothing_on_stderr(self, argv):
        result = invoke(FakeApi(ok=True), *argv)
        assert result.exit_code == 0, result.output
        assert result.stderr == "" or "Note:" in result.stderr  # only create's advice about access may appear

    def test_json_output_of_a_refused_write_is_still_complete_json(self):
        result = invoke(FakeApi(ok=False, error="nope"), "network", "delete", "-i", "n1", "--yes", fmt="json")
        assert result.exit_code == 1
        assert json.loads(result.stdout)["data"]["remoteNetworkDelete"]["ok"] is False

    def test_a_refusal_without_a_reason_still_says_something(self):
        api = FakeApi(ok=False)
        api.error = None
        result = invoke(api, "network", "delete", "-i", "n1", "--yes")
        assert result.exit_code == 1 and "Error: the API refused the change" in result.stderr

    def test_a_list_of_devices_attempts_every_one_then_exits_1_naming_each_refusal(self):
        answers = {"d1": True, "d2": False, "d3": True, "d4": False}
        class Api(FakeApi):
            def execute(self, query, variables=None):
                self.requests.append((query, variables or {}))
                ok = answers[variables["deviceID"]]
                return {"data": {"deviceUpdate": {"ok": ok, "error": None if ok else f"cannot change {variables['deviceID']}",
                                                  "entity": {"id": variables["deviceID"], "name": "n", "isTrusted": True, "activeState": "ACTIVE"} if ok else None}}}
        api = Api()
        result = invoke(api, "device", "updateTrust", "-l", "d1,d2,d3,d4", "-t", "True")
        assert result.exit_code == 1
        assert [v["deviceID"] for _, v in api.requests] == ["d1", "d2", "d3", "d4"]  # none skipped after a refusal
        assert "d2: cannot change d2" in result.stderr and "d4: cannot change d4" in result.stderr and "d1" not in result.stderr

    def test_a_list_of_devices_that_all_succeed_exits_0(self):
        result = invoke(FakeApi(ok=True), "device", "updateTrust", "-l", "d1,d2", "-t", "False")
        assert result.exit_code == 0

    def test_reads_are_not_affected(self):
        api = type("A", (), {"execute": staticmethod(lambda q, v=None: {"data": {"remoteNetworks": {"ok": False, "edges": []}}})})
        class Paged:
            def paginate(self, *a, **k): return [[]]
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[]]
            assert runner.invoke(app, ["-s", SESSION, "-f", "csv", "network", "list"]).exit_code == 0


class TestWriteRefused:
    @pytest.mark.parametrize("result", [None, {}, {"data": None}, {"data": {}}, {"data": {"x": None}}, {"data": {"x": {"ok": True}}},
                                         {"data": {"x": {"edges": []}}}, {"data": {"x": "ok"}}, {"data": {"x": {"ok": None}}}])
    def test_nothing_refused(self, result):
        assert write_refused(result) is None

    def test_the_apis_reason_is_returned(self):
        assert write_refused({"data": {"x": {"ok": False, "error": "bad id"}}}) == "bad id"

    def test_a_missing_reason_gets_a_default(self):
        assert write_refused({"data": {"x": {"ok": False, "error": None}}}) == "the API refused the change"

    def test_the_first_refusal_among_several_fields(self):
        assert write_refused({"data": {"a": {"ok": True}, "b": {"ok": False, "error": "no"}}}) == "no"


# ---------------------------------------------------------------------------------------------------------------- 3

def rotate_responses(old_name="old"):
    show = {"data": {"serviceAccountKey": {"id": "key-old", "name": old_name, "serviceAccount": {"id": "sa-1", "name": "CI Bot"}}}}
    revoke = {"data": {"serviceAccountKeyRevoke": {"ok": True, "error": None}}}
    return [show, CREATE_KEY_RESPONSE, revoke]


class TestKeyRotateOutput:
    def run_rotate(self, fmt):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = rotate_responses()
            return runner.invoke(app, ["-s", SESSION, "-f", fmt, "key", "rotate", "-i", "key-old"])

    def test_stdout_is_the_json_result_alone(self):
        result = self.run_rotate("json")
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["newKeyId"] == "key-new" and data["oldKeyRevoked"] is True and data["newKeyToken"] == "tgp_secret"

    def test_stdout_is_the_csv_result_alone(self):
        rows = list(csv.DictReader(io.StringIO(self.run_rotate("csv").stdout)))
        assert len(rows) == 1 and rows[0]["newKeyId"] == "key-new" and rows[0]["oldKeyId"] == "key-old"

    def test_progress_is_on_stderr(self):
        result = self.run_rotate("json")
        for text in ("Creating new Key", "Created new Key: key-new", "Revoking old Key 'key-old'"):
            assert text in result.stderr and text not in result.stdout

    def test_the_secret_is_never_in_the_progress_text(self):
        assert "tgp_secret" not in self.run_rotate("json").stderr


# ---------------------------------------------------------------------------------------------------------------- 4

CREATE = ["resource", "create", "-a", "app.example.com", "-n", "App", "-r", NET]


class TestResourceCreatePolicy:
    def test_the_policy_is_optional_and_nothing_is_sent_for_it(self):
        api = FakeApi()
        result = invoke(api, *CREATE)
        assert result.exit_code == 0, result.output
        (query, variables), = api.requests
        assert "securityPolicyId" not in variables and variables["remoteNetworkId"] == NET

    def test_a_policy_is_still_sent_when_given(self):
        api = FakeApi()
        invoke(api, *CREATE, "-p", POLICY)
        assert api.requests[0][1]["securityPolicyId"] == POLICY

    def test_a_bypass_resource_can_be_created_without_one(self):
        api = FakeApi()
        result = invoke(api, *CREATE, "-m", "BYPASS_TWINGATE")
        assert result.exit_code == 0, result.output
        (query, variables), = api.requests
        assert variables["routingMode"] == "BYPASS_TWINGATE" and "securityPolicyId" not in variables

    @pytest.mark.parametrize("mode", ["BYPASS_TWINGATE", "bypass_twingate"])
    def test_a_bypass_resource_with_a_policy_is_refused_before_any_request(self, mode):
        api = FakeApi()
        result = invoke(api, *CREATE, "-p", POLICY, "-m", mode)
        assert result.exit_code == 1 and api.requests == []
        assert "bypass Resource" in result.stderr and "cannot have a Security Policy" in result.stderr and "Leave out -p" in result.stderr

    def test_a_policy_with_through_twingate_is_fine(self):
        assert invoke(FakeApi(), *CREATE, "-p", POLICY, "-m", "THROUGH_TWINGATE").exit_code == 0

    def test_the_mutation_declares_the_policy_nullable(self):
        assert "$securityPolicyId: ID\n" in resource_queries.CREATE_RESOURCE and "$securityPolicyId: ID!" not in resource_queries.CREATE_RESOURCE

    def test_without_a_policy_no_policy_lookup_is_made(self):
        api = FakeApi()
        invoke(api, *CREATE, "-g", GROUP)
        assert len(api.requests) == 1  # ids are used as given, and there is no policy to look up

    def test_the_hint_after_create_still_appears_without_a_policy_or_group(self):
        assert "no group has access" in invoke(FakeApi(), *CREATE).stderr

    def test_the_routing_command_explains_the_bypass_rule(self):
        help_text = " ".join(runner.invoke(app, ["resource", "routing", "--help"]).stdout.split())
        assert "to have a Security Policy" in help_text and "-m BYPASS_TWINGATE" in help_text


# ---------------------------------------------------------------------------------------------------------------- 5

class PolicyApi:
    """A policy holding ``groups``; serves its group IDs two per page, and records the write."""

    def __init__(self, groups, found=True):
        self.groups, self.found = list(groups), found
        self.reads, self.writes = [], []

    def execute(self, query, variables=None):
        variables = variables or {}
        if query.lstrip().startswith("mutation"):
            self.writes.append(variables)
            return {"data": {"securityPolicyUpdate": {"ok": True, "error": None, "entity": {
                "id": "pol-1", "name": "P", "policyType": "RESOURCE", "groups": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        self.reads.append(variables)
        if not self.found:
            return {"data": {"securityPolicy": None}}
        start = 0 if variables.get("cursor") is None else int(variables["cursor"][1:])
        more = start + 2 < len(self.groups)
        return {"data": {"securityPolicy": {"groups": {
            "pageInfo": {"hasNextPage": more, "endCursor": f"c{start + 2}" if more else None},
            "edges": [{"node": {"id": g}} for g in self.groups[start:start + 2]]}}}}


class TestPolicyClearGroups:
    def update(self, *args, api=None):
        api = api or PolicyApi(["g1", "g2", "g3", "g4", "g5"])
        return invoke(api, "policy", "update", "-i", "pol-1", *args), api

    def test_clear_groups_reads_every_group_then_removes_them_all_in_one_write(self):
        result, api = self.update("--clear-groups")
        assert result.exit_code == 0, result.output
        assert len(api.reads) == 3  # five groups, two per page
        assert api.writes == [{"id": "pol-1", "removedGroupIds": ["g1", "g2", "g3", "g4", "g5"]}]

    def test_it_never_sends_the_empty_list_the_api_ignores(self):
        _, api = self.update("--clear-groups")
        assert all("groupIds" not in w for w in api.writes)

    def test_a_policy_with_no_groups_makes_no_write_and_says_so(self):
        result, api = self.update("--clear-groups", api=PolicyApi([]))
        assert result.exit_code == 0 and api.writes == [] and "no groups" in result.stderr

    def test_a_policy_that_does_not_exist_is_an_error_and_writes_nothing(self):
        result, api = self.update("--clear-groups", api=PolicyApi([], found=False))
        assert result.exit_code == 1 and api.writes == [] and "no policy with ID 'pol-1'" in result.stderr

    @pytest.mark.parametrize("error,message", [
        (TwingateAPIError("HTTP 500"), "could not read the policy's groups"),
        (TwingateAuthError("bad token"), "Authentication error: bad token"),
    ])
    def test_a_failure_while_reading_the_groups_stops_before_any_write(self, error, message):
        api = PolicyApi(["g1"])
        def failing(query, variables=None):
            raise error
        api.execute = failing
        result, _ = self.update("--clear-groups", api=api)
        assert result.exit_code == 1 and message in result.stderr and api.writes == []

    @pytest.mark.parametrize("extra", [["-a", "g1"], ["-r", "g1"], ["--set-groups", "g1"], ["--set-groups", ""]])
    def test_clear_groups_cannot_be_combined_with_anything_else(self, extra):
        result, api = self.update("--clear-groups", *extra)
        assert result.exit_code == 1 and api.reads == [] and api.writes == [] and "--clear-groups removes every group" in result.stderr

    @pytest.mark.parametrize("value", ["", " ", " , ", ",,"])
    def test_an_empty_set_groups_is_refused_and_points_to_clear_groups(self, value):
        result, api = self.update("--set-groups", value)
        assert result.exit_code == 1 and api.reads == [] and api.writes == []
        assert "--set-groups needs at least one Group ID" in result.stderr and "--clear-groups" in result.stderr

    def test_set_groups_with_ids_is_unchanged(self):
        result, api = self.update("--set-groups", "g1,g2")
        assert result.exit_code == 0 and api.writes == [{"id": "pol-1", "groupIds": ["g1", "g2"]}] and api.reads == []

    def test_no_option_at_all_names_the_new_flag_in_the_error(self):
        result, api = self.update()
        assert result.exit_code == 1 and api.writes == [] and "--clear-groups" in result.stderr

    def test_add_and_remove_are_unchanged_and_read_nothing(self):
        result, api = self.update("-a", "g1", "-r", "g2")
        assert api.writes == [{"id": "pol-1", "addedGroupIds": ["g1"], "removedGroupIds": ["g2"]}] and api.reads == []
