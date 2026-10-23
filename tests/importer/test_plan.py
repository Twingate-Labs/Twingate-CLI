"""What an import would do, from a file and what the tenant has. No API involved."""

from __future__ import annotations

import pytest

from tgcli.importer.load import AccessSpec, GroupSpec, NetworkSpec, ResourceSpec, Specs
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, SKIP, UPDATE, build_plan
from tgcli.importer.state import State


def net(name, **kw):
    return NetworkSpec(source=f"n:{name}", name=name, **kw)


def grp(name, members=(), **kw):
    return GroupSpec(source=f"g:{name}", name=name, members=list(members), **kw)


def res(name, network="HQ", access=(), **kw):
    kw.setdefault("address", "a.internal")
    kw.setdefault("protocols", {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}})
    return ResourceSpec(source=f"r:{name}", name=name, network=network, access=[a if isinstance(a, AccessSpec) else AccessSpec(a) for a in access], **kw)


def by_name(*nodes, key="name"):
    out: dict = {}
    for node in nodes:
        out.setdefault(node[key], []).append(node)
    return out


def state(networks=(), groups=(), users=(), policies=(), resources=(), members=None, access=None):
    return State(
        networks=by_name(*networks), groups=by_name(*groups), policies=by_name(*policies),
        users=by_name(*[{**u, "key": u["email"].lower()} for u in users], key="key"),
        resources={(r["name"], r["network"], r.get("address", "a.internal")): [r] for r in resources},
        group_members=members or {}, resource_access=access or {},
    )


def plan(specs, st=None):
    return build_plan(specs, st or state())


def only(rows):
    (row,) = rows
    return row


NET_HQ = {"id": "N-HQ", "name": "HQ"}
G_ENG = {"id": "G-ENG", "name": "Eng", "type": "MANUAL"}
G_SYNC = {"id": "G-SYNC", "name": "Okta", "type": "SYNCED"}
U_ANN = {"id": "U-ANN", "email": "Ann@x.com"}
U_BOB = {"id": "U-BOB", "email": "bob@x.com"}
POL = {"id": "P-STRICT", "name": "Strict"}


class TestNetworks:
    def test_a_new_one_is_created_and_an_existing_one_is_left_alone(self):
        rows = plan(Specs(networks=[net("New"), net("HQ")]), state(networks=[NET_HQ]))
        assert [(r.name, r.action) for r in rows] == [("New", CREATE), ("HQ", EXISTS)]
        assert rows[1].existing_id == "N-HQ"

    def test_a_row_with_problems_is_blocked_with_them(self):
        bad = net("x")
        bad.problems = ["location 'MARS' is not one of AWS"]
        row = only(plan(Specs(networks=[bad])))
        assert row.action == BLOCKED and "MARS" in row.detail

    def test_the_same_name_twice_blocks_the_second(self):
        rows = plan(Specs(networks=[net("A"), net("A")]))
        assert [r.action for r in rows] == [CREATE, BLOCKED] and "same name as n:A" in rows[1].detail

    def test_two_tenant_networks_with_the_name_block_it(self):
        row = only(plan(Specs(networks=[net("HQ")]), state(networks=[NET_HQ, {"id": "N2", "name": "HQ"}])))
        assert row.action == BLOCKED and "2 Remote Networks" in row.detail


class TestGroups:
    def test_a_new_group_gets_the_members_it_can_find_ignoring_email_case(self):
        row = only(plan(Specs(groups=[grp("New", ["ann@x.com", "BOB@X.COM"])]), state(users=[U_ANN, U_BOB])))
        assert row.action == CREATE and row.member_ids == ["U-ANN", "U-BOB"] and row.warnings == []

    def test_a_member_who_is_not_in_the_tenant_is_reported_and_the_group_still_goes_ahead(self):
        row = only(plan(Specs(groups=[grp("New", ["ann@x.com", "gone@x.com"])]), state(users=[U_ANN])))
        assert row.action == CREATE and row.member_ids == ["U-ANN"] and row.warnings == ["member not found: gone@x.com"]

    def test_an_email_shared_by_two_users_is_not_guessed(self):
        row = only(plan(Specs(groups=[grp("New", ["ann@x.com"])]), state(users=[U_ANN, {"id": "U-ANN2", "email": "ann@x.com"}])))
        assert row.member_ids == [] and "matches 2 users" in row.warnings[0]

    def test_an_existing_manual_group_is_only_added_to(self):
        row = only(plan(Specs(groups=[grp("Eng", ["ann@x.com", "bob@x.com"])]), state(groups=[G_ENG], users=[U_ANN, U_BOB], members={"G-ENG": {"U-ANN"}})))
        assert row.action == UPDATE and row.existing_id == "G-ENG" and row.member_ids == ["U-BOB"]

    def test_an_existing_group_that_has_everyone_is_left_alone(self):
        row = only(plan(Specs(groups=[grp("Eng", ["ann@x.com"])]), state(groups=[G_ENG], users=[U_ANN], members={"G-ENG": {"U-ANN"}})))
        assert row.action == EXISTS and row.member_ids == []

    def test_a_shared_email_is_settled_when_one_of_those_users_is_already_a_member(self):
        users = [U_ANN, {"id": "U-ANN2", "email": "ann@x.com"}]
        row = only(plan(Specs(groups=[grp("Eng", ["ann@x.com"])]), state(groups=[G_ENG], users=users, members={"G-ENG": {"U-ANN2"}})))
        assert row.action == EXISTS and row.warnings == []

    def test_a_synced_group_in_the_file_is_never_created_or_changed(self):
        row = only(plan(Specs(groups=[grp("Okta", ["ann@x.com"], type="SYNCED")]), state(groups=[G_SYNC], users=[U_ANN])))
        assert row.action == SKIP and "identity provider" in row.detail

    def test_a_system_group_in_the_file_is_not_imported(self):
        row = only(plan(Specs(groups=[grp("Everyone", type="SYSTEM")])))
        assert row.action == SKIP

    def test_a_manual_group_named_like_a_tenant_synced_group_is_skipped_not_duplicated(self):
        row = only(plan(Specs(groups=[grp("Okta", ["ann@x.com"])]), state(groups=[G_SYNC], users=[U_ANN])))
        assert row.action == SKIP and "synced group with this name already exists" in row.detail and row.member_ids == []

    def test_two_manual_groups_in_the_tenant_with_the_name_block_it(self):
        row = only(plan(Specs(groups=[grp("Eng")]), state(groups=[G_ENG, {"id": "G2", "name": "Eng", "type": "MANUAL"}])))
        assert row.action == BLOCKED

    def test_the_groups_policy_must_exist(self):
        row = only(plan(Specs(groups=[grp("New", security_policy="Nope")]), state(policies=[POL])))
        assert row.action == BLOCKED and "Security Policy 'Nope' does not exist" in row.detail

    def test_the_groups_policy_is_resolved(self):
        row = only(plan(Specs(groups=[grp("New", security_policy="Strict")]), state(policies=[POL])))
        assert row.action == CREATE and row.policy_id == "P-STRICT"

    def test_an_ambiguous_policy_name_blocks(self):
        row = only(plan(Specs(groups=[grp("New", security_policy="Strict")]), state(policies=[POL, {"id": "P2", "name": "Strict"}])))
        assert row.action == BLOCKED and "matches 2 policies" in row.detail

    def test_the_same_manual_group_twice_blocks_the_second(self):
        rows = plan(Specs(groups=[grp("A"), grp("A")]))
        assert [r.action for r in rows] == [CREATE, BLOCKED]

    def test_repeated_members_are_added_once(self):
        row = only(plan(Specs(groups=[grp("New", ["ann@x.com", "Ann@x.com"])]), state(users=[U_ANN])))
        assert row.member_ids == ["U-ANN"]


class TestResources:
    def test_a_new_resource_in_an_existing_network_is_created_with_its_settings(self):
        row = only(plan(Specs(resources=[res("Wiki", security_policy="Strict")]), state(networks=[NET_HQ], policies=[POL])))
        assert (row.action, row.network_id, row.policy_id) == (CREATE, "N-HQ", "P-STRICT")

    def test_a_network_created_by_the_same_import_is_accepted(self):
        rows = plan(Specs(networks=[net("New")], resources=[res("Wiki", "New")]))
        assert [(r.kind, r.action) for r in rows] == [("remote network", CREATE), ("resource", CREATE)] and rows[1].network_id is None

    def test_a_network_that_exists_nowhere_blocks(self):
        row = only(plan(Specs(resources=[res("Wiki", "Nowhere")])))
        assert row.action == BLOCKED and "'Nowhere' does not exist in this tenant or in the file" in row.detail

    def test_a_network_that_is_itself_blocked_does_not_count(self):
        bad = net("New")
        bad.problems = ["has no name"]
        rows = plan(Specs(networks=[bad], resources=[res("Wiki", "New")]))
        assert [r.action for r in rows] == [BLOCKED, BLOCKED]

    def test_an_ambiguous_network_blocks(self):
        row = only(plan(Specs(resources=[res("Wiki")]), state(networks=[NET_HQ, {"id": "N2", "name": "HQ"}])))
        assert row.action == BLOCKED and "2 Remote Networks named 'HQ'" in row.detail

    def test_a_policy_that_does_not_exist_blocks_rather_than_falling_back_to_the_default(self):
        row = only(plan(Specs(resources=[res("Wiki", security_policy="Nope")]), state(networks=[NET_HQ])))
        assert row.action == BLOCKED and "Security Policy 'Nope'" in row.detail

    def test_all_problems_are_reported_together(self):
        row = only(plan(Specs(resources=[res("Wiki", "Nowhere", security_policy="Nope")])))
        assert "Nowhere" in row.detail and "Nope" in row.detail

    def test_an_existing_resource_is_matched_by_name_within_its_network_only(self):
        existing = {"id": "R1", "name": "Wiki", "network": "Lab"}
        rows = plan(Specs(resources=[res("Wiki", "HQ"), res("Wiki", "Lab")]), state(networks=[NET_HQ, {"id": "N-LAB", "name": "Lab"}], resources=[existing]))
        assert [r.action for r in rows] == [CREATE, EXISTS]

    def test_the_same_name_and_network_with_different_addresses_are_different_resources(self):
        rows = plan(Specs(resources=[res("CIDR", address="10.0.0.0/16"), res("CIDR", address="10.1.0.0/16")]), state(networks=[NET_HQ]))
        assert [r.action for r in rows] == [CREATE, CREATE]

    def test_an_existing_resource_with_another_address_is_not_the_same_resource(self):
        existing = {"id": "R1", "name": "Wiki", "network": "HQ", "address": "old.internal"}
        assert only(plan(Specs(resources=[res("Wiki", address="new.internal")]), state(networks=[NET_HQ], resources=[existing]))).action == CREATE

    def test_two_rows_that_cannot_be_told_apart_are_not_both_imported(self):
        rows = plan(Specs(resources=[res("Wiki"), res("Wiki")]), state(networks=[NET_HQ]))
        assert rows[1].action == BLOCKED and "cannot be told apart" in rows[1].detail

    def test_an_existing_resource_is_only_given_the_access_it_lacks(self):
        st = state(networks=[NET_HQ], groups=[G_ENG, {"id": "G-OPS", "name": "Ops", "type": "MANUAL"}],
                   resources=[{"id": "R1", "name": "Wiki", "network": "HQ"}], access={"R1": {"G-ENG"}})
        row = only(plan(Specs(resources=[res("Wiki", access=["Eng", "Ops"])]), st))
        assert row.action == UPDATE and [g.group_id for g in row.grants] == ["G-OPS"]

    def test_an_existing_resource_with_all_its_access_is_left_alone(self):
        st = state(networks=[NET_HQ], groups=[G_ENG], resources=[{"id": "R1", "name": "Wiki", "network": "HQ"}], access={"R1": {"G-ENG"}})
        assert only(plan(Specs(resources=[res("Wiki", access=["Eng"])]), st)).action == EXISTS

    def test_two_tenant_resources_with_the_name_in_the_network_block_it(self):
        st = state(networks=[NET_HQ])
        st.resources[("Wiki", "HQ", "a.internal")] = [{"id": "R1"}, {"id": "R2"}]
        assert only(plan(Specs(resources=[res("Wiki")]), st)).action == BLOCKED

    def test_the_same_resource_twice_blocks_the_second(self):
        rows = plan(Specs(resources=[res("Wiki"), res("Wiki")]), state(networks=[NET_HQ]))
        assert [r.action for r in rows] == [CREATE, BLOCKED]

    @pytest.mark.parametrize("kind", ["SSH", "WEB_APP", "KUBERNETES"])
    def test_other_resource_types_are_skipped_with_a_reason(self, kind):
        row = only(plan(Specs(resources=[res("Bastion", type=kind)])))
        assert row.action == SKIP and f"{kind} resources are not imported yet" in row.detail

    def test_a_resource_with_problems_is_blocked(self):
        bad = res("Wiki")
        bad.problems = ["tcp_ports '80-x' is not a port"]
        assert only(plan(Specs(resources=[bad]), state(networks=[NET_HQ]))).action == BLOCKED

    def test_notes_from_the_file_are_carried_as_warnings(self):
        r = res("Wiki")
        r.notes = ["approver groups are not imported"]
        assert only(plan(Specs(resources=[r]), state(networks=[NET_HQ]))).warnings == ["approver groups are not imported"]


class TestAccess:
    def base(self, **kw):
        return state(networks=[NET_HQ], **kw)

    def test_an_existing_group_is_resolved_to_its_id_including_a_synced_one(self):
        row = only(plan(Specs(resources=[res("Wiki", access=["Eng", "Okta"])]), self.base(groups=[G_ENG, G_SYNC])))
        assert [g.group_id for g in row.grants] == ["G-ENG", "G-SYNC"] and row.warnings == []

    def test_a_group_created_by_the_same_import_has_no_id_yet(self):
        rows = plan(Specs(groups=[grp("New")], resources=[res("Wiki", access=["New"])]), self.base())
        grant = rows[1].grants[0]
        assert (grant.group, grant.group_id) == ("New", None) and rows[1].warnings == []

    def test_a_group_that_is_blocked_in_the_file_is_not_a_group_to_grant(self):
        rows = plan(Specs(groups=[grp("New", security_policy="Nope")], resources=[res("Wiki", access=["New"])]), self.base())
        assert rows[1].action == CREATE and rows[1].grants == [] and "no such group" in rows[1].warnings[0]

    def test_a_group_that_exists_nowhere_is_left_out_with_a_warning_and_the_resource_still_goes_ahead(self):
        row = only(plan(Specs(resources=[res("Wiki", access=["Ghost", "Eng"])]), self.base(groups=[G_ENG])))
        assert row.action == CREATE and [g.group for g in row.grants] == ["Eng"]
        assert row.warnings == ["access for group 'Ghost' not added: no such group in this tenant or in the file"]

    def test_an_ambiguous_group_is_left_out(self):
        row = only(plan(Specs(resources=[res("Wiki", access=["Eng"])]), self.base(groups=[G_ENG, {"id": "G2", "name": "Eng", "type": "SYNCED"}])))
        assert row.grants == [] and "2 groups with that name" in row.warnings[0]

    def test_a_per_group_policy_is_resolved(self):
        row = only(plan(Specs(resources=[res("Wiki", access=[AccessSpec("Eng", security_policy="Strict")])]), self.base(groups=[G_ENG], policies=[POL])))
        assert row.grants[0].policy_id == "P-STRICT"

    def test_a_per_group_policy_that_does_not_exist_leaves_the_grant_out_instead_of_using_the_default(self):
        row = only(plan(Specs(resources=[res("Wiki", access=[AccessSpec("Eng", security_policy="Nope")])]), self.base(groups=[G_ENG])))
        assert row.grants == [] and "Security Policy 'Nope' does not exist" in row.warnings[0]

    def test_an_expired_grant_is_not_restored_as_permanent_access(self):
        access = [AccessSpec("Eng", expires_at="2001-01-01T00:00:00Z")]
        row = only(plan(Specs(resources=[res("Wiki", access=access)]), self.base(groups=[G_ENG])))
        assert row.grants == [] and "expired on 2001-01-01" in row.warnings[0]

    def test_a_grant_that_has_not_expired_keeps_its_expiry_and_other_settings(self):
        access = [AccessSpec("Eng", access_policy={"mode": "AUTO_LOCK", "durationSeconds": 60}, approval_mode="MANUAL", expires_at="2999-01-01T00:00:00Z")]
        grant = only(plan(Specs(resources=[res("Wiki", access=access)]), self.base(groups=[G_ENG]))).grants[0]
        assert (grant.access_policy, grant.approval_mode, grant.expires_at) == ({"mode": "AUTO_LOCK", "durationSeconds": 60}, "MANUAL", "2999-01-01T00:00:00Z")


class TestEdgeCases:
    def test_a_group_row_with_problems_is_blocked(self):
        bad = grp("x")
        bad.problems = ["has no name"]
        assert only(plan(Specs(groups=[bad]))).action == BLOCKED

    def test_an_expiry_without_a_timezone_is_read_as_utc(self):
        past = AccessSpec("Eng", expires_at="2001-01-01T00:00:00")
        row = only(plan(Specs(resources=[res("Wiki", access=[past])]), state(networks=[NET_HQ], groups=[G_ENG])))
        assert row.grants == [] and "expired" in row.warnings[0]

    def test_an_expiry_that_cannot_be_read_is_left_for_the_api_to_judge_not_dropped(self):
        odd = AccessSpec("Eng", expires_at="soon")
        row = only(plan(Specs(resources=[res("Wiki", access=[odd])]), state(networks=[NET_HQ], groups=[G_ENG])))
        assert [g.expires_at for g in row.grants] == ["soon"]


class TestOrder:
    def test_rows_come_networks_then_groups_then_resources_whatever_order_they_were_loaded_in(self):
        specs = Specs(resources=[res("Wiki", "New")], groups=[grp("G")], networks=[net("New")])
        assert [r.kind for r in plan(specs)] == ["remote network", "group", "resource"]
