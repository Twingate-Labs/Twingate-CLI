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

    def test_list_active_filter(self, mock_keyring):
        active_edge = {"node": {**SAMPLE_RESOURCE_EDGE["node"], "id": "res-active", "isActive": True}}
        inactive_edge = {"node": {**SAMPLE_RESOURCE_EDGE["node"], "id": "res-inactive", "isActive": False}}
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[active_edge, inactive_edge]]
            result = runner.invoke(app, ["-s", SESSION, "resource", "list", "-a", "false"])
        assert result.exit_code == 0
        assert "res-inactive" in result.output
        assert "res-active" not in result.output

    def _csv_rows(self, edges, args=()):
        import csv
        import io

        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [edges]
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "list", *args])
        assert result.exit_code == 0
        return result.output, list(csv.DictReader(io.StringIO(result.output)))

    @pytest.mark.parametrize(
        "typename,label",
        [
            ("NetworkResource", "NETWORK"),
            ("SSHResource", "SSH"),
            ("WebAppResource", "WEB_APP"),
            ("KubernetesResource", "KUBERNETES"),
            ("SomeFutureResource", "SomeFutureResource"),
        ],
    )
    def test_list_type_column_labels_each_resource_type(self, mock_keyring, typename, label):
        edge = {"node": {**SAMPLE_RESOURCE_EDGE["node"], "__typename": typename}}
        _, rows = self._csv_rows([edge])
        assert rows[0]["type"] == label

    ORIGINAL_COLUMNS = [
        "id", "name", "isActive", "remoteNetwork.id", "address.type", "address.value", "access.edges",
        "securityPolicy.id", "alias", "isVisible", "isBrowserShortcutEnabled", "routingMode", "tags", "type",
    ]
    DETAIL_COLUMNS = [
        "accessPolicy.mode", "accessPolicy.durationSeconds", "gateway.id", "gateway.address", "clusterRef",
        "upstream.port", "upstream.tlsMode", "downstream.port", "downstream.tlsMode",
        "approvalMode", "approverGroups", "approverGroupNames",
    ]

    def test_list_default_has_only_the_original_columns_plus_type(self, mock_keyring):
        edge = {"node": {**SAMPLE_RESOURCE_EDGE["node"], "__typename": "SSHResource"}}
        output, _ = self._csv_rows([edge])
        assert output.splitlines()[0].split(",") == self.ORIGINAL_COLUMNS

    def test_list_detail_appends_the_extra_columns_after_the_original_ones(self, mock_keyring):
        edge = {"node": {**SAMPLE_RESOURCE_EDGE["node"], "__typename": "SSHResource"}}
        output, _ = self._csv_rows([edge], ["--detail"])
        assert output.splitlines()[0].split(",") == self.ORIGINAL_COLUMNS + self.DETAIL_COLUMNS

    def test_list_short_flag_d_is_detail(self, mock_keyring):
        edge = {"node": {**SAMPLE_RESOURCE_EDGE["node"], "__typename": "SSHResource"}}
        output, _ = self._csv_rows([edge], ["-d"])
        assert output.splitlines()[0].split(",")[-1] == "approverGroupNames"

    def _sent_query(self, args):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[SAMPLE_RESOURCE_EDGE]]
            runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "list", *args])
            return MockClient.return_value.paginate.call_args.args[0]

    def test_list_default_query_leaves_out_the_expensive_fields(self, mock_keyring):
        query = self._sent_query([])
        for field in ("approverGroups", "gateway", "accessPolicy", "upstream", "clusterRef"):
            assert field not in query, field
        assert "__typename" in query and "routingMode" in query

    def test_list_detail_query_asks_for_them(self, mock_keyring):
        query = self._sent_query(["--detail"])
        for field in ("approverGroups", "gateway", "accessPolicy", "upstream", "clusterRef"):
            assert field in query, field

    def test_mappings_keep_using_the_lean_list_query(self, mock_keyring):
        from tgcli.queries import resources as rq

        assert "approverGroups" not in rq.LIST_RESOURCES and "approverGroups" in rq.LIST_RESOURCES_DETAIL
        import inspect

        from tgcli.commands import mappings

        source = inspect.getsource(mappings)
        assert "resq.LIST_RESOURCES," in source and "LIST_RESOURCES_DETAIL" not in source

    def test_list_reports_type_specific_fields_per_row(self, mock_keyring):
        node = SAMPLE_RESOURCE_EDGE["node"]
        gateway = {"id": "gw-1", "address": "gw.example:443"}
        policy = {"mode": "AUTO_LOCK", "durationSeconds": 86400}
        edges = [
            {"node": {**node, "id": "net", "__typename": "NetworkResource", "accessPolicy": {"mode": "MANUAL", "durationSeconds": None},
                      "approvalMode": "AUTOMATIC", "approverGroups": {"edges": [{"node": {"id": "g-1", "name": "Ops, EMEA"}}, {"node": {"id": "g-2", "name": "DBAs"}}]}}},
            {"node": {**node, "id": "k8s", "__typename": "KubernetesResource", "accessPolicy": policy, "approvalMode": "MANUAL",
                      "approverGroups": {"edges": []}, "gateway": gateway, "clusterRef": "prod",
                      "upstream": {"port": 6443}, "downstream": {"port": 443}}},
            {"node": {**node, "id": "web", "__typename": "WebAppResource", "accessPolicy": policy, "approvalMode": "MANUAL",
                      "approverGroups": {"edges": [{"node": {"id": "g-3", "name": "Web"}}]}, "gateway": gateway,
                      "upstream": {"port": 8443, "tlsMode": "VERIFY_FULL"}, "downstream": {"port": 443, "tlsMode": "TLS13"}}},
        ]
        _, rows = self._csv_rows(edges, ["--detail"])
        net, k8s, web = rows
        assert (net["accessPolicy.mode"], net["accessPolicy.durationSeconds"], net["gateway.id"], net["upstream.port"]) == ("MANUAL", "", "", "")
        assert (net["approvalMode"], net["approverGroups"], net["approverGroupNames"]) == ("AUTOMATIC", "['g-1', 'g-2']", "['Ops, EMEA', 'DBAs']")
        assert (k8s["gateway.id"], k8s["gateway.address"], k8s["clusterRef"], k8s["upstream.port"], k8s["downstream.port"]) == ("gw-1", "gw.example:443", "prod", "6443", "443")
        assert (k8s["accessPolicy.durationSeconds"], k8s["approverGroups"], k8s["approverGroupNames"]) == ("86400", "[]", "[]")
        assert (web["upstream.tlsMode"], web["downstream.tlsMode"], web["approverGroupNames"]) == ("VERIFY_FULL", "TLS13", "['Web']")

    def test_list_approver_names_stay_aligned_with_rows_after_active_filter(self, mock_keyring):
        node = SAMPLE_RESOURCE_EDGE["node"]
        edges = [
            {"node": {**node, "id": "a", "isActive": True, "__typename": "NetworkResource", "approvalMode": "MANUAL",
                      "approverGroups": {"edges": [{"node": {"id": "g-a", "name": "A-team"}}]}}},
            {"node": {**node, "id": "b", "isActive": False, "__typename": "NetworkResource", "approvalMode": "MANUAL",
                      "approverGroups": {"edges": [{"node": {"id": "g-b", "name": "B-team"}}]}}},
        ]
        _, rows = self._csv_rows(edges, ["-a", "false", "--detail"])
        assert [(r["id"], r["approverGroups"], r["approverGroupNames"]) for r in rows] == [("b", "['g-b']", "['B-team']")]

    def test_list_handles_a_null_node_without_misaligning_later_rows(self, mock_keyring):
        node = {**SAMPLE_RESOURCE_EDGE["node"], "id": "ok", "__typename": "NetworkResource", "approvalMode": "MANUAL",
                "approverGroups": {"edges": [{"node": {"id": "g", "name": "G"}}]}}
        _, rows = self._csv_rows([{"node": None}, {"node": node}], ["--detail"])
        assert rows[0]["id"] == "" and rows[0]["approverGroupNames"] == ""
        assert rows[1]["id"] == "ok" and rows[1]["approverGroupNames"] == "['G']"

    def test_list_mixed_types_and_active_filter(self, mock_keyring):
        node = SAMPLE_RESOURCE_EDGE["node"]
        edges = [
            {"node": {**node, "id": "n", "isActive": True, "__typename": "NetworkResource"}},
            {"node": {**node, "id": "k", "isActive": False, "__typename": "KubernetesResource"}},
        ]
        _, rows = self._csv_rows(edges)
        assert [(r["id"], r["type"]) for r in rows] == [("n", "NETWORK"), ("k", "KUBERNETES")]
        _, inactive = self._csv_rows(edges, ["-a", "false"])
        assert [(r["id"], r["type"]) for r in inactive] == [("k", "KUBERNETES")]

    def test_list_invalid_active_exits_nonzero(self, mock_keyring):
        result = runner.invoke(app, ["-s", SESSION, "resource", "list", "-a", "maybe"])
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


    def _show_rows(self, resource):
        import csv
        import io

        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {"data": {"resource": resource}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "show", "-i", "res-1"])
        assert result.exit_code == 0
        return result.output, list(csv.DictReader(io.StringIO(result.output)))

    @pytest.mark.parametrize(
        "typename,label",
        [
            ("NetworkResource", "NETWORK"),
            ("SSHResource", "SSH"),
            ("WebAppResource", "WEB_APP"),
            ("KubernetesResource", "KUBERNETES"),
            ("SomeFutureResource", "SomeFutureResource"),
        ],
    )
    def test_show_type_column_labels_each_resource_type(self, mock_keyring, typename, label):
        _, rows = self._show_rows({**SAMPLE_RESOURCE_EDGE["node"], "__typename": typename})
        assert rows[0]["type"] == label and rows[0]["id"] == "res-1"

    _GATEWAY = {"id": "gw-1", "address": "gw.example:443"}
    _POLICY = {"mode": "AUTO_LOCK", "durationSeconds": 7776000}

    @pytest.mark.parametrize(
        "typename,extra,expected",
        [
            (
                "KubernetesResource",
                {"gateway": _GATEWAY, "clusterRef": "prod", "upstream": {"port": 6443}, "downstream": {"port": 443}},
                {"gateway.id": "gw-1", "gateway.address": "gw.example:443", "clusterRef": "prod",
                 "upstream.port": "6443", "upstream.tlsMode": "", "downstream.port": "443", "downstream.tlsMode": ""},
            ),
            (
                "SSHResource",
                {"gateway": _GATEWAY, "upstream": {"port": 22}, "downstream": {"port": 2222}},
                {"gateway.id": "gw-1", "clusterRef": "", "upstream.port": "22", "downstream.port": "2222", "upstream.tlsMode": ""},
            ),
            (
                "WebAppResource",
                {"gateway": _GATEWAY, "upstream": {"port": 8443, "tlsMode": "VERIFY_FULL"}, "downstream": {"port": 443, "tlsMode": "TLS13"}},
                {"gateway.id": "gw-1", "upstream.port": "8443", "upstream.tlsMode": "VERIFY_FULL",
                 "downstream.port": "443", "downstream.tlsMode": "TLS13"},
            ),
            (
                "NetworkResource",
                {},
                {"gateway.id": "", "gateway.address": "", "clusterRef": "", "upstream.port": "", "downstream.port": ""},
            ),
        ],
    )
    def test_show_gateway_ports_and_access_policy_per_type(self, mock_keyring, typename, extra, expected):
        resource = {**SAMPLE_RESOURCE_EDGE["node"], "__typename": typename, "accessPolicy": self._POLICY, **extra}
        _, rows = self._show_rows(resource)
        row = rows[0]
        assert row["accessPolicy.mode"] == "AUTO_LOCK" and row["accessPolicy.durationSeconds"] == "7776000"
        for column, value in expected.items():
            assert row[column] == value, column

    def test_show_access_policy_without_duration_is_blank(self, mock_keyring):
        resource = {**SAMPLE_RESOURCE_EDGE["node"], "__typename": "NetworkResource", "accessPolicy": {"mode": "MANUAL", "durationSeconds": None}}
        _, rows = self._show_rows(resource)
        assert rows[0]["accessPolicy.mode"] == "MANUAL" and rows[0]["accessPolicy.durationSeconds"] == ""

    def test_show_original_columns_keep_their_positions(self, mock_keyring):
        output, _ = self._show_rows({**SAMPLE_RESOURCE_EDGE["node"], "__typename": "SSHResource"})
        header = output.splitlines()[0].split(",")
        assert header[:13] == [
            "id", "name", "isActive", "remoteNetwork.id", "address.type", "address.value", "protocols.allowIcmp",
            "protocols.tcp.policy", "protocols.udp.policy", "isVisible", "isBrowserShortcutEnabled", "routingMode", "type",
        ]

    def test_show_reports_tcp_and_udp_protocol_policies(self, mock_keyring):
        resource = {
            **SAMPLE_RESOURCE_EDGE["node"],
            "__typename": "NetworkResource",
            "protocols": {
                "allowIcmp": False,
                "tcp": {"policy": "RESTRICTED", "ports": [{"start": 22, "end": 22}]},
                "udp": {"policy": "ALLOW_ALL", "ports": []},
            },
        }
        _, rows = self._show_rows(resource)
        assert rows[0]["protocols.allowIcmp"] == "False"
        assert rows[0]["protocols.tcp.policy"] == "RESTRICTED"
        assert rows[0]["protocols.udp.policy"] == "ALLOW_ALL"

    @pytest.mark.parametrize("typename", ["NetworkResource", "SSHResource", "WebAppResource", "KubernetesResource"])
    def test_show_approval_mode_and_approver_groups_for_every_type(self, mock_keyring, typename):
        resource = {
            **SAMPLE_RESOURCE_EDGE["node"],
            "__typename": typename,
            "approvalMode": "AUTOMATIC",
            "approverGroups": {"edges": [{"node": {"id": "g-1", "name": "Admins"}}, {"node": {"id": "g-2", "name": "Ops"}}]},
        }
        _, rows = self._show_rows(resource)
        assert rows[0]["approvalMode"] == "AUTOMATIC"
        assert rows[0]["approverGroups"] == "['g-1', 'g-2']"
        assert rows[0]["approverGroupNames"] == "['Admins', 'Ops']"

    def test_show_without_approver_groups_gives_empty_list(self, mock_keyring):
        resource = {
            **SAMPLE_RESOURCE_EDGE["node"], "__typename": "NetworkResource",
            "approvalMode": "MANUAL", "approverGroups": {"edges": []},
        }
        _, rows = self._show_rows(resource)
        assert rows[0]["approvalMode"] == "MANUAL" and rows[0]["approverGroups"] == "[]"
        assert rows[0]["approverGroupNames"] == "[]"

    def test_show_approver_group_names_stay_aligned_with_ids_and_survive_commas(self, mock_keyring):
        resource = {
            **SAMPLE_RESOURCE_EDGE["node"], "__typename": "NetworkResource", "approvalMode": "MANUAL",
            "approverGroups": {"edges": [{"node": {"id": "g-1", "name": "Ops, EMEA"}}, {"node": {"id": "g-2", "name": "DBAs"}}]},
        }
        _, rows = self._show_rows(resource)
        assert rows[0]["approverGroups"] == "['g-1', 'g-2']"
        assert rows[0]["approverGroupNames"] == "['Ops, EMEA', 'DBAs']"

    def test_show_approval_columns_are_appended_after_the_existing_ones(self, mock_keyring):
        resource = {**SAMPLE_RESOURCE_EDGE["node"], "__typename": "SSHResource", "approvalMode": "MANUAL", "approverGroups": {"edges": []}}
        output, _ = self._show_rows(resource)
        header = output.splitlines()[0].split(",")
        assert header[:13][-1] == "type" and header[-3:] == ["approvalMode", "approverGroups", "approverGroupNames"]

    def test_show_unknown_id_prints_blank_row_without_crashing(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {"data": {"resource": None}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", "show", "-i", "res-1"])
        assert result.exit_code == 0
        import csv
        import io

        (row,) = list(csv.DictReader(io.StringIO(result.output)))
        assert row["approverGroupNames"] == "" and row["id"] == ""

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

    def test_create_bypass_twingate(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = _mutation_ok(
                "resourceCreate",
                {"id": "res-new", "name": "New Res", "isVisible": True, "routingMode": "BYPASS_TWINGATE", "securityPolicy": None},
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
                    "-m", "bypass_twingate",
                ],
            )
            call_kwargs = MockClient.return_value.execute.call_args
        assert result.exit_code == 0
        assert call_kwargs.args[1]["routingMode"] == "BYPASS_TWINGATE"

    def test_create_invalid_routing_mode_exits_nonzero(self, mock_keyring):
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
                "-m", "sideways",
            ],
        )
        assert result.exit_code != 0


class TestResourceRouting:
    def test_routing_bypass(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = _mutation_ok(
                "resourceUpdate", {"id": "res-1", "name": "R", "routingMode": "BYPASS_TWINGATE"}
            )
            result = runner.invoke(
                app, ["-s", SESSION, "resource", "routing", "-i", "res-1", "-m", "bypass_twingate"]
            )
            call_kwargs = MockClient.return_value.execute.call_args
        assert result.exit_code == 0
        assert call_kwargs.args[1]["routingMode"] == "BYPASS_TWINGATE"

    def test_routing_invalid_mode_exits_nonzero(self, mock_keyring):
        result = runner.invoke(
            app, ["-s", SESSION, "resource", "routing", "-i", "res-1", "-m", "sideways"]
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
