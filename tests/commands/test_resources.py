"""Tests for resource commands (the most complex command module)."""

from __future__ import annotations

from unittest.mock import patch

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


def _res_list_response(edges):
    return {
        "data": {
            "resources": {
                "edges": edges,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }


def _mutation_ok(mutation_key, entity=None):
    return {
        "data": {
            mutation_key: {
                "ok": True,
                "error": None,
                "entity": entity or {"id": "res-1", "name": "My Resource"},
            }
        }
    }


SAMPLE_RESOURCE_EDGE = {
    "node": {
        "id": "res-1",
        "name": "My Resource",
        "isActive": True,
        "isVisible": True,
        "isBrowserShortcutEnabled": False,
        "usageBasedAutolockDurationDays": None,
        "alias": None,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "address": {"type": "DNS", "value": "*.example.com"},
        "remoteNetwork": {"id": "rn-1", "name": "Office"},
        "securityPolicy": None,
        "access": {"edges": []},
        "tags": [],
        "approvalMode": "MANUAL",
        "protocols": {
            "allowIcmp": True,
            "tcp": {"policy": "ALLOW_ALL", "ports": []},
            "udp": {"policy": "ALLOW_ALL", "ports": []},
        },
    }
}


class TestResourceList:
    def test_list_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[SAMPLE_RESOURCE_EDGE]]
            result = runner.invoke(app, ["-s", SESSION, "resource", "list"])
        assert result.exit_code == 0

    def test_list_api_error_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = TwingateAPIError("Fail")
            result = runner.invoke(app, ["-s", SESSION, "resource", "list"])
        assert result.exit_code != 0


class TestResourceShow:
    def test_show_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {
                "data": {
                    "resource": {
                        "id": "res-1",
                        "name": "Res",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "updatedAt": "2024-01-01T00:00:00Z",
                        "isVisible": True,
                        "isBrowserShortcutEnabled": False,
                        "usageBasedAutolockDurationDays": None,
                        "isActive": True,
                        "remoteNetwork": {"name": "Office", "id": "rn-1"},
                        "address": {"type": "DNS", "value": "*.example.com"},
                        "protocols": {
                            "allowIcmp": True,
                            "tcp": {"policy": "ALLOW_ALL", "ports": []},
                            "udp": {"policy": "ALLOW_ALL", "ports": []},
                        },
                    }
                }
            }
            result = runner.invoke(app, ["-s", SESSION, "resource", "show", "-i", "res-1"])
        assert result.exit_code == 0


class TestResourceCreate:
    def test_create_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = _mutation_ok(
                "resourceCreate", {"id": "res-new", "name": "New Res", "isVisible": True, "securityPolicy": None}
            )
            result = runner.invoke(
                app,
                [
                    "-s", SESSION, "resource", "create",
                    "-a", "app.example.com",
                    "-n", "New Res",
                    "-r", "rn-1",
                    "-t", "ALLOW_ALL",
                    "-u", "ALLOW_ALL",
                    "-p", "pol-1",
                ],
            )
        assert result.exit_code == 0

    def test_create_allow_all_with_tcp_ports_exits_nonzero(self, mock_keyring):
        result = runner.invoke(
            app,
            [
                "-s", SESSION, "resource", "create",
                "-a", "app.example.com",
                "-n", "New Res",
                "-r", "rn-1",
                "-t", "ALLOW_ALL",
                "-c", "[[22,22]]",  # ALLOW_ALL + non-empty range = invalid
                "-u", "ALLOW_ALL",
                "-p", "pol-1",
            ],
        )
        assert result.exit_code != 0

    def test_create_requires_address(self, mock_keyring):
        result = runner.invoke(
            app,
            ["-s", SESSION, "resource", "create", "-n", "New Res", "-r", "rn-1", "-t", "ALLOW_ALL", "-u", "ALLOW_ALL", "-p", "pol-1"],
        )
        assert result.exit_code != 0


class TestResourceDelete:
    def test_delete_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {
                "data": {"resourceDelete": {"ok": True, "error": None}}
            }
            result = runner.invoke(app, ["-s", SESSION, "resource", "delete", "-i", "res-1"])
        assert result.exit_code == 0


class TestResourceVisibility:
    def test_visibility_true(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = _mutation_ok(
                "resourceUpdate", {"id": "res-1", "name": "R", "isVisible": True, "isBrowserShortcutEnabled": False}
            )
            result = runner.invoke(
                app, ["-s", SESSION, "resource", "visibility", "-i", "res-1", "-v", "true"]
            )
        assert result.exit_code == 0

    def test_visibility_invalid_bool(self, mock_keyring):
        result = runner.invoke(
            app, ["-s", SESSION, "resource", "visibility", "-i", "res-1", "-v", "maybe"]
        )
        assert result.exit_code != 0
