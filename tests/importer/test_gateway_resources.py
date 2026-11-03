"""SSH, web app and Kubernetes resources in `tgcli import`: reading them, finding their Gateway, creating them, and syncing them."""

from __future__ import annotations

import csv
import json

import pytest

from tests.importer.fake_api import FakeApi
from tgcli.importer.apply import apply_plan, write_count
from tgcli.importer.load import CSV_COLUMNS, RESOURCES, load_file
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, UPDATE, build_plan
from tgcli.importer.state import fetch_state

NETS = [{"id": "N1", "name": "HQ"}, {"id": "N2", "name": "DR"}]
GROUPS = [{"id": "G1", "name": "Eng", "type": "MANUAL"}]
GATEWAYS = [{"id": "GW1", "address": "gw.example.com", "remoteNetwork": {"id": "N1", "name": "HQ"}, "sshCA": {"id": "CA1"}}]
POLICIES = [{"id": "P-STRICT", "name": "Strict", "policyType": "RESOURCE"}]


def backup(kind="SSH", name="bastion", **kw):
    """A resource as `tgcli backup` writes it."""
    record = {
        "type": kind, "name": name, "remoteNetwork": {"id": "X", "name": "HQ"}, "address": {"type": "DNS", "value": f"{name}.internal"},
        "protocols": {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}},
        "gateway": {"id": "OLD", "address": "gw.example.com"}, "upstream": {"port": 22}, "downstream": {"port": 22},
        "isVisible": True, "isBrowserShortcutEnabled": True, "access": [{"principal": {"type": "Group", "name": "Eng"}}],
    }
    if kind == "WEB_APP":
        record.update(upstream={"port": 8080, "tlsMode": "VERIFY_FULL"}, downstream={"port": 443, "tlsMode": "TLS13"},
                      requestHeaderRewrites=[{"key": "X-A", "value": "1"}])
    if kind == "KUBERNETES":
        record.update(clusterRef="prod", upstream={"port": 6443}, downstream={"port": 443})
    return {**record, **kw}


def load_json(tmp_path, *records):
    path = tmp_path / "resources.json"
    path.write_text(json.dumps(list(records)))
    return load_file(path, RESOURCES)


def load_csv(tmp_path, *rows):
    path = tmp_path / "resources.csv"
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS[RESOURCES])
        writer.writeheader()
        for row in rows:
            writer.writerow({"network": "HQ", "address": "a.internal", **row})
    return load_file(path, RESOURCES)


def tenant(*resources, gateways=GATEWAYS, networks=NETS):
    return FakeApi(networks=networks, groups=GROUPS, policies=POLICIES, gateways=gateways, resources=[
        {"id": f"R{i}", "network": "HQ", **r} for i, r in enumerate(resources, start=1)
    ])


def plan_for(api, specs, sync=False, prune=False):
    from tgcli.importer.load import Specs

    specs = Specs(resources=specs)
    return build_plan(specs, fetch_state(api, specs, sync=sync), sync=sync, prune=prune)


def run(api, specs, sync=False, prune=False):
    rows = plan_for(api, specs, sync, prune)
    api.requests.clear()
    apply_plan(api, rows)
    return rows


class TestReadingABackup:
    def test_an_ssh_resource_keeps_its_gateway_address_and_ports(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("SSH"))
        assert spec.problems == [] and spec.type == "SSH"
        assert (spec.gateway, spec.upstream, spec.downstream) == ("gw.example.com", {"port": 22}, {"port": 22})

    def test_a_web_app_keeps_its_tls_modes_and_headers(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("WEB_APP", "wiki"))
        assert spec.problems == []
        assert spec.upstream == {"port": 8080, "tlsMode": "VERIFY_FULL"} and spec.downstream == {"port": 443, "tlsMode": "TLS13"}
        assert spec.headers == [{"key": "X-A", "value": "1"}]

    def test_a_kubernetes_resource_keeps_its_cluster_reference(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("KUBERNETES", "k8s"))
        assert spec.problems == [] and spec.cluster_ref == "prod" and spec.upstream == {"port": 6443}

    def test_a_kubernetes_resource_does_not_need_a_gateway(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("KUBERNETES", "k8s", gateway=None))
        assert spec.problems == [] and spec.gateway == ""

    @pytest.mark.parametrize("kind", ["SSH", "WEB_APP"])
    def test_ssh_and_web_app_resources_must_name_a_gateway(self, tmp_path, kind):
        (spec,) = load_json(tmp_path, backup(kind, gateway=None))
        assert any("no gateway" in p for p in spec.problems)

    def test_a_web_app_needs_both_ports(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("WEB_APP", upstream={"tlsMode": "NONE"}, downstream=None))
        assert "has no upstream port" in spec.problems and "has no downstream port" in spec.problems

    def test_ports_and_tls_modes_are_checked(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("WEB_APP", upstream={"port": 70000, "tlsMode": "MAYBE"}, downstream={"port": "x"}))
        text = " ".join(spec.problems)
        assert "upstream port 70000 is not valid" in text and "TLS mode 'MAYBE'" in text and "downstream port 'x' is not a number" in text

    def test_a_downstream_tls_mode_is_checked_against_the_server_modes(self, tmp_path):
        for mode in ("VERIFY_FULL", "TLS12"):
            (spec,) = load_json(tmp_path, backup("WEB_APP", downstream={"port": 443, "tlsMode": mode}))
            assert any(f"downstream TLS mode '{mode}'" in p for p in spec.problems)

    def test_a_tls_mode_on_an_ssh_resource_is_a_problem(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("SSH", upstream={"port": 22, "tlsMode": "NONE"}))
        assert "the upstream TLS mode only applies to web app resources" in spec.problems

    def test_the_network_resource_settings_of_a_typed_resource_are_ignored(self, tmp_path):
        # the API reports protocols and the browser shortcut for every type, but cannot set them on these; they must not block or sync
        (spec,) = load_json(tmp_path, backup("SSH"))
        assert spec.problems == [] and spec.protocols == {} and spec.routing_mode is None
        assert spec.given.isdisjoint({"icmp", "tcp", "udp", "browser_shortcut", "routing_mode"})
        assert {"gateway", "upstream", "downstream", "access"} <= spec.given

    def test_a_network_resource_is_unchanged(self, tmp_path):
        (spec,) = load_json(tmp_path, backup("NETWORK", "wiki", gateway=None, upstream=None, downstream=None))
        assert spec.type == "NETWORK" and spec.gateway == "" and spec.upstream is None
        assert {"icmp", "tcp", "udp", "browser_shortcut"} <= spec.given and "gateway" not in spec.given


class TestReadingACsv:
    def test_the_type_column_accepts_the_usual_spellings(self, tmp_path):
        rows = [{"name": n, "type": t, "gateway": "gw.example.com", "upstream_port": "1", "downstream_port": "2"}
                for n, t in [("a", "ssh"), ("b", "Web App"), ("c", "web-app"), ("d", "webapp"), ("e", "k8s"), ("f", "Kubernetes"), ("g", "")]]
        specs = load_csv(tmp_path, *rows)
        assert [s.type for s in specs] == ["SSH", "WEB_APP", "WEB_APP", "WEB_APP", "KUBERNETES", "KUBERNETES", "NETWORK"]

    def test_a_web_app_row_reads_every_column(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "wiki", "type": "web app", "gateway": " gw.example.com ", "upstream_port": "8080", "downstream_port": "443",
                                      "upstream_tls": "verify_full", "downstream_tls": "tls13", "headers": "X-A=1; X-B = two "})
        assert spec.problems == [] and spec.gateway == "gw.example.com"
        assert spec.upstream == {"port": 8080, "tlsMode": "VERIFY_FULL"} and spec.downstream == {"port": 443, "tlsMode": "TLS13"}
        assert spec.headers == [{"key": "X-A", "value": "1"}, {"key": "X-B", "value": "two"}]
        assert {"gateway", "upstream", "downstream", "headers"} <= spec.given

    def test_blank_columns_state_nothing_so_a_sync_leaves_them_alone(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "bastion", "type": "ssh", "gateway": "gw.example.com"})
        assert spec.problems == [] and spec.upstream is None and spec.downstream is None
        assert "upstream" not in spec.given and "headers" not in spec.given and "cluster_ref" not in spec.given

    def test_a_kubernetes_row_without_a_gateway_is_fine(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "k8s", "type": "kubernetes", "cluster_ref": "prod"})
        assert spec.problems == [] and spec.cluster_ref == "prod"

    def test_a_malformed_header_blocks_the_row(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "wiki", "type": "web app", "gateway": "g", "upstream_port": "1", "downstream_port": "2", "headers": "X-A=1;oops"})
        assert any("'oops' should look like Key=Value" in p for p in spec.problems)

    def test_a_network_resource_row_that_fills_a_gateway_column_is_blocked(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "wiki", "gateway": "gw.example.com", "upstream_port": "22"})
        assert any("gateway only applies to SSH, web app and Kubernetes resources" in p for p in spec.problems)
        assert any("upstream_port only applies" in p for p in spec.problems)

    @pytest.mark.parametrize("column,value", [("tcp_ports", "443"), ("udp_ports", "53"), ("allow_icmp", "false"), ("routing_mode", "BYPASS_TWINGATE")])
    def test_a_typed_row_that_fills_a_network_resource_column_is_blocked(self, tmp_path, column, value):
        (spec,) = load_csv(tmp_path, {"name": "bastion", "type": "ssh", "gateway": "g", column: value})
        assert any(f"{column} only applies to network resources, not SSH resources" in p for p in spec.problems)

    def test_a_cluster_reference_and_headers_belong_to_their_own_type(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "bastion", "type": "ssh", "gateway": "g", "cluster_ref": "prod", "headers": "A=1"})
        assert "a cluster reference only applies to Kubernetes resources" in spec.problems
        assert "request headers only apply to web app resources" in spec.problems

    def test_a_network_resource_row_still_reads_ports_as_before(self, tmp_path):
        (spec,) = load_csv(tmp_path, {"name": "wiki", "tcp_ports": "80;443", "allow_icmp": "false"})
        assert spec.problems == [] and spec.protocols["tcp"]["ports"] == [{"start": 80, "end": 80}, {"start": 443, "end": 443}]


class TestFindingTheGateway:
    def test_the_gateway_is_found_by_address_not_by_the_id_in_the_backup(self, tmp_path):
        (row,) = plan_for(tenant(), load_json(tmp_path, backup("SSH")))
        assert row.action == CREATE and row.gateway_id == "GW1"

    def test_a_gateway_that_does_not_exist_blocks_the_row_and_says_what_to_do(self, tmp_path):
        (row,) = plan_for(tenant(gateways=[]), load_json(tmp_path, backup("SSH")))
        assert row.action == BLOCKED and "Gateway 'gw.example.com' does not exist in this tenant" in row.detail and "tgcli gateway create" in row.detail

    def test_two_gateways_with_one_address_are_told_apart_by_the_resources_network(self, tmp_path):
        twins = GATEWAYS + [{"id": "GW2", "address": "gw.example.com", "remoteNetwork": {"id": "N2", "name": "DR"}, "sshCA": {"id": "CA2"}}]
        (row,) = plan_for(tenant(gateways=twins), load_json(tmp_path, backup("SSH", remoteNetwork={"name": "DR"})))
        assert row.action == CREATE and row.gateway_id == "GW2"

    def test_two_gateways_with_one_address_and_no_way_to_tell_block_the_row(self, tmp_path):
        twins = GATEWAYS + [{"id": "GW2", "address": "gw.example.com", "remoteNetwork": {"id": "N1", "name": "HQ"}}]
        (row,) = plan_for(tenant(gateways=twins), load_json(tmp_path, backup("SSH")))
        assert row.action == BLOCKED and "2 Gateways in this tenant have the address" in row.detail

    def test_the_count_in_the_message_is_of_the_gateways_in_the_resources_own_network(self, tmp_path):
        trio = [{"id": f"GW{i}", "address": "gw.example.com", "remoteNetwork": {"id": "N1", "name": n}} for i, n in enumerate(["HQ", "HQ", "DR"])]
        (row,) = plan_for(tenant(gateways=trio), load_json(tmp_path, backup("SSH")))
        assert row.action == BLOCKED and "2 Gateways in this tenant have the address" in row.detail

    def test_two_gateways_with_one_address_none_in_the_resources_network_block_the_row(self, tmp_path):
        twins = [{"id": "GW1", "address": "gw.example.com", "remoteNetwork": {"id": "N2", "name": "DR"}},
                 {"id": "GW2", "address": "gw.example.com", "remoteNetwork": {"id": "N3", "name": "X"}}]
        (row,) = plan_for(tenant(gateways=twins), load_json(tmp_path, backup("SSH")))
        assert row.action == BLOCKED

    def test_an_ssh_resource_needs_a_gateway_with_an_ssh_ca(self, tmp_path):
        bare = [{**GATEWAYS[0], "sshCA": None}]
        (row,) = plan_for(tenant(gateways=bare), load_json(tmp_path, backup("SSH")))
        assert row.action == BLOCKED and "has no SSH Certificate Authority" in row.detail

    @pytest.mark.parametrize("kind", ["WEB_APP", "KUBERNETES"])
    def test_the_other_types_do_not_need_an_ssh_ca(self, tmp_path, kind):
        bare = [{**GATEWAYS[0], "sshCA": None}]
        (row,) = plan_for(tenant(gateways=bare), load_json(tmp_path, backup(kind, "x")))
        assert row.action == CREATE

    def test_syncing_an_ssh_resource_onto_a_gateway_without_an_ssh_ca_is_blocked(self, tmp_path):
        other = {"id": "GW9", "address": "other.example.com", "remoteNetwork": {"id": "N1", "name": "HQ"}, "sshCA": None}
        api = tenant({"name": "bastion", "type": "SSH", "address": "bastion.internal", "gateway": {"id": "GW1", "address": "gw.example.com"},
                      "upstream": {"port": 22}, "downstream": {"port": 22}}, gateways=GATEWAYS + [other])
        (row,) = plan_for(api, load_json(tmp_path, backup("SSH", gateway={"address": "other.example.com"})), sync=True)
        assert row.action == BLOCKED

    def test_the_gateways_are_only_read_when_a_resource_needs_one(self, tmp_path):
        api = tenant()
        plan_for(api, load_json(tmp_path, backup("NETWORK", "wiki", gateway=None)))
        assert not any("gateways(" in q for q, _ in api.requests)
        plan_for(api, load_json(tmp_path, backup("SSH")))
        assert any("gateways(" in q for q, _ in api.requests)

    def test_a_kubernetes_resource_with_no_gateway_needs_none_to_exist(self, tmp_path):
        (row,) = plan_for(tenant(gateways=[]), load_json(tmp_path, backup("KUBERNETES", "k8s", gateway=None)))
        assert row.action == CREATE and row.gateway_id is None

    def test_the_plan_names_the_type_and_the_gateway(self, tmp_path):
        (row,) = plan_for(tenant(), load_json(tmp_path, backup("WEB_APP", "wiki")))
        assert row.detail.startswith("web app resource, in 'HQ' through Gateway gw.example.com")


class TestTheMutations:
    def test_the_gateway_is_required_where_the_api_requires_it(self):
        from tgcli.queries import importing as q

        assert "$gatewayId: ID!" in q.CREATE_TYPED["SSH"] and "$gatewayId: ID!" in q.CREATE_TYPED["WEB_APP"]
        assert "$gatewayId: ID," in q.CREATE_TYPED["KUBERNETES"]
        assert all("$gatewayId: ID," in q.UPDATE_TYPED[kind] for kind in q.UPDATE_TYPED)

    def test_a_web_apps_two_sides_are_required_on_create_and_optional_on_update(self):
        from tgcli.queries import importing as q

        assert "$upstream: WebAppUpstreamInput!" in q.CREATE_TYPED["WEB_APP"] and "$downstream: WebAppDownstreamInput!" in q.CREATE_TYPED["WEB_APP"]
        assert "$upstream: WebAppUpstreamInput," in q.UPDATE_TYPED["WEB_APP"]


class TestCreating:
    def test_an_ssh_resource_is_created_with_its_gateway_ports_and_access(self, tmp_path):
        api = tenant()
        (row,) = run(api, load_json(tmp_path, backup("SSH", alias="ssh.example.com", isVisible=False)))
        assert row.status == "created" and not row.error
        assert [n for n, _ in api.writes] == ["importSshResourceCreate", "importAccess"]
        assert api.writes[0][1] == {
            "name": "bastion", "address": "bastion.internal", "remoteNetworkId": "N1", "gatewayId": "GW1", "alias": "ssh.example.com",
            "isVisible": False, "upstream": {"port": 22}, "downstream": {"port": 22},
        }
        assert api.writes[1][1] == {"id": row.id, "access": [{"principalId": "G1"}]}

    def test_a_web_app_is_created_with_tls_modes_and_headers(self, tmp_path):
        api = tenant()
        run(api, load_json(tmp_path, backup("WEB_APP", "wiki")))
        sent = api.writes[0][1]
        assert api.writes[0][0] == "importWebAppResourceCreate"
        assert sent["upstream"] == {"port": 8080, "tlsMode": "VERIFY_FULL"} and sent["downstream"] == {"port": 443, "tlsMode": "TLS13"}
        assert sent["requestHeaderRewrites"] == [{"key": "X-A", "value": "1"}] and sent["gatewayId"] == "GW1"

    def test_a_kubernetes_resource_is_created_with_its_cluster_reference_and_no_gateway_when_it_has_none(self, tmp_path):
        api = tenant(gateways=[])
        run(api, load_json(tmp_path, backup("KUBERNETES", "k8s", gateway=None)))
        sent = api.writes[0][1]
        assert api.writes[0][0] == "importKubernetesResourceCreate" and "gatewayId" not in sent
        assert sent["clusterRef"] == "prod" and sent["upstream"] == {"port": 6443}

    def test_only_what_the_file_sets_away_from_the_defaults_is_sent(self, tmp_path):
        api = tenant()
        run(api, load_csv(tmp_path, {"name": "bastion", "type": "ssh", "gateway": "gw.example.com"}))
        assert api.writes[0][1] == {"name": "bastion", "address": "a.internal", "remoteNetworkId": "N1", "gatewayId": "GW1"}

    def test_network_resource_settings_are_never_sent_for_these_types(self, tmp_path):
        api = tenant()
        run(api, load_json(tmp_path, backup("SSH")))
        assert {"protocols", "isBrowserShortcutEnabled", "routingMode"}.isdisjoint(api.writes[0][1])

    def test_security_policy_tags_and_access_policy_are_sent(self, tmp_path):
        api = tenant()
        run(api, load_json(tmp_path, backup("SSH", securityPolicy={"name": "Strict"}, tags=[{"key": "env", "value": "prod"}],
                                            accessPolicy={"mode": "AUTO_LOCK", "durationSeconds": 3600}, approvalMode="AUTOMATIC")))
        sent = api.writes[0][1]
        assert sent["securityPolicyId"] == "P-STRICT" and sent["tags"] == [{"key": "env", "value": "prod"}]
        assert sent["accessPolicy"] == {"mode": "AUTO_LOCK", "durationSeconds": 3600} and sent["approvalMode"] == "AUTOMATIC"

    def test_a_refused_create_is_an_error_row_and_no_access_is_attempted(self, tmp_path):
        api = tenant()
        api.fail["importSshResourceCreate"] = "Gateway is not in this Remote Network"
        (row,) = run(api, load_json(tmp_path, backup("SSH")))
        assert row.status == "error" and "Gateway is not in this Remote Network" in row.error
        assert [n for n, _ in api.writes] == ["importSshResourceCreate"]

    def test_a_second_run_finds_nothing_to_do(self, tmp_path):
        api = tenant()
        specs = load_json(tmp_path, backup("SSH"), backup("WEB_APP", "wiki"), backup("KUBERNETES", "k8s"))
        run(api, specs)
        rows = run(api, specs)
        assert [r.status for r in rows] == ["exists"] * 3 and api.writes == []

    def test_each_type_is_created_in_the_same_run_as_its_network_and_group(self, tmp_path):
        from tgcli.importer.load import GroupSpec, NetworkSpec, Specs

        api = FakeApi(gateways=GATEWAYS)
        path = tmp_path / "resources.json"
        path.write_text(json.dumps([backup("SSH", remoteNetwork={"name": "Fresh"}, access=[{"principal": {"type": "Group", "name": "New"}}])]))
        specs = Specs(networks=[NetworkSpec(name="Fresh")], groups=[GroupSpec(name="New")], resources=load_file(path, RESOURCES))
        rows = build_plan(specs, fetch_state(api, specs))
        # the gateway lives in HQ, which this tenant does not have: it is found by address, so the create proceeds
        apply_plan(api, rows)
        assert [r.status for r in rows] == ["created"] * 3
        assert api.resources[0]["network"] == "Fresh"

    def test_the_write_count_is_the_create_and_the_access_call(self, tmp_path):
        rows = plan_for(tenant(), load_json(tmp_path, backup("SSH")))
        assert write_count(rows) == 2


class TestExistingResources:
    def existing(self, **kw):
        return {"name": "bastion", "type": "SSH", "address": "bastion.internal", "gateway": {"id": "GW1", "address": "gw.example.com"},
                "upstream": {"port": 22}, "downstream": {"port": 22}, **kw}

    def test_a_matching_resource_is_left_alone(self, tmp_path):
        api = tenant({**self.existing(), "access": {"G1": {}}})
        (row,) = run(api, load_json(tmp_path, backup("SSH")))
        assert row.status == "exists" and api.writes == []

    def test_missing_access_is_added_without_a_sync(self, tmp_path):
        api = tenant(self.existing())
        (row,) = run(api, load_json(tmp_path, backup("SSH", upstream={"port": 2222})))
        assert row.status == "updated" and [n for n, _ in api.writes] == ["importAccess"]  # the port is only compared with --sync

    def test_a_resource_of_another_type_with_the_same_key_blocks_the_row(self, tmp_path):
        api = tenant({"name": "bastion", "address": "bastion.internal"})  # a network resource
        (row,) = plan_for(api, load_json(tmp_path, backup("SSH")))
        assert row.action == BLOCKED and "a network resource with this name, Remote Network and address already exists" in row.detail
        assert "cannot change a resource's type" in row.detail

    def test_a_network_resource_row_over_an_existing_ssh_resource_blocks_too(self, tmp_path):
        api = tenant(self.existing())
        (row,) = plan_for(api, load_json(tmp_path, backup("NETWORK", "bastion", gateway=None, upstream=None, downstream=None)))
        assert row.action == BLOCKED and "an SSH resource" in row.detail

    def test_the_lookup_asks_for_the_type(self, tmp_path):
        api = tenant()
        plan_for(api, load_json(tmp_path, backup("SSH")))
        assert any("__typename" in q for q, _ in api.lookups)


class TestSync:
    def existing(self, kind="SSH", **kw):
        base = {"name": "bastion", "type": "SSH", "address": "bastion.internal", "gateway": {"id": "GW1", "address": "gw.example.com"},
                "upstream": {"port": 22}, "downstream": {"port": 22}, "access": {"G1": {}}}
        if kind == "WEB_APP":
            base.update(name="wiki", type="WEB_APP", address="wiki.internal", upstream={"port": 8080, "tlsMode": "VERIFY_FULL"},
                        downstream={"port": 443, "tlsMode": "TLS13"}, requestHeaderRewrites=[{"key": "X-A", "value": "1"}])
        if kind == "KUBERNETES":
            base.update(name="k8s", type="KUBERNETES", address="k8s.internal", clusterRef="prod", upstream={"port": 6443}, downstream={"port": 443})
        return {**base, **kw}

    def test_a_matching_resource_has_nothing_to_sync(self, tmp_path):
        api = tenant(self.existing())
        (row,) = run(api, load_json(tmp_path, backup("SSH")), sync=True)
        assert row.status == "exists" and api.writes == []

    def test_a_changed_port_is_updated_with_the_types_own_mutation(self, tmp_path):
        api = tenant(self.existing())
        (row,) = run(api, load_json(tmp_path, backup("SSH", upstream={"port": 2222})), sync=True)
        assert row.status == "updated" and "upstream port" in row.detail
        assert api.writes == [("importSshResourceUpdate", {"id": "R1", "upstream": {"port": 2222}})]

    def test_a_moved_gateway_is_changed(self, tmp_path):
        twins = GATEWAYS + [{"id": "GW9", "address": "other.example.com", "remoteNetwork": {"id": "N1", "name": "HQ"}, "sshCA": {"id": "CA2"}}]
        api = tenant(self.existing(), gateways=twins)
        (row,) = run(api, load_json(tmp_path, backup("SSH", gateway={"address": "other.example.com"})), sync=True)
        assert "Gateway" in row.detail and api.writes == [("importSshResourceUpdate", {"id": "R1", "gatewayId": "GW9"})]

    def test_only_the_tls_mode_changing_sends_the_port_with_it(self, tmp_path):
        api = tenant(self.existing("WEB_APP"))
        record = backup("WEB_APP", "wiki", upstream={"port": 8080, "tlsMode": "INSECURE"})
        run(api, load_json(tmp_path, record), sync=True)
        assert api.writes == [("importWebAppResourceUpdate", {"id": "R1", "upstream": {"port": 8080, "tlsMode": "INSECURE"}})]

    def test_a_changed_downstream_port_is_updated(self, tmp_path):
        api = tenant(self.existing())
        run(api, load_json(tmp_path, backup("SSH", downstream={"port": 2200})), sync=True)
        assert api.writes == [("importSshResourceUpdate", {"id": "R1", "downstream": {"port": 2200}})]

    def test_a_blank_gateway_cell_does_not_move_a_kubernetes_resource_off_its_gateway(self, tmp_path):
        api = tenant(self.existing("KUBERNETES"))
        (row,) = run(api, load_csv(tmp_path, {"name": "k8s", "address": "k8s.internal", "type": "kubernetes"}), sync=True)
        assert row.status == "exists" and api.writes == []

    def test_a_tls_mode_the_file_does_not_state_is_kept(self, tmp_path):
        api = tenant(self.existing("WEB_APP"))
        run(api, load_csv(tmp_path, {"name": "wiki", "address": "wiki.internal", "type": "web app", "gateway": "gw.example.com",
                                     "upstream_port": "9090", "downstream_port": "443"}), sync=True)
        assert api.writes == [("importWebAppResourceUpdate", {"id": "R1", "upstream": {"port": 9090, "tlsMode": "VERIFY_FULL"}})]

    def test_headers_are_merged_without_prune_and_replaced_with_it(self, tmp_path):
        have = [{"key": "X-A", "value": "1"}, {"key": "X-Old", "value": "z"}]
        file = backup("WEB_APP", "wiki", requestHeaderRewrites=[{"key": "X-A", "value": "2"}, {"key": "X-New", "value": "n"}])
        api = tenant(self.existing("WEB_APP", requestHeaderRewrites=have))
        run(api, load_json(tmp_path, file), sync=True)
        assert api.writes[0][1]["requestHeaderRewrites"] == [{"key": "X-A", "value": "2"}, {"key": "X-Old", "value": "z"}, {"key": "X-New", "value": "n"}]
        api = tenant(self.existing("WEB_APP", requestHeaderRewrites=have))
        run(api, load_json(tmp_path, file), sync=True, prune=True)
        assert api.writes[0][1]["requestHeaderRewrites"] == [{"key": "X-A", "value": "2"}, {"key": "X-New", "value": "n"}]

    def test_a_changed_cluster_reference_is_updated(self, tmp_path):
        api = tenant(self.existing("KUBERNETES"))
        run(api, load_json(tmp_path, backup("KUBERNETES", "k8s", clusterRef="staging")), sync=True)
        assert api.writes == [("importKubernetesResourceUpdate", {"id": "R1", "clusterRef": "staging"})]

    def test_common_settings_use_the_same_mutation(self, tmp_path):
        api = tenant(self.existing())
        run(api, load_json(tmp_path, backup("SSH", alias="new.example.com", isVisible=False, securityPolicy={"name": "Strict"})), sync=True)
        (name, sent), = api.writes
        assert name == "importSshResourceUpdate"
        assert sent == {"id": "R1", "alias": "new.example.com", "isVisible": False, "securityPolicyId": "P-STRICT"}

    def test_a_blank_csv_cell_leaves_the_setting_alone(self, tmp_path):
        api = tenant(self.existing())
        (row,) = run(api, load_csv(tmp_path, {"name": "bastion", "address": "bastion.internal", "type": "ssh", "gateway": "gw.example.com"}), sync=True)
        assert row.status == "exists" and api.writes == []

    def test_the_network_resource_settings_a_backup_carries_never_cause_a_change(self, tmp_path):
        # the backup of an SSH resource lists protocols and a browser shortcut; syncing them would call a mutation that cannot set them
        api = tenant(self.existing(isBrowserShortcutEnabled=False, protocols={"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}))
        (row,) = run(api, load_json(tmp_path, backup("SSH")), sync=True)
        assert row.status == "exists" and api.writes == []

    def test_a_synced_resource_is_idempotent(self, tmp_path):
        api = tenant(self.existing())
        specs = load_json(tmp_path, backup("SSH", upstream={"port": 2222}, alias="x.example.com"))
        run(api, specs, sync=True)
        rows = run(api, specs, sync=True)
        assert [r.status for r in rows] == ["exists"] and api.writes == []

    def test_a_refused_update_is_an_error_row(self, tmp_path):
        api = tenant(self.existing())
        api.fail["importSshResourceUpdate"] = "Port is reserved"
        (row,) = run(api, load_json(tmp_path, backup("SSH", upstream={"port": 2222})), sync=True)
        assert row.status == "error" and "Port is reserved" in row.error

    def test_the_sync_lookup_reads_the_typed_fields(self, tmp_path):
        api = tenant(self.existing())
        plan_for(api, load_json(tmp_path, backup("SSH")), sync=True)
        query = next(q for q, _ in api.lookups if "alias isVisible" in q)
        for fragment in ("... on SSHResource", "... on WebAppResource", "... on KubernetesResource", "requestHeaderRewrites", "clusterRef"):
            assert fragment in query
