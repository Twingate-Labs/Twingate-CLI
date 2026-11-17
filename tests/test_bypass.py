"""The planner behind `tgcli resource bypass`: what has to go before a Resource can bypass Twingate."""

from __future__ import annotations

import pytest

from tgcli import bypass as bp

OPEN = {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}


def node(**changes):
    base = {"__typename": "NetworkResource", "id": "res-1", "name": "Office", "routingMode": "THROUGH_TWINGATE", "securityPolicy": None, "protocols": OPEN}
    base.update(changes)
    return base


class TestWhatIsCleared:
    def test_a_resource_with_nothing_in_the_way_only_changes_its_routing_mode(self):
        row = bp.plan_resource(node(), "res-1")
        assert row.status == bp.WOULD_CONVERT and row.detail == "only the routing mode changes"
        assert row.variables == {"id": "res-1"}

    def test_a_security_policy_is_cleared_with_an_explicit_null(self):
        row = bp.plan_resource(node(securityPolicy={"id": "pol-1", "name": "Strict"}), "res-1")
        assert row.variables == {"id": "res-1", "securityPolicyId": None}
        assert "'Strict' is removed" in row.detail and "ports" not in row.detail
        assert (row.securityPolicyId, row.securityPolicyName) == ("pol-1", "Strict")

    @pytest.mark.parametrize(
        "protocols,text",
        [
            ({**OPEN, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}, {"start": 8000, "end": 8100}]}}, "TCP is limited to 443,8000-8100"),
            ({**OPEN, "udp": {"policy": "RESTRICTED", "ports": [{"start": 53, "end": 53}]}}, "UDP is limited to 53"),
            ({**OPEN, "udp": {"policy": "RESTRICTED", "ports": []}}, "UDP is restricted (no ports)"),
            ({**OPEN, "allowIcmp": False}, "ICMP is blocked"),
        ],
    )
    def test_any_port_or_icmp_restriction_opens_everything(self, protocols, text):
        row = bp.plan_resource(node(protocols=protocols), "res-1")
        assert text in row.detail and "all ports and ICMP are opened" in row.detail
        assert row.variables == {"id": "res-1", "protocols": bp.OPEN_PROTOCOLS}

    def test_policy_and_restrictions_go_in_the_same_update(self):
        protocols = {"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 22, "end": 22}]}, "udp": OPEN["udp"]}
        row = bp.plan_resource(node(securityPolicy={"id": "pol-1", "name": "Strict"}, protocols=protocols), "res-1")
        assert row.variables == {"id": "res-1", "securityPolicyId": None, "protocols": bp.OPEN_PROTOCOLS}

    def test_the_row_keeps_what_the_resource_had_before(self):
        protocols = {"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 80, "end": 80}, {"start": 443, "end": 443}]}, "udp": {"policy": "RESTRICTED", "ports": []}}
        row = bp.plan_resource(node(protocols=protocols), "res-1").as_dict()
        assert (row["allowIcmp"], row["tcpPolicy"], row["tcpPorts"], row["udpPolicy"], row["udpPorts"]) == (False, "RESTRICTED", "80,443", "RESTRICTED", "")
        assert list(row) == list(bp.COLUMNS)

    def test_the_open_protocols_are_never_shared_between_plans(self):
        restricted = node(protocols={**OPEN, "allowIcmp": False})
        first = bp.plan_resource(restricted, "res-1").variables["protocols"]
        first["allowIcmp"] = False
        assert bp.plan_resource(restricted, "res-1").variables["protocols"] == OPEN


class TestWhatIsNotConverted:
    def test_a_resource_that_already_bypasses_is_reported_and_left_alone(self):
        row = bp.plan_resource(node(routingMode="BYPASS_TWINGATE"), "res-1")
        assert row.status == bp.ALREADY and row.variables is None

    @pytest.mark.parametrize("typename", ["SSHResource", "WebAppResource", "KubernetesResource"])
    def test_a_resource_with_no_routing_mode_is_blocked_with_its_type_named(self, typename):
        raw = node(__typename=typename)
        del raw["routingMode"]
        row = bp.plan_resource(raw, "res-1")
        assert row.status == bp.BLOCKED and typename in row.detail and row.variables is None

    def test_an_id_with_no_resource_is_blocked_and_keeps_the_id_asked_for(self):
        row = bp.plan_resource(None, "res-9")
        assert (row.id, row.status) == ("res-9", bp.BLOCKED) and row.variables is None


def test_counts_group_rows_by_status():
    rows = [bp.Row("a", status=bp.CONVERTED), bp.Row("b", status=bp.CONVERTED), bp.Row("c", status=bp.BLOCKED)]
    assert bp.counts(rows) == {bp.CONVERTED: 2, bp.BLOCKED: 1}
