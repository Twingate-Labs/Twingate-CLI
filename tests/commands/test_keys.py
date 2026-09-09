"""Tests for Service Account Key commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
TOKEN = "tok-test"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", TOKEN)


def _show_key_response(name="old-key", sa_id="sa-1", sa_name="CI Bot"):
    return {
        "data": {
            "serviceAccountKey": {
                "id": "key-old",
                "name": name,
                "createdAt": "2024-01-01T00:00:00Z",
                "expiresAt": "2024-04-01T00:00:00Z",
                "revokedAt": None,
                "updatedAt": "2024-01-01T00:00:00Z",
                "status": "ACTIVE",
                "serviceAccount": {"id": sa_id, "name": sa_name},
            }
        }
    }


def _create_key_response(ok=True):
    return {
        "data": {
            "serviceAccountKeyCreate": {
                "ok": ok,
                "error": None if ok else "boom",
                "token": "tgp_newtoken",
                "entity": {
                    "id": "key-new",
                    "name": "old-key (rotated)",
                    "expiresAt": "2025-01-01T00:00:00Z",
                    "createdAt": "2024-06-01T00:00:00Z",
                    "status": "ACTIVE",
                },
            }
        }
    }


def _revoke_key_response(ok=True):
    return {"data": {"serviceAccountKeyRevoke": {"ok": ok, "error": None if ok else "revoke failed"}}}


class TestKeyRotate:
    def test_rotate_success(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = [
                _show_key_response(),
                _create_key_response(),
                _revoke_key_response(),
            ]
            result = runner.invoke(app, ["-s", SESSION, "key", "rotate", "-i", "key-old"])
        assert result.exit_code == 0
        assert "key-new" in result.output
        assert "tgp_newtoken" in result.output

    def test_rotate_uses_default_name(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = [
                _show_key_response(name="prod-key"),
                _create_key_response(),
                _revoke_key_response(),
            ]
            result = runner.invoke(app, ["-s", SESSION, "key", "rotate", "-i", "key-old"])
            create_call = MockClient.return_value.execute.call_args_list[1]
        assert result.exit_code == 0
        assert create_call.args[1]["name"] == "prod-key (rotated)"
        assert create_call.args[1]["serviceAccountId"] == "sa-1"

    def test_rotate_key_not_found_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {"data": {"serviceAccountKey": None}}
            result = runner.invoke(app, ["-s", SESSION, "key", "rotate", "-i", "missing-key"])
        assert result.exit_code != 0

    def test_rotate_create_failure_leaves_old_key(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = [
                _show_key_response(),
                _create_key_response(ok=False),
            ]
            result = runner.invoke(app, ["-s", SESSION, "key", "rotate", "-i", "key-old"])
        assert result.exit_code != 0
        assert MockClient.return_value.execute.call_count == 2  # revoke never attempted

    def test_rotate_revoke_failure_warns_and_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = [
                _show_key_response(),
                _create_key_response(),
                _revoke_key_response(ok=False),
            ]
            result = runner.invoke(app, ["-s", SESSION, "key", "rotate", "-i", "key-old"])
        assert result.exit_code != 0
        assert "key-new" in result.output
        assert "manually" in result.output

    def test_rotate_show_api_error_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = TwingateAPIError("Fail")
            result = runner.invoke(app, ["-s", SESSION, "key", "rotate", "-i", "key-old"])
        assert result.exit_code != 0

    def test_rotate_invalid_expiration_exits_nonzero(self, mock_keyring):
        result = runner.invoke(
            app, ["-s", SESSION, "key", "rotate", "-i", "key-old", "-e", "9999"]
        )
        assert result.exit_code != 0
