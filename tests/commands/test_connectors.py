"""Tests for connector commands."""

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


class TestConnectorDelete:
    def _invoke(self, payload):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = {"data": {"connectorDelete": payload}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "connector", "delete", "-i", "conn-1"])
        return result, inst

    def test_sends_connector_id_to_delete_mutation(self):
        result, inst = self._invoke({"ok": True, "error": None})
        assert result.exit_code == 0
        query, variables = inst.execute.call_args.args
        assert "connectorDelete(id: $id)" in query
        assert variables == {"id": "conn-1"}

    def test_reports_success(self):
        result, _ = self._invoke({"ok": True, "error": None})
        assert result.output.split() == ["ok,error", "True,"]

    def test_reports_api_error(self):
        result, _ = self._invoke({"ok": False, "error": "Connector with id 'x' does not exist"})
        assert "False" in result.output and "does not exist" in result.output

    def test_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "connector", "delete"]).exit_code != 0

    def test_auth_error_exits_nonzero(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, "connector", "delete", "-i", "conn-1"])
        assert result.exit_code != 0
