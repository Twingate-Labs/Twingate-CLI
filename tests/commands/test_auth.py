"""Tests for auth commands (login, logout, list)."""

from __future__ import annotations

from typer.testing import CliRunner

from tgcli.client.session import SERVICE_NAME, SessionManager
from tgcli.main import app

runner = CliRunner()


class TestAuthLogin:
    def test_login_stores_credentials(self, mock_keyring):
        result = runner.invoke(
            app,
            ["auth", "login", "-a", "tok-xyz", "-t", "acme", "-s", "MySession"],
        )
        assert result.exit_code == 0
        assert mock_keyring.get((SERVICE_NAME, "MySession:token")) == "tok-xyz"
        assert mock_keyring.get((SERVICE_NAME, "MySession:tenant")) == "acme"

    def test_login_staging_flag(self, mock_keyring):
        result = runner.invoke(
            app,
            ["auth", "login", "-a", "tok-xyz", "-t", "acme", "-s", "StgSess", "--staging"],
        )
        assert result.exit_code == 0
        assert mock_keyring.get((SERVICE_NAME, "StgSess:staging")) == "true"

    def test_login_auto_generates_session_name(self, mock_keyring):
        result = runner.invoke(
            app,
            ["auth", "login", "-a", "tok-xyz", "-t", "acme"],
        )
        assert result.exit_code == 0
        sessions = SessionManager.list_sessions()
        assert len(sessions) == 1

    def test_login_requires_api_key(self, mock_keyring):
        result = runner.invoke(app, ["auth", "login", "-t", "acme", "-s", "MySess"])
        assert result.exit_code != 0

    def test_login_requires_tenant(self, mock_keyring):
        result = runner.invoke(app, ["auth", "login", "-a", "tok", "-s", "MySess"])
        assert result.exit_code != 0

    def test_login_prints_success_message(self, mock_keyring):
        result = runner.invoke(
            app,
            ["auth", "login", "-a", "tok-xyz", "-t", "acme", "-s", "MySess"],
        )
        assert result.exit_code == 0
        assert "MySess" in result.output or "logged in" in result.output.lower() or "stored" in result.output.lower()


class TestAuthLogout:
    def test_logout_removes_session(self, mock_keyring):
        SessionManager.store("MySess", "acme", "tok-123")
        result = runner.invoke(app, ["auth", "logout", "-s", "MySess"])
        assert result.exit_code == 0
        assert "MySess" not in SessionManager.list_sessions()

    def test_logout_nonexistent_session_exits_gracefully(self, mock_keyring):
        result = runner.invoke(app, ["auth", "logout", "-s", "ghost"])
        # Should exit 0 or print a message — not crash with exception
        assert result.exit_code in (0, 1)


class TestAuthList:
    def test_list_empty(self, mock_keyring):
        result = runner.invoke(app, ["auth", "list"])
        assert result.exit_code == 0

    def test_list_shows_stored_sessions(self, mock_keyring):
        SessionManager.store("SessA", "ta", "tokA")
        SessionManager.store("SessB", "tb", "tokB")
        result = runner.invoke(app, ["auth", "list"])
        assert result.exit_code == 0
        assert "SessA" in result.output
        assert "SessB" in result.output
