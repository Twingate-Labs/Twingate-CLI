"""Tests for ssh-resource, webapp-resource and k8s-resource commands."""

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

REQUIRED_CREATE = {
    "ssh-resource": ["-n", "R", "-a", "h.example", "-r", "rn-1", "-w", "gw-1"],
    "webapp-resource": ["-n", "R", "-a", "h.example", "-r", "rn-1", "-w", "gw-1", "--upstream-port", "443", "--downstream-port", "443"],
    "k8s-resource": ["-n", "R", "-a", "h.example", "-r", "rn-1"],
}
MUTATION_KEYS = {
    "ssh-resource": ("sshResourceCreate", "sshResourceUpdate"),
    "webapp-resource": ("webAppResourceCreate", "webAppResourceUpdate"),
    "k8s-resource": ("kubernetesResourceCreate", "kubernetesResourceUpdate"),
}
BASE_VARS = {
    "ssh-resource": {"name": "R", "address": "h.example", "remoteNetworkId": "rn-1", "gatewayId": "gw-1"},
    "webapp-resource": {
        "name": "R", "address": "h.example", "remoteNetworkId": "rn-1", "gatewayId": "gw-1",
        "upstream": {"port": 443}, "downstream": {"port": 443},
    },
    "k8s-resource": {"name": "R", "address": "h.example", "remoteNetworkId": "rn-1"},
}
TYPES = list(REQUIRED_CREATE)


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def _invoke(group, command, args, payload=None):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        key = MUTATION_KEYS[group][0 if command == "create" else 1]
        inst.execute.return_value = {"data": {key: payload or {"ok": True, "error": None, "entity": _entity()}}}
        result = runner.invoke(app, ["-s", SESSION, "-f", "csv", group, command, *args])
    return result, inst


def _entity(**extra):
    return {
        "id": "res-1", "name": "R", "isActive": True, "isVisible": True,
        "address": {"value": "h.example"}, "remoteNetwork": {"id": "rn-1", "name": "Net"},
        "gateway": {"id": "gw-1"}, **extra,
    }


def _vars(inst):
    return inst.execute.call_args.args[1]


@pytest.mark.parametrize("group", TYPES)
class TestCreateCommon:
    def test_sends_required_and_omits_every_optional(self, group):
        result, inst = _invoke(group, "create", REQUIRED_CREATE[group])
        assert result.exit_code == 0
        assert _vars(inst) == BASE_VARS[group]

    def test_optional_common_fields(self, group):
        args = [*REQUIRED_CREATE[group], "-l", "a.local", "-p", "pol-1", "-g", "g1, g2", "-v", "false"]
        _, inst = _invoke(group, "create", args)
        assert _vars(inst) == {
            **BASE_VARS[group], "alias": "a.local", "securityPolicyId": "pol-1", "groupIds": ["g1", "g2"], "isVisible": False,
        }

    def test_reports_api_error(self, group):
        bad = {"ok": False, "error": "RemoteNetwork does not exist", "entity": None}
        result, _ = _invoke(group, "create", REQUIRED_CREATE[group], bad)
        assert "False" in result.output and "does not exist" in result.output

    def test_invalid_bool_rejected_before_any_api_call(self, group):
        result, inst = _invoke(group, "create", [*REQUIRED_CREATE[group], "-v", "maybe"])
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    @pytest.mark.parametrize("port", ["0", "70000"])
    def test_port_range_enforced(self, group, port):
        result, inst = _invoke(group, "create", [*REQUIRED_CREATE[group], "--upstream-port", port])
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_requires_name_address_and_network(self, group):
        for flag in ("-n", "-a", "-r"):
            args = list(REQUIRED_CREATE[group])
            i = args.index(flag)
            del args[i : i + 2]
            assert runner.invoke(app, ["-s", SESSION, group, "create", *args]).exit_code != 0

    def test_auth_error_exits_nonzero(self, group):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, group, "create", *REQUIRED_CREATE[group]])
        assert result.exit_code != 0


@pytest.mark.parametrize("group", TYPES)
class TestUpdateCommon:
    @pytest.mark.parametrize(
        "args,expected",
        [
            (["-n", "New"], {"name": "New"}),
            (["-a", "x.example"], {"address": "x.example"}),
            (["-r", "rn-2"], {"remoteNetworkId": "rn-2"}),
            (["-w", "gw-2"], {"gatewayId": "gw-2"}),
            (["-l", "x.local"], {"alias": "x.local"}),
            (["-p", "pol-2"], {"securityPolicyId": "pol-2"}),
            (["-v", "true"], {"isVisible": True}),
            (["--active", "false"], {"isActive": False}),
            (["--add-groups", "g1,g2"], {"addedGroupIds": ["g1", "g2"]}),
            (["--remove-groups", "g3"], {"removedGroupIds": ["g3"]}),
            (["--upstream-port", "8080"], {"upstream": {"port": 8080}}),
        ],
    )
    def test_sends_only_what_was_given(self, group, args, expected):
        if group == "webapp-resource" and "--upstream-port" in args:
            expected = {"upstream": {"port": 8080}}
        result, inst = _invoke(group, "update", ["-i", "res-1", *args])
        assert result.exit_code == 0
        assert _vars(inst) == {"id": "res-1", **expected}

    def test_requires_a_change_and_makes_no_api_call(self, group):
        result, inst = _invoke(group, "update", ["-i", "res-1"])
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_requires_id(self, group):
        assert runner.invoke(app, ["-s", SESSION, group, "update", "-n", "x"]).exit_code != 0

    def test_invalid_bool_rejected(self, group):
        for flag in ("-v", "--active"):
            result, inst = _invoke(group, "update", ["-i", "res-1", flag, "maybe"])
            assert result.exit_code != 0
            inst.execute.assert_not_called()

    def test_reports_api_error(self, group):
        bad = {"ok": False, "error": "Resource does not exist", "entity": None}
        result, _ = _invoke(group, "update", ["-i", "res-1", "-n", "x"], bad)
        assert "False" in result.output and "does not exist" in result.output


class TestSSH:
    def test_ports_and_output(self):
        entity = _entity(upstream={"port": 22}, downstream={"port": 2222})
        result, inst = _invoke(
            "ssh-resource", "create", [*REQUIRED_CREATE["ssh-resource"], "--upstream-port", "22", "--downstream-port", "2222"],
            {"ok": True, "error": None, "entity": entity},
        )
        assert _vars(inst)["upstream"] == {"port": 22} and _vars(inst)["downstream"] == {"port": 2222}
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert (row["ok"], row["id"], row["address.value"], row["remoteNetwork.name"], row["gateway.id"]) == ("True", "res-1", "h.example", "Net", "gw-1")
        assert (row["upstream.port"], row["downstream.port"]) == ("22", "2222")

    def test_gateway_is_required_on_create(self):
        args = [a for a in REQUIRED_CREATE["ssh-resource"] if a not in ("-w", "gw-1")]
        assert runner.invoke(app, ["-s", SESSION, "ssh-resource", "create", *args]).exit_code != 0


class TestWebApp:
    def test_tls_modes_are_case_insensitive_and_sent(self):
        args = [*REQUIRED_CREATE["webapp-resource"], "--upstream-tls", "verify_ca", "--downstream-tls", "tls13"]
        result, inst = _invoke("webapp-resource", "create", args)
        assert result.exit_code == 0
        assert _vars(inst)["upstream"] == {"port": 443, "tlsMode": "VERIFY_CA"}
        assert _vars(inst)["downstream"] == {"port": 443, "tlsMode": "TLS13"}

    @pytest.mark.parametrize("flag,value", [("--upstream-tls", "TLS13"), ("--downstream-tls", "VERIFY_FULL"), ("--upstream-tls", "bogus")])
    def test_tls_mode_must_match_its_side(self, flag, value):
        result, inst = _invoke("webapp-resource", "create", [*REQUIRED_CREATE["webapp-resource"], flag, value])
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    @pytest.mark.parametrize("flag", ["--upstream-tls", "--downstream-tls"])
    def test_update_tls_without_port_rejected(self, flag):
        result, inst = _invoke("webapp-resource", "update", ["-i", "res-1", flag, "NONE"])
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_update_tls_with_port(self):
        _, inst = _invoke("webapp-resource", "update", ["-i", "res-1", "--downstream-port", "8443", "--downstream-tls", "none"])
        assert _vars(inst) == {"id": "res-1", "downstream": {"port": 8443, "tlsMode": "NONE"}}

    def test_headers_split_on_first_equals(self):
        args = [*REQUIRED_CREATE["webapp-resource"], "--header", "X-A=b=c", "--header", "X-Empty="]
        _, inst = _invoke("webapp-resource", "create", args)
        assert _vars(inst)["requestHeaderRewrites"] == [{"key": "X-A", "value": "b=c"}, {"key": "X-Empty", "value": ""}]

    @pytest.mark.parametrize("bad", ["novalue", "=v", " =v"])
    def test_malformed_header_rejected(self, bad):
        result, inst = _invoke("webapp-resource", "create", [*REQUIRED_CREATE["webapp-resource"], "--header", bad])
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_update_headers_replace_list(self):
        _, inst = _invoke("webapp-resource", "update", ["-i", "res-1", "--header", "X-A=1"])
        assert _vars(inst) == {"id": "res-1", "requestHeaderRewrites": [{"key": "X-A", "value": "1"}]}

    @pytest.mark.parametrize("missing", ["--upstream-port", "--downstream-port"])
    def test_ports_are_required_on_create(self, missing):
        args = list(REQUIRED_CREATE["webapp-resource"])
        i = args.index(missing)
        del args[i : i + 2]
        assert runner.invoke(app, ["-s", SESSION, "webapp-resource", "create", *args]).exit_code != 0

    def test_output_includes_tls_modes(self):
        entity = _entity(upstream={"port": 443, "tlsMode": "VERIFY_FULL"}, downstream={"port": 443, "tlsMode": "TLS13"})
        result, _ = _invoke("webapp-resource", "create", REQUIRED_CREATE["webapp-resource"], {"ok": True, "error": None, "entity": entity})
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert (row["upstream.tlsMode"], row["downstream.tlsMode"]) == ("VERIFY_FULL", "TLS13")


class TestKubernetes:
    def test_cluster_ref_gateway_and_ports(self):
        args = [*REQUIRED_CREATE["k8s-resource"], "--clusterref", "prod", "-w", "gw-1", "--upstream-port", "6443", "--downstream-port", "443"]
        _, inst = _invoke("k8s-resource", "create", args)
        assert _vars(inst) == {
            **BASE_VARS["k8s-resource"], "gatewayId": "gw-1", "clusterRef": "prod",
            "upstream": {"port": 6443}, "downstream": {"port": 443},
        }

    def test_gateway_is_optional_on_create(self):
        result, inst = _invoke("k8s-resource", "create", REQUIRED_CREATE["k8s-resource"])
        assert result.exit_code == 0 and "gatewayId" not in _vars(inst)

    def test_update_cluster_ref(self):
        _, inst = _invoke("k8s-resource", "update", ["-i", "res-1", "--clusterref", "dr"])
        assert _vars(inst) == {"id": "res-1", "clusterRef": "dr"}

    def test_output_includes_cluster_ref(self):
        entity = _entity(clusterRef="prod", upstream={"port": 6443}, downstream={"port": 443})
        result, _ = _invoke("k8s-resource", "create", REQUIRED_CREATE["k8s-resource"], {"ok": True, "error": None, "entity": entity})
        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["clusterRef"] == "prod" and row["upstream.port"] == "6443"
