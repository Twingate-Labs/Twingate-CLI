"""Creating service accounts, certificate authorities, Gateways and DNS profiles, and importing approver groups: planning, applying, and re-running."""

from __future__ import annotations

import pytest

from tests.importer.ca_material import pem, ssh_fingerprint, ssh_key, x509_fingerprint
from tests.importer.fake_api import FakeApi
from tgcli.client.exceptions import TwingateAPIError
from tgcli.importer.apply import apply_plan, write_count
from tgcli.importer.cafiles import CaFiles, read_ca_files
from tgcli.importer.load import (
    AccessSpec, CaSpec, DnsProfileSpec, GatewaySpec, ResourceSpec, ServiceAccountSpec, Specs, NetworkSpec, GroupSpec,
)
from tgcli.importer.notices import not_carried_over
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, SKIP, UPDATE, Ref, build_plan
from tgcli.importer.state import fetch_state

NETS = [{"id": "N1", "name": "HQ"}, {"id": "N2", "name": "DR"}]
GROUPS = [{"id": "G1", "name": "Eng", "type": "MANUAL"}, {"id": "G2", "name": "Ops", "type": "MANUAL"}]
ROOT, SHELL = x509_fingerprint("root"), ssh_fingerprint("shell")


def files(tmp_path, **named):
    """A folder of certificate files: name -> text."""
    for name, text in named.items():
        (tmp_path / name).write_text(text)
    return read_ca_files(tmp_path)


def build(api, specs, ca_files=None, sync=False, prune=False):
    state = fetch_state(api, specs, sync=sync)
    return build_plan(specs, state, sync, prune, ca_files)


def run(api, specs, ca_files=None, sync=False, prune=False):
    rows = build(api, specs, ca_files, sync, prune)
    api.requests.clear()
    apply_plan(api, rows)
    return rows


def sa(name, keys=0):
    return ServiceAccountSpec(source="service-accounts.json item 1", name=name, keys=keys)


def ca(name="Root", type="x509", fingerprint=ROOT):
    return CaSpec(source="certificate-authorities.json item 1", name=name, type=type, fingerprint=fingerprint)


def gateway(address="gw.example.com", network="HQ", x509=None, ssh=None):
    return GatewaySpec(
        source="gateways.json item 1", address=address, network=network,
        x509_ca={"name": "Root", "fingerprint": ROOT} if x509 is None else x509, ssh_ca=ssh or {},
    )


def dns(name="Kids", **kw):
    return DnsProfileSpec(source="dns-profiles.json item 1", name=name, **kw)


def resource(name="Wiki", **kw):
    everything = {"policy": "ALLOW_ALL", "ports": []}
    base = dict(source="resources.json item 1", name=name, network="HQ", address=f"{name.lower()}.internal",
                protocols={"allowIcmp": True, "tcp": everything, "udp": everything})
    base.update(kw)
    return ResourceSpec(**base)


def only(rows):
    assert len(rows) == 1, [(r.kind, r.name, r.action) for r in rows]
    return rows[0]


def by_kind(rows, kind):
    return [r for r in rows if r.kind == kind]


class TestServiceAccounts:
    def test_a_missing_one_is_created_and_a_rerun_finds_it(self):
        api = FakeApi()
        specs = Specs(service_accounts=[sa("ci")])
        (row,) = build(api, specs)
        assert row.action == CREATE and row.kind == "service account" and "without keys" in row.detail
        run(api, specs)
        assert [a["name"] for a in api.service_accounts] == ["ci"]
        (again,) = build(api, specs)
        assert again.action == EXISTS and again.existing_id == api.service_accounts[0]["id"]

    def test_an_existing_one_is_left_alone(self):
        api = FakeApi(service_accounts=[{"id": "S1", "name": "ci"}])
        rows = run(api, Specs(service_accounts=[sa("ci")]))
        assert only(rows).action == EXISTS and api.writes == []

    def test_two_in_the_tenant_with_one_name_block_the_row(self):
        api = FakeApi(service_accounts=[{"id": "S1", "name": "ci"}, {"id": "S2", "name": "ci"}])
        assert only(build(api, Specs(service_accounts=[sa("ci")]))).action == BLOCKED

    def test_a_repeat_in_the_file_and_a_row_with_a_problem_are_blocked_and_nothing_extra_is_made(self):
        bad = ServiceAccountSpec(source="x", name="", problems=["has no name"])
        api = FakeApi()
        rows = run(api, Specs(service_accounts=[sa("ci"), sa("ci"), bad]))
        assert [r.action for r in rows] == [CREATE, BLOCKED, BLOCKED] and "same name as" in rows[1].detail and rows[2].detail == "has no name"
        assert len(api.service_accounts) == 1

    def test_a_resource_in_the_same_file_is_given_access_for_the_account_it_just_made(self):
        api = FakeApi(networks=NETS)
        specs = Specs(service_accounts=[sa("ci")], resources=[resource(access=[AccessSpec("ci", kind="service account")])])
        rows = run(api, specs)
        assert [r.status for r in rows] == ["created", "created"] and rows[1].warnings == []
        assert list(api.resources[0]["access"]) == [api.service_accounts[0]["id"]]

    def test_a_service_account_still_gets_nothing_the_api_refuses_it(self):
        api = FakeApi(networks=NETS)
        entry = AccessSpec("ci", kind="service account", security_policy="Strict", given={"security_policy"})
        (_, wiki) = build(api, Specs(service_accounts=[sa("ci")], resources=[resource(access=[entry])]))
        assert wiki.grants == [] and "cannot give a service account" in wiki.warnings[0]

    def test_a_failure_to_create_it_leaves_the_resource_without_that_access_and_says_so(self):
        api = FakeApi(networks=NETS)
        api.fail["restoreServiceAccountCreate"] = "no"
        rows = run(api, Specs(service_accounts=[sa("ci")], resources=[resource(access=[AccessSpec("ci", kind="service account")])]))
        assert rows[0].status == "error" and rows[0].error == "no"
        assert rows[1].status == "created" and "was not created" in rows[1].warnings[0]

    def test_it_counts_as_a_write(self):
        assert write_count(build(FakeApi(), Specs(service_accounts=[sa("a"), sa("b")]))) == 2


class TestCertificateAuthorities:
    def test_a_ca_is_made_from_the_file_whose_fingerprint_is_the_backups(self, tmp_path):
        api = FakeApi()
        specs = Specs(certificate_authorities=[ca()])
        rows = run(api, specs, files(tmp_path, **{"root.pem": pem("root"), "other.pem": pem("other")}))
        (row,) = rows
        assert row.status == "created" and "root.pem" in row.detail
        assert [(c["name"], c["type"], c["fingerprint"]) for c in api.cas] == [("Root", "x509", ROOT)]

    def test_an_ssh_ca_is_made_from_a_public_key(self, tmp_path):
        api = FakeApi()
        rows = run(api, Specs(certificate_authorities=[ca("Shell", "ssh", SHELL)]), files(tmp_path, **{"shell.pub": ssh_key("shell")}))
        assert only(rows).status == "created" and api.cas[0]["type"] == "ssh"

    def test_a_rerun_finds_it_by_fingerprint_even_when_it_has_another_name(self, tmp_path):
        api = FakeApi()
        api.cas = [{"id": "CA9", "name": "Renamed", "fingerprint": ROOT, "type": "x509"}]
        (row,) = build(api, Specs(certificate_authorities=[ca()]), files(tmp_path, **{"root.pem": pem("root")}))
        assert row.action == EXISTS and row.existing_id == "CA9" and "as 'Renamed'" in row.detail

    def test_a_file_with_another_fingerprint_is_never_used(self, tmp_path):
        api = FakeApi()
        (row,) = build(api, Specs(certificate_authorities=[ca()]), files(tmp_path, **{"other.pem": pem("other")}))
        assert row.action == SKIP and "no supplied certificate file has this fingerprint" in row.detail

    def test_without_files_it_is_skipped_and_nothing_is_written(self):
        api = FakeApi()
        rows = run(api, Specs(certificate_authorities=[ca()]))
        assert only(rows).action == SKIP and api.writes == []

    def test_a_file_of_the_wrong_kind_is_not_used_even_with_the_right_fingerprint(self, tmp_path):
        # the key's fingerprint is in the file's list, but the backup says the authority is x509
        api = FakeApi()
        (row,) = build(api, Specs(certificate_authorities=[ca("Odd", "x509", SHELL)]), files(tmp_path, **{"shell.pub": ssh_key("shell")}))
        assert row.action == SKIP

    def test_the_wrong_certificate_reported_back_fails_the_row_and_nothing_is_built_on_it(self, tmp_path):
        api = FakeApi(networks=NETS)
        api.ca_fingerprint = lambda kind, content: "0" * 64  # the tenant fingerprints it differently from the file
        specs = Specs(certificate_authorities=[ca()], gateways=[gateway()])
        rows = run(api, specs, files(tmp_path, **{"root.pem": pem("root")}))
        assert rows[0].status == "error" and "not the certificate authority that was backed up" in rows[0].error and "tgcli ca delete -i" in rows[0].error
        assert rows[1].status == "error" and "was not created" in rows[1].error and api.gateways == []

    def test_a_same_named_ca_with_another_fingerprint_blocks_it(self, tmp_path):
        api = FakeApi()
        api.cas = [{"id": "CA9", "name": "Root", "fingerprint": "ff" * 32, "type": "x509"}]
        (row,) = build(api, Specs(certificate_authorities=[ca()]), files(tmp_path, **{"root.pem": pem("root")}))
        assert row.action == BLOCKED and "already has a certificate authority named 'Root'" in row.detail

    @pytest.mark.parametrize("spec, reason", [
        (CaSpec(source="x", name="Root", type="x509", fingerprint=""), "no fingerprint"),
        (CaSpec(source="x", name="", type="x509", fingerprint="aa", problems=["has no name"]), "has no name"),
    ])
    def test_a_ca_that_cannot_be_checked_is_blocked(self, spec, reason):
        assert reason in only(build(FakeApi(), Specs(certificate_authorities=[spec]))).detail

    def test_the_same_fingerprint_twice_is_blocked_the_second_time(self, tmp_path):
        rows = build(FakeApi(), Specs(certificate_authorities=[ca(), ca("Copy")]), files(tmp_path, **{"root.pem": pem("root")}))
        assert [r.action for r in rows] == [CREATE, BLOCKED] and "same fingerprint" in rows[1].detail

    def test_a_tenant_that_cannot_list_them_blocks_it_rather_than_guessing(self, tmp_path):
        api = FakeApi()
        api.unreadable["certificateAuthorities"] = TwingateAPIError("not on your plan")
        (row,) = build(api, Specs(certificate_authorities=[ca()]), files(tmp_path, **{"root.pem": pem("root")}))
        assert row.action == BLOCKED and "not on your plan" in row.detail

    def test_it_is_a_single_write_with_the_public_material_only(self, tmp_path):
        api = FakeApi()
        run(api, Specs(certificate_authorities=[ca()]), files(tmp_path, **{"root.pem": pem("root")}))
        assert [name for name, _ in api.writes] == ["createX509CA"]
        assert api.writes[0][1] == {"name": "Root", "certificate": pem("root").strip()}


class TestGateways:
    def tenant(self, **kw):
        api = FakeApi(networks=NETS, groups=GROUPS, **kw)
        api.cas = [{"id": "CA1", "name": "Root", "fingerprint": ROOT, "type": "x509"}, {"id": "CA2", "name": "Shell", "fingerprint": SHELL, "type": "ssh"}]
        return api

    def test_a_gateway_is_made_with_the_ca_the_tenant_already_has(self):
        api = self.tenant()
        rows = run(api, Specs(gateways=[gateway(ssh={"name": "Shell", "fingerprint": SHELL})]))
        (row,) = rows
        assert row.status == "created" and "SSH certificate authority" in row.detail and "still has to be deployed" in row.warnings[0]
        assert [(g["address"], g["remoteNetwork"]["name"], g["x509CA"]["id"], g["sshCA"]["id"]) for g in api.gateways] == [("gw.example.com", "HQ", "CA1", "CA2")]

    def test_a_ca_made_in_the_same_run_is_used(self, tmp_path):
        api = FakeApi(networks=NETS)
        specs = Specs(certificate_authorities=[ca()], gateways=[gateway()])
        rows = run(api, specs, files(tmp_path, **{"root.pem": pem("root")}))
        assert [r.status for r in rows] == ["created", "created"]
        assert api.gateways[0]["x509CA"]["id"] == api.cas[0]["id"]

    def test_a_remote_network_made_in_the_same_run_is_used(self):
        api = self.tenant()
        net = NetworkSpec(source="x", name="Fresh")
        rows = run(api, Specs(networks=[net], gateways=[gateway(network="Fresh")]))
        assert [r.status for r in rows] == ["created", "created"] and api.gateways[0]["remoteNetwork"]["name"] == "Fresh"

    def test_a_rerun_finds_it_by_address_and_remote_network(self):
        api = self.tenant()
        specs = Specs(gateways=[gateway()])
        run(api, specs)
        (again,) = build(api, specs)
        assert again.action == EXISTS and again.existing_id == api.gateways[0]["id"]
        (elsewhere,) = build(api, Specs(gateways=[gateway(network="DR")]))
        assert elsewhere.action == CREATE  # the same address in another Remote Network is another Gateway

    def test_two_with_the_same_address_and_network_in_the_file_are_blocked_the_second_time(self):
        rows = build(self.tenant(), Specs(gateways=[gateway(), gateway()]))
        assert [r.action for r in rows] == [CREATE, BLOCKED] and "same address and Remote Network" in rows[1].detail

    def test_a_missing_ca_blocks_it_and_says_how_to_supply_one(self):
        (row,) = build(FakeApi(networks=NETS), Specs(gateways=[gateway()]))
        assert row.action == BLOCKED and "--ca-files" in row.detail

    def test_a_ca_the_file_names_without_a_fingerprint_is_found_by_name_and_kind(self):
        api = self.tenant()
        (row,) = build(api, Specs(gateways=[gateway(x509={"name": "Root", "fingerprint": ""})]))
        assert row.action == CREATE
        (row,) = build(api, Specs(gateways=[gateway(x509={"name": "Nope", "fingerprint": ""})]))
        assert row.action == BLOCKED and "tgcli ca create" in row.detail
        (row,) = build(api, Specs(gateways=[gateway(x509={"name": "Shell", "fingerprint": ""})]))
        assert row.action == BLOCKED  # an SSH authority cannot stand in for the X.509 one

    def test_two_authorities_of_one_name_are_not_guessed_between(self):
        api = self.tenant()
        api.cas.append({"id": "CA3", "name": "Root", "fingerprint": "ee" * 32, "type": "x509"})
        (row,) = build(api, Specs(gateways=[gateway(x509={"name": "Root", "fingerprint": ""})]))
        assert row.action == BLOCKED and "cannot be told" in row.detail

    def test_a_ca_of_the_wrong_kind_by_fingerprint_is_refused(self):
        api = self.tenant()
        (row,) = build(api, Specs(gateways=[gateway(x509={"name": "Root", "fingerprint": SHELL})]))
        assert row.action == BLOCKED and "is not an X.509 one" in row.detail

    def test_a_ca_made_in_the_same_run_of_the_wrong_kind_is_refused_too(self, tmp_path):
        api = FakeApi(networks=NETS)
        specs = Specs(certificate_authorities=[ca("Shell", "ssh", SHELL)], gateways=[gateway(x509={"name": "Shell", "fingerprint": SHELL})])
        rows = build(api, specs, files(tmp_path, **{"shell.pub": ssh_key("shell")}))
        assert rows[0].action == CREATE and rows[1].action == BLOCKED and "is not an X.509 one" in rows[1].detail

    def test_a_missing_remote_network_blocks_it(self):
        (row,) = build(self.tenant(), Specs(gateways=[gateway(network="Nowhere")]))
        assert row.action == BLOCKED and "Remote Network 'Nowhere' does not exist" in row.detail

    def test_a_tenant_that_cannot_list_authorities_blocks_it(self):
        api = FakeApi(networks=NETS)
        api.unreadable["certificateAuthorities"] = TwingateAPIError("no")
        (row,) = build(api, Specs(gateways=[gateway()]))
        assert row.action == BLOCKED and "could not be read" in row.detail

    def test_a_rate_limit_while_reading_authorities_stops_the_import_instead_of_guessing(self):
        from tgcli.client.exceptions import TwingateThrottleError

        api = FakeApi(networks=NETS)
        api.unreadable["certificateAuthorities"] = TwingateThrottleError("slow down")
        with pytest.raises(TwingateThrottleError):
            build(api, Specs(gateways=[gateway()]))

    def test_a_row_with_a_problem_is_blocked_without_looking_anything_up(self):
        bad = GatewaySpec(source="x", address="", network="HQ", problems=["has no address"])
        assert only(build(self.tenant(), Specs(gateways=[bad]))).detail == "has no address"

    def test_two_existing_gateways_with_the_address_in_one_network_block_it(self):
        gws = [{"id": f"GW{i}", "address": "gw.example.com", "remoteNetwork": {"id": "N1", "name": "HQ"}} for i in (1, 2)]
        assert "2 Gateways with this address" in only(build(self.tenant(gateways=gws), Specs(gateways=[gateway()]))).detail


class TestResourcesThroughANewGateway:
    def tenant(self):
        api = FakeApi(networks=NETS, groups=GROUPS)
        api.cas = [{"id": "CA1", "name": "Root", "fingerprint": ROOT, "type": "x509"}, {"id": "CA2", "name": "Shell", "fingerprint": SHELL, "type": "ssh"}]
        return api

    def ssh(self, **kw):
        return resource("Bastion", type="SSH", gateway="gw.example.com", upstream={"port": 22}, downstream={"port": 22}, **kw)

    def test_an_ssh_resource_is_served_through_the_gateway_made_just_before_it(self):
        api = self.tenant()
        specs = Specs(gateways=[gateway(ssh={"name": "Shell", "fingerprint": SHELL})], resources=[self.ssh()])
        rows = run(api, specs)
        assert [r.status for r in rows] == ["created", "created"]
        assert api.resources[0]["gateway"]["id"] == api.gateways[0]["id"]

    def test_an_ssh_resource_through_a_new_gateway_without_an_ssh_ca_is_blocked(self):
        rows = build(self.tenant(), Specs(gateways=[gateway()], resources=[self.ssh()]))
        assert rows[1].action == BLOCKED and "no SSH Certificate Authority" in rows[1].detail

    def test_a_web_app_does_not_need_the_ssh_ca(self):
        web = resource("Wiki", type="WEB_APP", gateway="gw.example.com", upstream={"port": 80}, downstream={"port": 443})
        rows = run(self.tenant(), Specs(gateways=[gateway()], resources=[web]))
        assert [r.status for r in rows] == ["created", "created"]

    def test_the_resources_own_network_picks_between_two_new_gateways_of_one_address(self):
        api = self.tenant()
        specs = Specs(gateways=[gateway(network="HQ"), gateway(network="DR")], resources=[self.ssh(network="DR")]) 
        rows = run(api, specs)
        assert [r.status for r in rows] == ["created", "created", "blocked"]  # the SSH one still needs an SSH CA
        web = resource("Wiki", type="WEB_APP", network="DR", gateway="gw.example.com", upstream={"port": 80}, downstream={"port": 443})
        api = self.tenant()
        run(api, Specs(gateways=[gateway(network="HQ"), gateway(network="DR")], resources=[web]))
        dr = next(g for g in api.gateways if g["remoteNetwork"]["name"] == "DR")
        assert api.resources[0]["gateway"]["id"] == dr["id"]

    def test_two_new_gateways_of_one_address_in_other_networks_are_not_guessed_between(self):
        api = FakeApi(networks=NETS + [{"id": "N3", "name": "Lab"}], groups=GROUPS)
        api.cas = [{"id": "CA1", "name": "Root", "fingerprint": ROOT, "type": "x509"}]
        web = resource("Wiki", type="WEB_APP", network="HQ", gateway="gw.example.com", upstream={"port": 80}, downstream={"port": 443})
        rows = build(api, Specs(gateways=[gateway(network="DR"), gateway(network="Lab")], resources=[web]))
        assert rows[-1].action == BLOCKED and "2 Gateways in this tenant have the address" in rows[-1].detail

    def test_a_gateway_that_failed_to_be_made_leaves_its_resource_with_an_error_not_a_guess(self):
        api = self.tenant()
        api.fail["restoreGatewayCreate"] = "refused"
        web = resource("Wiki", type="WEB_APP", gateway="gw.example.com", upstream={"port": 80}, downstream={"port": 443})
        rows = run(api, Specs(gateways=[gateway()], resources=[web]))
        assert rows[0].status == "error" and rows[1].status == "error" and "was not created" in rows[1].error and api.resources == []

    def test_a_missing_gateway_still_says_how_to_make_one(self):
        (row,) = build(self.tenant(), Specs(resources=[self.ssh()]))
        assert row.action == BLOCKED and "tgcli gateway create" in row.detail and "gateways file" in row.detail


class TestApproverGroups:
    def tenant(self, **kw):
        return FakeApi(networks=NETS, groups=GROUPS, **kw)

    def test_a_new_resource_gets_the_groups_that_exist_and_the_ones_made_in_the_same_run(self):
        api = self.tenant()
        specs = Specs(groups=[GroupSpec(source="g", name="New")], resources=[resource(approver_groups=["Eng", "New"], given={"approvers"})])
        rows = run(api, specs)
        assert [r.status for r in rows] == ["created", "created"]
        new = next(g for g in api.groups if g["name"] == "New")
        assert api.resources[0]["approvers"] == {"G1", new["id"]}

    def test_an_approver_group_that_does_not_exist_is_left_out_and_says_so(self):
        (row,) = build(self.tenant(), Specs(resources=[resource(approver_groups=["Eng", "Ghost"], given={"approvers"})]))
        assert row.action == CREATE and row.approvers_add == ["G1"]
        assert row.warnings == ["approver group 'Ghost' not added: no such group in this tenant or in the file"]

    def test_two_groups_of_the_name_are_not_guessed_between(self):
        api = self.tenant()
        api.groups.append({"id": "G9", "name": "Eng", "type": "MANUAL", "members": set()})
        (row,) = build(api, Specs(resources=[resource(approver_groups=["Eng"], given={"approvers"})]))
        assert row.approvers_add == [] and "2 groups with that name" in row.warnings[0]

    def test_an_existing_resource_is_topped_up_with_the_missing_approvers_only(self):
        api = self.tenant(resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "wiki.internal", "approvers": {"G1"}}])
        specs = Specs(resources=[resource(approver_groups=["Eng", "Ops"], given={"approvers"})])
        (row,) = build(api, specs)
        assert row.action == UPDATE and row.approvers_add == ["G2"] and "1 approver group to add" in row.detail
        run(api, specs)
        assert api.resources[0]["approvers"] == {"G1", "G2"}
        (again,) = build(api, specs)
        assert again.action == EXISTS

    def test_approvers_the_file_leaves_out_stay_unless_sync_and_prune_are_both_given(self):
        api = self.tenant(resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "wiki.internal", "approvers": {"G1", "G2"}}])
        spec = resource(approver_groups=["Eng"], given={"approvers"})
        for flags in ({}, {"sync": True}, {"prune": True}):
            assert only(build(api, Specs(resources=[spec]), **flags)).approvers_remove == []
        row = only(build(api, Specs(resources=[spec]), sync=True, prune=True))
        assert row.approvers_remove == ["G2"] and row.approvers_add == [] and "1 approver group to remove" in row.detail
        run(api, Specs(resources=[spec]), sync=True, prune=True)
        assert api.resources[0]["approvers"] == {"G1"}

    def test_prune_needs_the_file_to_state_the_approvers_at_all(self):
        api = self.tenant(resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "wiki.internal", "approvers": {"G1"}}])
        assert only(build(api, Specs(resources=[resource()]), sync=True, prune=True)).action == EXISTS
        # an empty list that IS stated means nobody approves
        row = only(build(api, Specs(resources=[resource(given={"approvers"})]), sync=True, prune=True))
        assert row.approvers_remove == ["G1"]

    def test_a_group_the_file_names_is_never_pruned_even_when_it_cannot_be_told_apart(self):
        api = self.tenant(resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "wiki.internal", "approvers": {"G1", "G9"}}])
        api.groups.append({"id": "G9", "name": "Eng", "type": "MANUAL", "members": set()})
        row = only(build(api, Specs(resources=[resource(approver_groups=["Eng"], given={"approvers"})]), sync=True, prune=True))
        assert row.approvers_remove == []

    def test_the_plan_itself_will_not_prune_approvers_the_file_does_not_state(self):
        api = self.tenant(resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "wiki.internal", "approvers": {"G1"}}])
        specs = Specs(resources=[resource()])
        state = fetch_state(api, specs, sync=True)
        state.resource_approvers["R1"] = {"G1"}  # even if something had read them
        assert only(build_plan(specs, state, True, True)).approvers_remove == []

    def test_an_ssh_resource_takes_approvers_in_its_create_too(self):
        api = FakeApi(networks=NETS, groups=GROUPS, gateways=[{"id": "GW1", "address": "gw.example.com", "remoteNetwork": {"id": "N1", "name": "HQ"}, "sshCA": {"id": "CA"}}])
        ssh = resource("Bastion", type="SSH", gateway="gw.example.com", upstream={"port": 22}, downstream={"port": 22}, approver_groups=["Ops"], given={"approvers"})
        assert only(run(api, Specs(resources=[ssh]))).status == "created" and api.resources[0]["approvers"] == {"G2"}

    def test_the_approvers_of_a_resource_the_file_says_nothing_about_are_not_even_read(self):
        api = self.tenant(resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "wiki.internal", "approvers": {"G1"}}])
        build(api, Specs(resources=[resource()]))
        assert not any("approverGroups" in q for q, _ in api.requests)


class TestDnsProfiles:
    def tenant(self, **kw):
        return FakeApi(groups=GROUPS, **kw)

    def test_a_profile_is_made_then_given_its_settings_and_groups(self):
        api = self.tenant()
        spec = dns(priority=5.0, fallback_method="AUTO", allowed_domains=["a.com"], denied_domains=["bad.com"], categories={"contentCategoryConfig": {"blockGambling": True}}, groups=["Eng", "Ops"])
        (row,) = run(api, Specs(dns_profiles=[spec]))
        assert row.status == "created" and row.detail == "priority, fallback method, allowed domains, denied domains, content categories, 2 groups"
        (profile,) = api.dns_profiles
        assert (profile["priority"], profile["fallbackMethod"], profile["allowedDomains"], profile["deniedDomains"]) == (5.0, "AUTO", ["a.com"], ["bad.com"])
        assert profile["contentCategoryConfig"] == {"blockGambling": True} and profile["groups"] == ["G1", "G2"]

    def test_a_profile_with_no_settings_is_just_created(self):
        api = self.tenant()
        (row,) = run(api, Specs(dns_profiles=[dns()]))
        assert row.detail == "default settings" and [n for n, _ in api.writes] == ["restoreDnsProfileCreate"]

    def test_a_group_made_in_the_same_run_is_put_on_the_profile(self):
        api = self.tenant()
        rows = run(api, Specs(groups=[GroupSpec(source="g", name="New")], dns_profiles=[dns(groups=["New"])]))
        assert [r.status for r in rows] == ["created", "created"]
        assert api.dns_profiles[0]["groups"] == [next(g["id"] for g in api.groups if g["name"] == "New")]

    def test_a_group_that_does_not_exist_is_left_off_and_says_so(self):
        (row,) = build(self.tenant(), Specs(dns_profiles=[dns(groups=["Eng", "Ghost"])]))
        assert row.warnings == ["group 'Ghost' not put on the profile: no such group in this tenant or in the file"]

    def test_two_groups_of_the_name_are_not_guessed_between(self):
        api = self.tenant()
        api.groups.append({"id": "G9", "name": "Eng", "type": "MANUAL", "members": set()})
        (row,) = build(api, Specs(dns_profiles=[dns(groups=["Eng"])]))
        assert "2 groups with that name" in row.warnings[0] and "groups" not in row.steps[-1].variables

    def test_an_existing_profile_is_left_as_it_is_and_a_rerun_finds_it(self):
        api = self.tenant()
        specs = Specs(dns_profiles=[dns(priority=2.0)])
        run(api, specs)
        count = len(api.writes)
        (again,) = run(api, specs)
        assert again.action == EXISTS and "left as they are" in again.detail and len(api.writes) == 0 and count == 2

    def test_two_profiles_in_the_tenant_with_the_name_block_the_row(self):
        api = self.tenant()
        api.dns_profiles = [{"id": "D1", "name": "Kids"}, {"id": "D2", "name": "Kids"}]
        assert only(build(api, Specs(dns_profiles=[dns()]))).action == BLOCKED

    def test_a_repeat_in_the_file_and_a_row_with_a_problem_are_blocked(self):
        bad = DnsProfileSpec(source="x", name="Odd", problems=["priority 'x' is not a number"])
        rows = build(self.tenant(), Specs(dns_profiles=[dns(), dns(), bad]))
        assert [r.action for r in rows] == [CREATE, BLOCKED, BLOCKED]

    def test_a_rate_limit_while_reading_profiles_stops_the_import_instead_of_guessing(self):
        from tgcli.client.exceptions import TwingateThrottleError

        api = self.tenant()
        api.unreadable["dnsFilteringProfiles"] = TwingateThrottleError("slow down")
        with pytest.raises(TwingateThrottleError):
            build(api, Specs(dns_profiles=[dns()]))

    def test_a_tenant_without_the_feature_blocks_rather_than_guessing(self):
        api = self.tenant()
        api.unreadable["dnsFilteringProfiles"] = TwingateAPIError("not enabled")
        (row,) = build(api, Specs(dns_profiles=[dns()]))
        assert row.action == BLOCKED and "not enabled" in row.detail

    def test_it_counts_each_step_as_a_write(self):
        assert write_count(build(self.tenant(), Specs(dns_profiles=[dns(priority=1.0), dns("B")]))) == 3


class TestNotCarriedOver:
    def specs(self, **counts):
        return Specs(counts=counts, service_accounts=[sa("ci", 2), sa("deploy", 1)])

    def test_each_backup_file_that_is_left_out_is_named_with_its_count_and_what_to_do(self):
        notices = {n.what: n for n in not_carried_over(
            Specs(counts={"users.json": 2, "connectors.json": 1, "security-policies.json": 3, "devices.json": 4}), [])}
        assert set(notices) == {"users", "connectors", "security policies", "device registrations"}
        assert "2 users in the backup" in notices["users"].detail and "identity provider" in notices["users"].detail
        assert "tgcli connector create" in notices["connectors"].detail
        assert "cannot create them" in notices["security policies"].detail and notices["security policies"].source == "security-policies.json"
        assert "devices.csv" in notices["device registrations"].detail

    def test_a_count_that_could_not_be_read_still_gets_a_notice(self):
        (notice,) = not_carried_over(Specs(counts={"users.json": None}), [])
        assert notice.detail.startswith("Not created (the users in the backup)")

    def test_keys_are_counted_across_all_the_service_accounts(self):
        (notice,) = not_carried_over(self.specs(), [])
        assert notice.what == "service account keys" and "3 keys in the backup" in notice.detail and "tgcli key create" in notice.detail

    def test_an_import_of_a_few_files_has_nothing_to_say(self):
        assert not_carried_over(Specs(service_accounts=[sa("ci")]), []) == []

    def test_cas_that_were_skipped_are_counted_and_unusable_files_are_listed(self, tmp_path):
        rows = build(FakeApi(), Specs(certificate_authorities=[ca(), ca("Other", fingerprint="ee" * 32)]))
        (notice,) = not_carried_over(Specs(), rows)
        assert notice.what == "certificate authorities" and "2 certificate authorities in the backup" in notice.detail and "--ca-files" in notice.detail
        (key,) = [f for f in (tmp_path / "k.key",)]
        key.write_text("-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n")
        bad = read_ca_files(tmp_path)
        assert not_carried_over(Specs(), [], bad)[-1].what == "certificate files" and "private key" in not_carried_over(Specs(), [], bad)[-1].detail
        assert not_carried_over(Specs(), [], CaFiles()) == []


class TestEverythingTogether:
    def test_a_whole_backup_is_rebuilt_in_an_empty_tenant_and_a_rerun_changes_nothing(self, tmp_path):
        api = FakeApi(users=[{"id": "U1", "email": "ann@x.com"}])
        specs = Specs(
            networks=[NetworkSpec(source="n", name="HQ")],
            groups=[GroupSpec(source="g", name="Eng", members=["ann@x.com"])],
            service_accounts=[sa("ci", 1)],
            certificate_authorities=[ca(), ca("Shell", "ssh", SHELL)],
            gateways=[gateway(ssh={"name": "Shell", "fingerprint": SHELL})],
            resources=[
                resource("Bastion", type="SSH", gateway="gw.example.com", upstream={"port": 22}, downstream={"port": 22},
                         access=[AccessSpec("Eng"), AccessSpec("ci", kind="service account")], approver_groups=["Eng"], given={"approvers"}),
            ],
            dns_profiles=[dns(priority=2.0, groups=["Eng"])],
        )
        certs = files(tmp_path, **{"root.pem": pem("root"), "shell.pub": ssh_key("shell")})
        rows = run(api, specs, certs)
        assert [(r.kind, r.status) for r in rows] == [
            ("remote network", "created"), ("group", "created"), ("service account", "created"), ("certificate authority", "created"),
            ("certificate authority", "created"), ("gateway", "created"), ("resource", "created"), ("dns profile", "created"),
        ], [(r.kind, r.status, r.error) for r in rows]
        eng = next(g["id"] for g in api.groups if g["name"] == "Eng")
        (res,) = api.resources
        assert res["gateway"]["address"] == "gw.example.com" and res["approvers"] == {eng} and set(res["access"]) == {eng, api.service_accounts[0]["id"]}
        assert api.dns_profiles[0]["groups"] == [eng]
        count = len(api.writes)
        again = run(api, specs, certs)
        assert {r.status for r in again} == {"exists"} and api.writes == [] and count > 0
