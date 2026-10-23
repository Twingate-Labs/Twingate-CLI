"""resource create and the access commands accept IDs or exact names. What reaches the API write must always be IDs."""

from __future__ import annotations

import base64
import json
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"


def make_id(kind, number):
    return base64.b64encode(f"{kind}:{number}".encode()).decode()


G_ENG, G_OPS, G_SALES = make_id("Group", 1), make_id("Group", 2), make_id("Group", 3)
NET, NET_OFFICE = make_id("RemoteNetwork", 1), make_id("RemoteNetwork", 2)
POL_DEFAULT, POL_STRICT = make_id("SecurityPolicy", 1), make_id("SecurityPolicy", 2)
SA_CI = make_id("ServiceAccount", "11111111-1111-1111-1111-111111111111")
RES = make_id("Resource", 9)


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


class Api:
    """Answers name lookups from a small tenant and records every request, so tests can see what was written."""

    TENANT = {
        "groups": [{"id": G_ENG, "name": "Eng"}, {"id": G_OPS, "name": "Ops"}, {"id": G_SALES, "name": "Sales"},
                   {"id": make_id("Group", 4), "name": "Dup"}, {"id": make_id("Group", 5), "name": "Dup"},
                   {"id": make_id("Group", 6), "name": "Ops, EMEA"}],
        "remoteNetworks": [{"id": NET, "name": "Cloud Applications"}, {"id": NET_OFFICE, "name": "Office"}],
        "securityPolicies": [{"id": POL_DEFAULT, "name": "Default Policy"}, {"id": POL_STRICT, "name": "Strict"}],
        "serviceAccounts": [{"id": SA_CI, "name": "ci"}],
    }

    def __init__(self):
        self.requests: list[tuple[str, dict]] = []
        self.error: Exception | None = None

    @property
    def lookups(self):
        return [r for r in self.requests if "filter: {name: {in: $names}}" in r[0]]

    @property
    def writes(self):
        return [r for r in self.requests if r[0].lstrip().startswith("mutation")]

    def execute(self, query, variables=None):
        variables = variables or {}
        self.requests.append((query, variables))
        if self.error and "filter: {name:" in query:
            raise self.error
        if "filter: {name: {in: $names}}" in query:
            root = re.search(r"(\w+)\(after: \$cursor", query).group(1)
            hits = [o for o in self.TENANT[root] if o["name"] in variables["names"]]
            return {"data": {root: {"pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": [{"node": o} for o in hits]}}}
        key = re.search(r"(resourceCreate|resourceAccessAdd|resourceAccessSet|resourceAccessRemove)", query).group(1)
        return {"data": {key: {"ok": True, "error": None, "entity": {"id": RES, "name": "R"}}}}


def run(*args):
    api = Api()
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.side_effect = api.execute
        result = runner.invoke(app, ["-s", SESSION, "resource", *args])
    return result, api


CREATE = ["create", "-a", "app.example.com", "-n", "App"]


class TestCreate:
    def test_names_for_network_policy_and_groups_are_sent_as_ids(self):
        result, api = run(*CREATE, "-r", "Cloud Applications", "-p", "Default Policy", "-g", "Eng,Ops")
        assert result.exit_code == 0, result.output
        (query, variables), = api.writes
        assert (variables["remoteNetworkId"], variables["securityPolicyId"], variables["groupIds"]) == (NET, POL_DEFAULT, [G_ENG, G_OPS])

    def test_one_lookup_per_kind_and_all_of_them_before_the_write(self):
        _, api = run(*CREATE, "-r", "Office", "-p", "Strict", "-g", "Eng,Ops,Sales")
        assert len(api.lookups) == 3 and len(api.writes) == 1
        assert api.requests[-1] in api.writes  # the write is last

    def test_ids_only_makes_exactly_the_one_write_request_as_before(self):
        result, api = run(*CREATE, "-r", NET, "-p", POL_DEFAULT, "-g", f"{G_ENG},{G_OPS}")
        assert result.exit_code == 0
        assert len(api.requests) == 1 and api.lookups == []
        assert api.writes[0][1]["groupIds"] == [G_ENG, G_OPS]

    def test_ids_and_names_can_be_mixed(self):
        _, api = run(*CREATE, "-r", NET, "-p", "Strict", "-g", f"{G_SALES},Eng")
        assert api.writes[0][1]["groupIds"] == [G_SALES, G_ENG] and len(api.lookups) == 2  # policy + groups

    def test_the_flag_can_be_repeated_and_spaces_after_commas_are_fine(self):
        _, api = run(*CREATE, "-r", NET, "-p", POL_DEFAULT, "-g", "Eng, Ops", "-g", "Sales")
        assert api.writes[0][1]["groupIds"] == [G_ENG, G_OPS, G_SALES]

    def test_a_group_name_containing_a_comma_is_looked_up_as_two_names_so_use_its_id(self):
        result, api = run(*CREATE, "-r", NET, "-p", POL_DEFAULT, "-g", "Ops, EMEA")
        assert result.exit_code == 1 and api.writes == []
        assert "no group named 'EMEA'" in result.output  # 'Ops' exists, so only the second half is reported

    def test_no_groups_is_still_fine(self):
        result, api = run(*CREATE, "-r", "Office", "-p", "Strict")
        assert result.exit_code == 0 and api.writes[0][1]["groupIds"] == []

    @pytest.mark.parametrize("args,message", [
        (["-r", "Cloud Aplications", "-p", "Strict"], "no Remote Network named 'Cloud Aplications'"),
        (["-r", "Office", "-p", "Strikt"], "no Security Policy named 'Strikt'"),
        (["-r", "Office", "-p", "Strict", "-g", "Nope"], "no group named 'Nope'"),
        (["-r", "Office", "-p", "Strict", "-g", "Dup"], "'Dup' matches 2 groups"),
        (["-r", "Office", "-p", "Strict", "-g", "eng"], "no group named 'eng'"),
    ])
    def test_a_name_that_cannot_be_resolved_stops_everything_before_any_write(self, args, message):
        result, api = run(*CREATE, *args)
        assert result.exit_code == 1 and message in result.output
        assert api.writes == []

    def test_an_ambiguous_group_lists_the_candidate_ids(self):
        result, _ = run(*CREATE, "-r", NET, "-p", POL_DEFAULT, "-g", "Dup")
        assert make_id("Group", 4) in result.output and make_id("Group", 5) in result.output

    def test_problems_in_different_kinds_are_all_reported_together(self):
        result, api = run(*CREATE, "-r", "Nowhere", "-p", "Nothing", "-g", "Nobody,Eng")
        assert result.exit_code == 1 and api.writes == []
        assert result.output.count("Error:") == 3
        for message in ("no Remote Network named 'Nowhere'", "no Security Policy named 'Nothing'", "no group named 'Nobody'"):
            assert message in result.output

    def test_access_commands_also_report_every_kind_at_once(self):
        result, api = run("access_add", "-i", RES, "-g", "Nobody", "-s", "nobody", "-p", "Nothing")
        assert result.exit_code == 1 and result.output.count("Error:") == 3 and api.writes == []

    @pytest.mark.parametrize("error,message", [(TwingateAPIError("boom"), "API error: boom"), (TwingateAuthError("Bad token"), "Authentication error: Bad token")])
    def test_a_failing_lookup_is_reported_like_any_other_api_failure(self, error, message):
        api = Api(); api.error = error
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = api.execute
            result = runner.invoke(app, ["-s", SESSION, "resource", *CREATE, "-r", "Office", "-p", "Strict"])
        assert result.exit_code == 1 and message in result.output and api.writes == []

    def test_bad_protocol_options_are_still_rejected_before_any_lookup(self):
        result, api = run(*CREATE, "-r", "Office", "-p", "Strict", "-t", "ALLOW_ALL", "-c", "[[22,22]]")
        assert result.exit_code != 0 and api.requests == []


class TestAccessAdd:
    def test_group_and_policy_names_become_ids(self):
        result, api = run("access_add", "-i", RES, "-g", "Eng", "-p", "Strict")
        assert result.exit_code == 0, result.output
        (query, variables), = api.writes
        assert variables == {"itemid": RES, "accessids": [{"principalId": G_ENG, "securityPolicyId": POL_STRICT}]}

    def test_one_policy_applies_to_every_group(self):
        _, api = run("access_add", "-i", RES, "-g", "Eng,Ops", "-p", "Strict")
        assert [e["securityPolicyId"] for e in api.writes[0][1]["accessids"]] == [POL_STRICT, POL_STRICT]

    def test_one_policy_per_group_lines_up_in_order(self):
        _, api = run("access_add", "-i", RES, "-g", "Eng,Ops", "-p", "Strict,Default Policy")
        assert [(e["principalId"], e["securityPolicyId"]) for e in api.writes[0][1]["accessids"]] == [(G_ENG, POL_STRICT), (G_OPS, POL_DEFAULT)]

    def test_a_policy_flag_repeated_per_group(self):
        _, api = run("access_add", "-i", RES, "-g", "Eng", "-g", "Ops", "-p", "Strict", "-p", POL_DEFAULT)
        assert [e["securityPolicyId"] for e in api.writes[0][1]["accessids"]] == [POL_STRICT, POL_DEFAULT]

    def test_no_policy_means_none_as_before(self):
        _, api = run("access_add", "-i", RES, "-g", "Eng")
        assert api.writes[0][1]["accessids"] == [{"principalId": G_ENG, "securityPolicyId": None}]

    def test_a_service_account_by_name(self):
        _, api = run("access_add", "-i", RES, "-s", "ci")
        assert api.writes[0][1]["accessids"] == [{"principalId": SA_CI, "securityPolicyId": None}]

    def test_service_accounts_come_before_groups_as_before(self):
        _, api = run("access_add", "-i", RES, "-g", "Eng", "-s", "ci")
        assert [e["principalId"] for e in api.writes[0][1]["accessids"]] == [SA_CI, G_ENG]

    def test_autolock_and_expiry_are_attached_to_every_group_entry(self):
        _, api = run("access_add", "-i", RES, "-g", "Eng,Ops", "-a", "7", "-e", "2027-01-01T00:00:00Z")
        for entry in api.writes[0][1]["accessids"]:
            assert entry["accessPolicy"] == {"mode": "AUTO_LOCK", "durationSeconds": 604800} and entry["expiresAt"] == "2027-01-01T00:00:00Z"
            assert "usageBasedAutolockDurationDays" not in entry

    def test_ids_only_makes_exactly_the_one_write_request_as_before(self):
        result, api = run("access_add", "-i", RES, "-g", f"{G_ENG},{G_OPS}", "-p", POL_STRICT, "-s", SA_CI)
        assert result.exit_code == 0 and len(api.requests) == 1 and api.lookups == []

    def test_the_wrong_number_of_policies_is_refused_before_any_request(self):
        result, api = run("access_add", "-i", RES, "-g", "Eng,Ops,Sales", "-p", "Strict,Default Policy")
        assert result.exit_code == 1 and "Number of Policy IDs" in result.output and api.requests == []

    @pytest.mark.parametrize("args,message", [
        (["-g", "Nope"], "no group named 'Nope'"),
        (["-g", "Eng", "-p", "Nope"], "no Security Policy named 'Nope'"),
        (["-s", "nobody"], "no Service Account named 'nobody'"),
        (["-g", "Dup"], "'Dup' matches 2 groups"),
    ])
    def test_an_unresolvable_name_stops_before_any_write(self, args, message):
        result, api = run("access_add", "-i", RES, *args)
        assert result.exit_code == 1 and message in result.output and api.writes == []


class TestAccessSet:
    def test_names_become_ids_in_the_replacing_call(self):
        result, api = run("access_set", "-i", RES, "-g", "Eng,Ops", "-p", "Default Policy")
        assert result.exit_code == 0
        query, variables = api.writes[0]
        assert "resourceAccessSet" in query
        assert [e["principalId"] for e in variables["accessids"]] == [G_ENG, G_OPS]

    def test_an_unknown_group_never_reaches_the_replacing_call(self):
        result, api = run("access_set", "-i", RES, "-g", "Eng,Nope")
        assert result.exit_code == 1 and api.writes == []


class TestAccessRemove:
    def test_groups_and_service_accounts_by_name(self):
        result, api = run("access_remove", "-i", RES, "-g", "Eng,Ops", "-s", "ci")
        assert result.exit_code == 0, result.output
        query, variables = api.writes[0]
        assert "resourceAccessRemove" in query and variables == {"itemid": RES, "groupid": [G_ENG, G_OPS, SA_CI]}

    def test_ids_still_work_for_groups_and_for_service_accounts_in_g(self):
        result, api = run("access_remove", "-i", RES, "-g", f"{G_ENG},{SA_CI}")
        assert result.exit_code == 0 and len(api.requests) == 1 and api.writes[0][1]["groupid"] == [G_ENG, SA_CI]

    def test_naming_nothing_is_an_error_not_an_empty_removal(self):
        result, api = run("access_remove", "-i", RES)
        assert result.exit_code == 1 and "at least one" in result.output and api.requests == []

    def test_an_unknown_name_removes_nothing(self):
        result, api = run("access_remove", "-i", RES, "-g", "Eng,Nope")
        assert result.exit_code == 1 and api.writes == []


@pytest.mark.parametrize("command", [["create"], ["access_add"], ["access_set"], ["access_remove"]])
def test_help_says_names_are_accepted(command):
    result = runner.invoke(app, ["resource", *command, "--help"])
    assert "exact name" in " ".join(result.output.replace("│", " ").split())
