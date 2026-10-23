"""resource access add|set|remove, the old access_* names, the guard on empty calls, and the hint after resource create."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.commands.test_names_or_ids import G_ENG, NET, POL_DEFAULT, RES, SA_CI, Api
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def invoke(*args, api=None):
    api = api or Api()
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.side_effect = api.execute
        result = runner.invoke(app, ["-s", SESSION, "resource", *args])
    return result, api


CREATE = ["create", "-a", "app.example.com", "-n", "App", "-r", NET, "-p", POL_DEFAULT]


class TestNewNames:
    @pytest.mark.parametrize("new,old,flags", [
        (["access", "add"], "access_add", ["-g", "Eng", "-p", "Strict"]),
        (["access", "set"], "access_set", ["-g", "Eng,Ops", "-s", "ci"]),
        (["access", "remove"], "access_remove", ["-g", "Eng", "-s", "ci"]),
    ])
    def test_each_new_command_sends_exactly_what_the_old_name_does(self, new, old, flags):
        result_new, api_new = invoke(*new, "-i", RES, *flags)
        result_old, api_old = invoke(old, "-i", RES, *flags)
        assert result_new.exit_code == result_old.exit_code == 0, result_new.output
        assert api_new.writes == api_old.writes and len(api_new.writes) == 1

    def test_the_sub_group_lists_its_commands(self):
        result, _ = invoke("access", "--help")
        assert result.exit_code == 0 and all(word in result.output for word in ("add", "set", "remove"))

    def test_the_old_names_are_hidden_from_help_but_still_run(self):
        listing, _ = invoke("--help")
        assert "access_set" not in listing.output and "access_add" not in listing.output and "access_remove" not in listing.output
        assert "access " in listing.output
        for old in ("access_add", "access_set", "access_remove"):
            result, _ = invoke(old, "--help")
            assert result.exit_code == 0

    def test_the_help_of_set_says_it_replaces_everything(self):
        result, _ = invoke("access", "set", "--help")
        assert "REPLACES all" in " ".join(result.output.split()) and "--clear" in result.output


class TestEmptyCalls:
    @pytest.mark.parametrize("name", [["access", "set"], ["access_set"]])
    def test_set_with_nobody_named_is_refused_before_any_request(self, name):
        result, api = invoke(*name, "-i", RES)
        assert result.exit_code == 1 and api.requests == []
        assert "REPLACES all access" in " ".join(result.output.split()) and "--clear" in result.output and "access add" in result.output

    def test_set_with_only_a_policy_is_still_nobody(self):
        result, api = invoke("access", "set", "-i", RES, "-p", "Strict")
        assert result.exit_code == 1 and api.requests == []

    @pytest.mark.parametrize("name", [["access", "set"], ["access_set"]])
    def test_clear_is_the_explicit_way_to_remove_all_access(self, name):
        result, api = invoke(*name, "-i", RES, "--clear")
        assert result.exit_code == 0, result.output
        (query, variables), = api.writes
        assert "resourceAccessSet" in query and variables == {"accessids": [], "itemid": RES} and api.lookups == []

    @pytest.mark.parametrize("extra", [["-g", "Eng"], ["-s", "ci"]])
    def test_clear_cannot_be_combined_with_anyone_named(self, extra):
        result, api = invoke("access", "set", "-i", RES, "--clear", *extra)
        assert result.exit_code == 1 and api.requests == [] and "cannot be combined" in result.output

    @pytest.mark.parametrize("name", [["access", "add"], ["access_add"]])
    def test_add_with_nobody_named_is_refused_before_any_request(self, name):
        result, api = invoke(*name, "-i", RES)
        assert result.exit_code == 1 and api.requests == [] and "at least one group (-g) or service account (-s)" in result.output

    def test_set_with_someone_named_still_works_and_does_not_need_clear(self):
        result, api = invoke("access", "set", "-i", RES, "-g", G_ENG)
        assert result.exit_code == 0 and api.writes[0][1]["accessids"] == [{"principalId": G_ENG, "securityPolicyId": None}]

    def test_remove_with_nobody_named_is_still_refused(self):
        result, api = invoke("access", "remove", "-i", RES)
        assert result.exit_code == 1 and api.requests == []


class TestCreateHint:
    def test_without_groups_it_says_how_to_give_access_and_names_the_new_resource_and_session(self):
        result, api = invoke(*CREATE)
        assert result.exit_code == 0 and len(api.writes) == 1
        hint = " ".join(result.stderr.split())
        assert "no group has access to this Resource yet" in hint
        assert f"tgcli -s {SESSION} resource access add -i {RES} -g <group name or ID>" in hint
        assert "add -g <group> to 'resource create'" in hint

    def test_the_hint_is_on_stderr_only_so_piped_output_is_unchanged(self):
        result, _ = invoke(*CREATE)
        assert "Note:" not in result.stdout and RES in result.stdout

    def test_with_groups_there_is_no_hint(self):
        result, _ = invoke(*CREATE, "-g", G_ENG)
        assert result.exit_code == 0 and "Note:" not in result.output

    def test_a_refused_create_gets_no_hint(self):
        api = Api()
        original = api.execute
        api.execute = lambda q, v=None: {"data": {"resourceCreate": {"ok": False, "error": "name taken", "entity": None}}} if "resourceCreate" in q else original(q, v)
        result, _ = invoke(*CREATE, api=api)
        assert "Note:" not in result.output
