"""Shared fixtures for the tgcli test suite."""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """A Typer test runner."""
    return CliRunner()


# ---------------------------------------------------------------------------
# Keyring mock — prevents touching the real OS keychain during tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_keyring() -> Generator[dict, None, None]:
    """Replace keyring with an in-memory dict store for all tests."""
    store: dict[tuple[str, str], str] = {}

    def _set(service: str, key: str, value: str) -> None:
        store[(service, key)] = value

    def _get(service: str, key: str) -> str | None:
        return store.get((service, key))

    def _delete(service: str, key: str) -> None:
        import keyring.errors  # noqa: PLC0415

        if (service, key) not in store:
            raise keyring.errors.PasswordDeleteError("not found")
        del store[(service, key)]

    with (
        patch("keyring.set_password", side_effect=_set),
        patch("keyring.get_password", side_effect=_get),
        patch("keyring.delete_password", side_effect=_delete),
    ):
        yield store


# ---------------------------------------------------------------------------
# Sample API response fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def resource_edge() -> dict:
    return {
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
            "protocols": {
                "allowIcmp": True,
                "tcp": {"policy": "ALLOW_ALL", "ports": []},
                "udp": {"policy": "ALLOW_ALL", "ports": []},
            },
        }
    }


@pytest.fixture
def device_edge() -> dict:
    return {
        "node": {
            "id": "dev-1",
            "name": "MacBook Pro",
            "isTrusted": True,
            "osName": "macOS",
            "deviceType": "LAPTOP",
            "lastFailedLoginAt": None,
            "lastSuccessfulLoginAt": "2024-01-01T00:00:00Z",
            "lastConnectedAt": "2024-01-01T00:00:00Z",
            "osVersion": "14.0",
            "hardwareModel": "MacBookPro18,1",
            "hostname": "macbook.local",
            "username": "alice",
            "serialNumber": "SN123",
            "user": {
                "firstName": "Alice",
                "lastName": "Smith",
                "email": "alice@example.com",
            },
            "activeState": "ACTIVE",
            "clientVersion": "2024.1",
            "manufacturerName": "Apple",
        }
    }


@pytest.fixture
def user_edge() -> dict:
    return {
        "node": {
            "id": "usr-1",
            "email": "bob@example.com",
            "firstName": "Bob",
            "lastName": "Jones",
            "state": "ACTIVE",
            "role": "MEMBER",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "groups": {"edges": [{"node": {"id": "grp-1"}}]},
        }
    }


@pytest.fixture
def paginated_response_factory():
    """Factory: given a list of edges, return a paginated API response dict."""

    def _make(data_key: str, edges: list[dict], has_next: bool = False) -> dict:
        return {
            "data": {
                data_key: {
                    "edges": edges,
                    "pageInfo": {
                        "hasNextPage": has_next,
                        "endCursor": "cursor-abc" if has_next else None,
                    },
                }
            }
        }

    return _make
