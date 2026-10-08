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


def _entity(gateway_id="gw-1", ssh_ca=None):
    return _gateway(gateway_id, ssh_ca)["node"]


class _Mutation:
    def _invoke(self, args, key, payload):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = {"data": {key: payload}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "gateway", *args])
        return result, inst

    @staticmethod
    def _variables(inst):
        return inst.execute.call_args.args[1]


class TestGatewayShow(_Mutation):
    def test_show_flattens_fields(self):
        result, inst = self._invoke(["show", "-i", "gw-1"], "gateway", _entity())
        assert result.exit_code == 0
        assert self._variables(inst) == {"itemID": "gw-1"}
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["id"] == "gw-1" and row["x509CA.name"] == "X509 CA" and row["sshCA.name"] == ""

    def test_show_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "gateway", "show"]).exit_code != 0


class TestGatewayCreate(_Mutation):
    ARGS = ["create", "-n", "rn-1", "-a", "gw.example.com:443", "-x", "x-1"]

    def test_sends_required_fields_and_omits_ssh_ca(self):
        result, inst = self._invoke(self.ARGS, "gatewayCreate", {"ok": True, "error": None, "entity": _entity()})
        assert result.exit_code == 0
        assert self._variables(inst) == {"address": "gw.example.com:443", "remoteNetworkId": "rn-1", "x509CAId": "x-1"}

    def test_includes_ssh_ca_when_given(self):
        _, inst = self._invoke([*self.ARGS, "-s", "s-1"], "gatewayCreate", {"ok": True, "error": None, "entity": _entity()})
        assert self._variables(inst)["sshCAId"] == "s-1"

    def test_output_shows_created_gateway(self):
        result, _ = self._invoke(self.ARGS, "gatewayCreate", {"ok": True, "error": None, "entity": _entity("gw-9")})
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["ok"] == "True" and row["id"] == "gw-9" and row["remoteNetwork.name"] == "K8s"

    def test_reports_api_error(self):
        result, _ = self._invoke(self.ARGS, "gatewayCreate", {"ok": False, "error": "RemoteNetwork does not exist", "entity": None})
        assert "False" in result.output and "does not exist" in result.output

    @pytest.mark.parametrize("missing", ["-n", "-a", "-x"])
    def test_required_options(self, missing):
        args = list(self.ARGS)
        i = args.index(missing)
        del args[i : i + 2]
        assert runner.invoke(app, ["-s", SESSION, "gateway", *args]).exit_code != 0


class TestGatewayUpdate(_Mutation):
    def _ok(self):
        return {"ok": True, "error": None, "entity": _entity()}

    @pytest.mark.parametrize(
        "args,expected",
        [
            (["-a", "new:443"], {"address": "new:443"}),
            (["-n", "rn-2"], {"remoteNetworkId": "rn-2"}),
            (["-x", "x-2"], {"x509CAId": "x-2"}),
            (["-s", "s-2"], {"sshCAId": "s-2"}),
            (["-a", "a:1", "-s", "s-2"], {"address": "a:1", "sshCAId": "s-2"}),
        ],
    )
    def test_sends_only_the_options_given(self, args, expected):
        result, inst = self._invoke(["update", "-i", "gw-1", *args], "gatewayUpdate", self._ok())
        assert result.exit_code == 0
        assert self._variables(inst) == {"id": "gw-1", **expected}

    def test_requires_at_least_one_change_and_makes_no_api_call(self):
        result, inst = self._invoke(["update", "-i", "gw-1"], "gatewayUpdate", self._ok())
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_reports_api_error(self):
        result, _ = self._invoke(
            ["update", "-i", "gw-1", "-a", "x:1"], "gatewayUpdate", {"ok": False, "error": "Gateway does not exist", "entity": None}
        )
        assert "False" in result.output and "does not exist" in result.output

    def test_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "gateway", "update", "-a", "x:1"]).exit_code != 0


class TestGatewayDelete(_Mutation):
    def test_sends_id_and_reports_ok(self):
        result, inst = self._invoke(["delete", "-i", "gw-1"], "gatewayDelete", {"ok": True, "error": None})
        assert result.exit_code == 0
        query, variables = inst.execute.call_args.args
        assert "gatewayDelete(id: $id)" in query and variables == {"id": "gw-1"}
        assert result.output.split() == ["ok,error", "True,"]

    def test_reports_api_error(self):
        result, _ = self._invoke(["delete", "-i", "gw-1"], "gatewayDelete", {"ok": False, "error": "Gateway is in use"})
        assert "False" in result.output and "in use" in result.output

    def test_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "gateway", "delete"]).exit_code != 0
