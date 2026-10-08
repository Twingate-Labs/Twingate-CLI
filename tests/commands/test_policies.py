"""Tests for policy commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def _ok_payload(group_ids):
    return {
        "ok": True,
        "error": None,
        "entity": {
            "id": "pol-1",
            "name": "Device Only",
            "policyType": "RESOURCE",
            "groups": {"edges": [{"node": {"id": g, "name": g}} for g in group_ids]},
        },
    }


class TestPolicyUpdate:
    def _invoke(self, args, payload=None):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = {"data": {"securityPolicyUpdate": payload or _ok_payload(["g1"])}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "policy", "update", *args])
        return result, inst

    def _variables(self, inst):
        return inst.execute.call_args.args[1]

    def test_add_groups_sends_only_added_and_omits_the_rest(self):
        result, inst = self._invoke(["-i", "pol-1", "-a", "g1, g2"])
        assert result.exit_code == 0
        assert self._variables(inst) == {"id": "pol-1", "addedGroupIds": ["g1", "g2"]}

    def test_remove_groups_sends_only_removed(self):
        _, inst = self._invoke(["-i", "pol-1", "-r", "g3"])
        assert self._variables(inst) == {"id": "pol-1", "removedGroupIds": ["g3"]}

    def test_add_and_remove_together(self):
        _, inst = self._invoke(["-i", "pol-1", "-a", "g1", "-r", "g2"])
        assert self._variables(inst) == {"id": "pol-1", "addedGroupIds": ["g1"], "removedGroupIds": ["g2"]}

    def test_set_groups_sends_only_replacement(self):
        _, inst = self._invoke(["-i", "pol-1", "--set-groups", "g1,g2"])
        assert self._variables(inst) == {"id": "pol-1", "groupIds": ["g1", "g2"]}

    def test_output_lists_resulting_groups(self):
        result, _ = self._invoke(["-i", "pol-1", "-a", "g1"], _ok_payload(["g1", "g2"]))
        header, row = result.output.strip().splitlines()
        assert header == "ok,error,id,name,policyType,groups"
        assert row.startswith("True,,pol-1,Device Only,RESOURCE,") and "g1" in row and "g2" in row

    def test_reports_api_error(self):
        result, _ = self._invoke(["-i", "pol-1", "-a", "g1"], {"ok": False, "error": "Group does not exist", "entity": None})
        assert "False" in result.output and "Group does not exist" in result.output

    @pytest.mark.parametrize(
        "args",
        [
            ["-i", "pol-1"],
            ["-i", "pol-1", "-a", " , "],
            ["-i", "pol-1", "--set-groups", "g1", "-a", "g2"],
            ["-i", "pol-1", "--set-groups", "g1", "-r", "g2"],
        ],
    )
    def test_invalid_combinations_rejected_before_any_api_call(self, args):
        result, inst = self._invoke(args)
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_requires_policy_id(self):
        assert runner.invoke(app, ["-s", SESSION, "policy", "update", "-a", "g1"]).exit_code != 0

    def test_auth_error_exits_nonzero(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, "policy", "update", "-i", "pol-1", "-a", "g1"])
        assert result.exit_code != 0
