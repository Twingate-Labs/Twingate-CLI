"""Tests for device commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
TOKEN = "tok-test"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", TOKEN)


def _make_list_response(edges):
    return {
        "data": {
            "devices": {
                "edges": edges,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }


def _make_mutation_response(mutation_key, entity=None):
    return {
        "data": {
            mutation_key: {
                "ok": True,
                "error": None,
                "entity": entity or {"id": "dev-1", "name": "Test Device", "isTrusted": True, "activeState": "ACTIVE"},
            }
        }
    }


class TestDeviceList:
    def test_list_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.return_value = [
                [{"node": {"id": "dev-1", "name": "Laptop", "isTrusted": True, "osName": "macOS", "deviceType": "LAPTOP", "activeState": "ACTIVE", "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "lastConnectedAt": None, "osVersion": "14.0", "hardwareModel": "MBP", "hostname": "host", "username": "u", "serialNumber": "SN1", "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"}, "clientVersion": "1.0", "manufacturerName": "Apple"}}]
            ]
            result = runner.invoke(app, ["-s", SESSION, "device", "list"])
        assert result.exit_code == 0

    def test_list_no_session_exits_nonzero(self, mock_keyring):
        result = runner.invoke(app, ["device", "list"])
        assert result.exit_code != 0

    def test_list_auth_error_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, "device", "list"])
        assert result.exit_code != 0

    def test_list_csv_format(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.return_value = [
                [{"node": {"id": "dev-1", "name": "Laptop", "isTrusted": True, "osName": "macOS", "deviceType": "LAPTOP", "activeState": "ACTIVE", "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "lastConnectedAt": None, "osVersion": "14.0", "hardwareModel": "MBP", "hostname": "host", "username": "u", "serialNumber": "SN1", "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"}, "clientVersion": "1.0", "manufacturerName": "Apple"}}]
            ]
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "device", "list"])
        assert result.exit_code == 0


class TestDeviceShow:
    def test_show_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.execute.return_value = {
                "data": {
                    "device": {
                        "id": "dev-1",
                        "name": "Laptop",
                        "isTrusted": True,
                        "osName": "macOS",
                        "deviceType": "LAPTOP",
                        "activeState": "ACTIVE",
                        "lastFailedLoginAt": None,
                        "lastSuccessfulLoginAt": None,
                        "lastConnectedAt": None,
                        "osVersion": "14.0",
                        "hardwareModel": "MBP",
                        "hostname": "host",
                        "username": "u",
                        "serialNumber": "SN1",
                        "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"},
                        "clientVersion": "1.0",
                        "manufacturerName": "Apple",
                    }
                }
            }
            result = runner.invoke(app, ["-s", SESSION, "device", "show", "-i", "dev-1"])
        assert result.exit_code == 0

    def test_show_requires_id(self, mock_keyring):
        result = runner.invoke(app, ["-s", SESSION, "device", "show"])
        assert result.exit_code != 0


class TestDeviceUpdateTrust:
    def test_update_trust_true(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.execute.return_value = _make_mutation_response("deviceUpdate")
            result = runner.invoke(
                app, ["-s", SESSION, "device", "updateTrust", "-l", "dev-1", "-t", "True"]
            )
        assert result.exit_code == 0

    def test_update_trust_invalid_bool(self, mock_keyring):
        result = runner.invoke(
            app, ["-s", SESSION, "device", "updateTrust", "-l", "dev-1", "-t", "maybe"]
        )
        assert result.exit_code != 0


class TestDeviceBlock:
    def test_block_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.execute.return_value = _make_mutation_response("deviceBlock")
            result = runner.invoke(app, ["-s", SESSION, "device", "block", "-i", "dev-1"])
        assert result.exit_code == 0
