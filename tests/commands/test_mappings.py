"""Tests for mapping/analytics commands."""

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


def _connector_edge(cid, rn_id, state):
    return {"node": {"id": cid, "name": cid, "state": state, "remoteNetwork": {"id": rn_id, "name": "RN"}}}


def _resource_edge(rid, rn_id, is_active=True):
    return {
        "node": {
            "id": rid,
            "name": rid,
            "isActive": is_active,
            "remoteNetwork": {"id": rn_id, "name": "RN"},
        }
    }


class TestResourceConnectivity:
    def test_flags_resource_with_no_live_connector(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = [
                [[_connector_edge("conn-1", "rn-dead", "DEAD_NO_HEARTBEAT")]],
                [[_resource_edge("res-offline", "rn-dead"), _resource_edge("res-online", "rn-live")]],
            ]
            result = runner.invoke(app, ["-s", SESSION, "mappings", "resource-connectivity"])
        assert result.exit_code == 0
        assert "res-offline" in result.output
        assert "\"isReachable\": false" in result.output

    def test_offline_only_filters_reachable_resources(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = [
                [[_connector_edge("conn-1", "rn-live", "ALIVE")]],
                [[_resource_edge("res-offline", "rn-dead"), _resource_edge("res-online", "rn-live")]],
            ]
            result = runner.invoke(
                app, ["-s", SESSION, "mappings", "resource-connectivity", "--offline-only"]
            )
        assert result.exit_code == 0
        assert "res-offline" in result.output
        assert "res-online" not in result.output

    def test_connector_api_error_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = TwingateAPIError("Fail")
            result = runner.invoke(app, ["-s", SESSION, "mappings", "resource-connectivity"])
        assert result.exit_code != 0
