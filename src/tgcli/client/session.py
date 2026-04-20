"""Session management using OS keychain via the keyring library.

Replaces the XOR-based flat-file storage in the original DataUtils.py.
Keyring keys follow the pattern:
  "{session}:token"   — API token
  "{session}:tenant"  — Twingate tenant name
  "{session}:staging" — "true" if targeting staging environment
  "__sessions__"      — comma-joined index of all known session names
"""

from __future__ import annotations

import json
import random

import keyring
import keyring.errors

from tgcli.client.exceptions import TwingateAuthError

SERVICE_NAME = "tgcli"

COLORS = [
    "Blue", "Pink", "Yellow", "Green", "Red",
    "Orange", "Purple", "White", "Black", "Silver", "Golden",
]
ANIMALS = [
    "Dog", "Eel", "Cat", "Bat", "Cow",
    "Elk", "Fox", "Ape", "Boa", "Yak", "Fly",
]


class SessionManager:
    """Manage Twingate CLI sessions stored in the OS keychain."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def random_session_name() -> str:
        """Generate a random ColorAnimal session name (e.g. 'BlueDog')."""
        return random.choice(COLORS) + random.choice(ANIMALS)

    @staticmethod
    def store(session: str, tenant: str, token: str, staging: bool = False) -> None:
        """Persist session credentials to the OS keychain."""
        keyring.set_password(SERVICE_NAME, f"{session}:token", token)
        keyring.set_password(SERVICE_NAME, f"{session}:tenant", tenant)
        if staging:
            keyring.set_password(SERVICE_NAME, f"{session}:staging", "true")
        SessionManager._add_to_index(session)

    @staticmethod
    def delete(session: str) -> None:
        """Remove a session's credentials from the OS keychain."""
        for suffix in ("token", "tenant", "staging"):
            try:
                keyring.delete_password(SERVICE_NAME, f"{session}:{suffix}")
            except keyring.errors.PasswordDeleteError:
                pass
        SessionManager._remove_from_index(session)

    @staticmethod
    def get_token(session: str) -> str:
        """Retrieve the API token for a session.

        Raises:
            TwingateAuthError: If no token is found for the given session name.
        """
        token = keyring.get_password(SERVICE_NAME, f"{session}:token")
        if not token:
            raise TwingateAuthError(
                f"Session '{session}' not found. Run 'tgcli auth login' first."
            )
        return token

    @staticmethod
    def get_url(session: str) -> str:
        """Build the GraphQL endpoint URL for a session.

        Raises:
            TwingateAuthError: If no tenant is stored for the session.
        """
        tenant = keyring.get_password(SERVICE_NAME, f"{session}:tenant")
        if not tenant:
            raise TwingateAuthError(
                f"Session '{session}' has no tenant configured. "
                "Run 'tgcli auth login' first."
            )
        staging = keyring.get_password(SERVICE_NAME, f"{session}:staging")
        if staging == "true":
            return f"https://{tenant}.stg.opstg.com/api/graphql/"
        return f"https://{tenant}.twingate.com/api/graphql/"

    @staticmethod
    def list_sessions() -> list[str]:
        """Return a list of all known session names."""
        index_raw = keyring.get_password(SERVICE_NAME, "__sessions__") or ""
        return [s for s in index_raw.split(",") if s]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add_to_index(session: str) -> None:
        sessions = SessionManager.list_sessions()
        if session not in sessions:
            sessions.append(session)
            keyring.set_password(SERVICE_NAME, "__sessions__", ",".join(sessions))

    @staticmethod
    def _remove_from_index(session: str) -> None:
        sessions = SessionManager.list_sessions()
        sessions = [s for s in sessions if s != session]
        keyring.set_password(SERVICE_NAME, "__sessions__", ",".join(sessions))
