"""Tests for access-request commands."""

from __future__ import annotations

import json
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


def _node(request_id="ar-1", status="PENDING"):
    return {
        "node": {
            "id": request_id,
            "status": status,
            "reason": "need it",
            "requestedAt": "2026-10-01T00:00:00+00:00",
            "user": {"id": "u-1", "email": "a@b.com"},
            "resource": {"id": "r-1", "name": "Wiki"},
        }
    }


def _sent_variables(mock_instance):
    _query, make_vars, _key = mock_instance.paginate.call_args.args
    return make_vars("0")


class TestList:
    def _invoke(self, args, pages=None):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.paginate.return_value = pages if pages is not None else [[_node()]]
            result = runner.invoke(app, ["-s", SESSION, *args])
        return result, inst

    def test_default_requests_every_status(self):
        result, inst = self._invoke(["access-request", "list"])
        assert result.exit_code == 0
        assert _sent_variables(inst)["filter"] == {"status": {"in": ["PENDING", "APPROVED", "REJECTED"]}}

    def test_status_is_case_insensitive_and_repeatable(self):
        _, inst = self._invoke(["access-request", "list", "--status", "pending", "--status", "Rejected"])
        assert _sent_variables(inst)["filter"] == {"status": {"in": ["PENDING", "REJECTED"]}}

    def test_invalid_status_rejected_before_any_api_call(self):
        result, inst = self._invoke(["access-request", "list", "--status", "NOPE"])
        assert result.exit_code != 0
        inst.paginate.assert_not_called()

    def test_user_and_resource_filters(self):
        _, inst = self._invoke(
            ["access-request", "list", "--status", "PENDING", "--user-id", "u1", "--user-id", "u2", "--resource-id", "r1"]
        )
        assert _sent_variables(inst)["filter"] == {
            "status": {"in": ["PENDING"]},
            "userId": {"in": ["u1", "u2"]},
            "resourceId": {"in": ["r1"]},
        }

    def test_csv_output_flattens_user_and_resource(self):
        result, _ = self._invoke(["-f", "csv", "access-request", "list"], [[_node("ar-9", "APPROVED")]])
        header, row = result.output.strip().splitlines()
        assert header == "id,status,requestedAt,user.email,user.id,resource.name,resource.id,reason"
        assert row.startswith("ar-9,APPROVED,") and "a@b.com" in row and "Wiki" in row

    def test_auth_error_exits_nonzero(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, "access-request", "list"])
        assert result.exit_code != 0


class TestShow:
    def test_show_flattens_fields(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {"data": {"accessRequest": _node()["node"]}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "access-request", "show", "-i", "ar-1"])
        assert result.exit_code == 0
        assert "a@b.com" in result.output and "Wiki" in result.output

    def test_show_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "access-request", "show"]).exit_code != 0


@pytest.mark.parametrize("command,key", [("approve", "accessRequestApprove"), ("reject", "accessRequestReject")])
class TestApproveReject:
    def _invoke(self, command, key, payload):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = {"data": {key: payload}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "access-request", command, "-i", "ar-1"])
        return result, inst

    def test_sends_id_and_reports_ok(self, command, key):
        result, inst = self._invoke(command, key, {"ok": True, "error": None})
        assert result.exit_code == 0
        assert inst.execute.call_args.args[1] == {"itemID": "ar-1"}
        assert result.output.split() == ["ok,error", "True,"]

    def test_reports_api_error(self, command, key):
        result, _ = self._invoke(command, key, {"ok": False, "error": "Request already resolved"})
        assert "False" in result.output and "Request already resolved" in result.output

    def test_requires_id(self, command, key):
        assert runner.invoke(app, ["-s", SESSION, "access-request", command]).exit_code != 0
