"""user create / user role must accept every role the Twingate API defines and pass it through unchanged."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.session import SessionManager
from tgcli.main import app
from tgcli.validators.user import VALID_ROLES

runner = CliRunner()
SESSION = "TestSess"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def invoke(*args):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.execute.return_value = {"data": {"userRoleUpdate": {"ok": True, "error": None, "entity": {
            "id": "u1", "state": "ACTIVE", "email": "a@b.io", "role": "MEMBER", "firstName": "A", "lastName": "B",
            "createdAt": "t", "updatedAt": "t", "groups": {"edges": []}}}, "userCreate": {"ok": True, "error": None, "entity": {"id": "u1"}}}}
        result = runner.invoke(app, ["-s", SESSION, "user", *args])
    return result, inst


@pytest.mark.parametrize("role", VALID_ROLES)
class TestEveryRole:
    def test_user_role_sends_the_role_to_the_api(self, role):
        result, inst = invoke("role", "-i", "u1", "-r", role)
        assert result.exit_code == 0, result.output
        assert inst.execute.call_args.args[1] == {"itemid": "u1", "userRole": role}

    def test_a_lowercase_role_is_sent_in_uppercase(self, role):
        _, inst = invoke("role", "-i", "u1", "-r", role.lower())
        assert inst.execute.call_args.args[1]["userRole"] == role

    def test_user_create_sends_the_role_to_the_api(self, role):
        result, inst = invoke("create", "-e", "a@b.io", "-f", "A", "-l", "B", "-r", role)
        assert result.exit_code == 0, result.output
        assert inst.execute.call_args.args[1]["userRole"] == role


class TestInvalidRoleNeverReachesTheApi:
    @pytest.mark.parametrize("command", [["role", "-i", "u1"], ["create", "-e", "a@b.io", "-f", "A", "-l", "B"]])
    def test_rejected_before_any_request(self, command):
        result, inst = invoke(*command, "-r", "SUPERUSER")
        assert result.exit_code != 0
        inst.execute.assert_not_called()


@pytest.mark.parametrize("command", [["role"], ["create"]])
def test_help_lists_every_role(command):
    result = runner.invoke(app, ["user", *command, "--help"])
    flat = " ".join(result.output.replace("│", " ").split())
    for role in VALID_ROLES:
        assert role in flat, role
