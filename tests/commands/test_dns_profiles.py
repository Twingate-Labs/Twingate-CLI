"""Tests for dns-profile create and delete."""

from __future__ import annotations

import csv
import io
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


class TestCreate:
    def _invoke(self, payload):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = {"data": {"dnsFilteringProfileCreate": payload}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "dns-profile", "create", "-n", "Contractors"])
        return result, inst

    def test_sends_name_and_shows_new_profile(self):
        result, inst = self._invoke({"ok": True, "error": None, "entity": {"id": "p-1", "name": "Contractors", "priority": 0.75}})
        assert result.exit_code == 0
        query, variables = inst.execute.call_args.args
        assert "dnsFilteringProfileCreate(name: $name)" in query and variables == {"name": "Contractors"}
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert (row["ok"], row["id"], row["name"], row["priority"]) == ("True", "p-1", "Contractors", "0.75")

    def test_reports_api_error(self):
        result, _ = self._invoke({"ok": False, "error": "Name already in use", "entity": None})
        assert "False" in result.output and "already in use" in result.output

    def test_requires_name(self):
        assert runner.invoke(app, ["-s", SESSION, "dns-profile", "create"]).exit_code != 0

    def test_auth_error_exits_nonzero(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = TwingateAuthError("Bad token")
            assert runner.invoke(app, ["-s", SESSION, "dns-profile", "create", "-n", "x"]).exit_code != 0


class TestDelete:
    def _invoke(self, found, payload=None):
        def execute(query, variables=None):
            if "dnsFilteringProfile(id" in query:
                return {"data": {"dnsFilteringProfile": found}}
            return {"data": {"dnsFilteringProfileDelete": payload or {"ok": True, "error": None}}}

        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.side_effect = execute
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "dns-profile", "delete", "-i", "p-1"])
        return result, inst

    def test_deletes_an_existing_profile(self):
        result, inst = self._invoke({"id": "p-1"})
        assert result.exit_code == 0 and result.output.split() == ["ok,error", "True,"]
        query, variables = inst.execute.call_args.args
        assert "dnsFilteringProfileDelete(id: $id)" in query and variables == {"id": "p-1"}

    def test_unknown_id_errors_without_calling_delete(self):
        result, inst = self._invoke(None)
        assert result.exit_code != 0
        assert inst.execute.call_count == 1

    def test_reports_api_error(self):
        result, _ = self._invoke({"id": "p-1"}, {"ok": False, "error": "Cannot delete the default profile"})
        assert "False" in result.output and "default profile" in result.output

    def test_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "dns-profile", "delete"]).exit_code != 0
