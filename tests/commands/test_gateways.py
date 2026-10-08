"""Tests for gateway commands."""

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


def _gateway(gateway_id, ssh_ca=None):
    return {
        "node": {
            "id": gateway_id,
            "address": f"{gateway_id}.svc:443",
            "remoteNetwork": {"id": "rn-1", "name": "K8s"},
            "x509CA": {"id": "x-1", "name": "X509 CA", "fingerprint": "AA:BB"},
            "sshCA": ssh_ca,
        }
    }


class TestGatewayList:
    def _invoke(self, args, pages):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = pages
            return runner.invoke(app, ["-s", SESSION, *args])

    def test_csv_flattens_networks_and_cas(self):
        ssh = {"id": "s-1", "name": "Vault SSH CA", "fingerprint": "SHA256:xyz"}
        result = self._invoke(["-f", "csv", "gateway", "list"], [[_gateway("gw-1", ssh)]])
        assert result.exit_code == 0
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["id"] == "gw-1" and row["remoteNetwork.name"] == "K8s"
        assert row["x509CA.fingerprint"] == "AA:BB"
        assert row["sshCA.name"] == "Vault SSH CA" and row["sshCA.fingerprint"] == "SHA256:xyz"

    def test_missing_ssh_ca_gives_empty_columns(self):
        result = self._invoke(["-f", "csv", "gateway", "list"], [[_gateway("gw-1")]])
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["sshCA.name"] == "" and row["sshCA.fingerprint"] == ""

    def test_spans_pages(self):
        result = self._invoke(["-f", "csv", "gateway", "list"], [[_gateway("gw-1")], [_gateway("gw-2")]])
        assert [r["id"] for r in csv.DictReader(io.StringIO(result.output))] == ["gw-1", "gw-2"]

    def test_empty_tenant_prints_header_only(self):
        result = self._invoke(["-f", "csv", "gateway", "list"], [[]])
        assert result.exit_code == 0
        assert result.output.strip().startswith("id,address,")
        assert list(csv.DictReader(io.StringIO(result.output))) == []

    def test_auth_error_exits_nonzero(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, "gateway", "list"])
        assert result.exit_code != 0
