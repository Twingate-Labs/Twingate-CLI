"""Tests for SessionManager (keyring-backed credential storage)."""

from __future__ import annotations

import pytest

from tgcli.client.exceptions import TwingateAuthError
from tgcli.client.session import SERVICE_NAME, SessionManager


class TestStore:
    def test_store_persists_token_and_tenant(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-123")
        assert mock_keyring[(SERVICE_NAME, "MySess:token")] == "tok-123"
        assert mock_keyring[(SERVICE_NAME, "MySess:tenant")] == "mytenant"

    def test_store_no_staging_flag_by_default(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-123")
        assert (SERVICE_NAME, "MySess:staging") not in mock_keyring

    def test_store_staging_flag(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-123", staging=True)
        assert mock_keyring[(SERVICE_NAME, "MySess:staging")] == "true"

    def test_store_adds_to_index(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-123")
        sessions = SessionManager.list_sessions()
        assert "MySess" in sessions

    def test_store_multiple_sessions(self, mock_keyring):
        SessionManager.store("Sess1", "t1", "tok1")
        SessionManager.store("Sess2", "t2", "tok2")
        sessions = SessionManager.list_sessions()
        assert "Sess1" in sessions
        assert "Sess2" in sessions


class TestDelete:
    def test_delete_removes_credentials(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-123")
        SessionManager.delete("MySess")
        assert (SERVICE_NAME, "MySess:token") not in mock_keyring
        assert (SERVICE_NAME, "MySess:tenant") not in mock_keyring

    def test_delete_removes_from_index(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-123")
        SessionManager.delete("MySess")
        assert "MySess" not in SessionManager.list_sessions()

    def test_delete_nonexistent_does_not_raise(self, mock_keyring):
        # Should not raise even if credentials don't exist
        SessionManager.delete("ghost-session")


class TestGetToken:
    def test_returns_token_for_known_session(self, mock_keyring):
        SessionManager.store("MySess", "mytenant", "tok-abc")
        assert SessionManager.get_token("MySess") == "tok-abc"

    def test_raises_auth_error_for_unknown_session(self, mock_keyring):
        with pytest.raises(TwingateAuthError, match="MySess"):
            SessionManager.get_token("MySess")


class TestGetUrl:
    def test_production_url(self, mock_keyring):
        SessionManager.store("MySess", "acme", "tok-123")
        assert SessionManager.get_url("MySess") == "https://acme.twingate.com/api/graphql/"

    def test_staging_url(self, mock_keyring):
        SessionManager.store("MySess", "acme", "tok-123", staging=True)
        assert SessionManager.get_url("MySess") == "https://acme.stg.opstg.com/api/graphql/"

    def test_raises_auth_error_for_missing_tenant(self, mock_keyring):
        with pytest.raises(TwingateAuthError, match="MySess"):
            SessionManager.get_url("MySess")


class TestListSessions:
    def test_empty_when_no_sessions(self, mock_keyring):
        assert SessionManager.list_sessions() == []

    def test_lists_all_stored_sessions(self, mock_keyring):
        SessionManager.store("A", "ta", "tokA")
        SessionManager.store("B", "tb", "tokB")
        sessions = SessionManager.list_sessions()
        assert set(sessions) == {"A", "B"}

    def test_no_duplicates_on_double_store(self, mock_keyring):
        SessionManager.store("A", "ta", "tokA")
        SessionManager.store("A", "ta", "tokA2")
        sessions = SessionManager.list_sessions()
        assert sessions.count("A") == 1


class TestRandomSessionName:
    def test_returns_non_empty_string(self):
        name = SessionManager.random_session_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_uniqueness(self):
        # Very unlikely to get 10 identical names
        names = {SessionManager.random_session_name() for _ in range(10)}
        assert len(names) > 1
