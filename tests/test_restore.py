"""Restore: what the plan says for each kind of damage, and that applying it puts the tenant back (a second plan finds nothing)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.importer.fake_api import FakeApi, resource_detail
from tgcli.backup_diff import Backup
from tgcli.importer.apply import apply_plan, write_count
from tgcli.importer.plan import BLOCKED, CREATE, EXISTS, SKIP, UPDATE
from tgcli.restore import build_plan

ALL = {"policy": "ALLOW_ALL", "ports": []}
PROTOCOLS = {"allowIcmp": True, "tcp": ALL, "udp": ALL}
MANUAL = {"mode": "MANUAL", "durationSeconds": None}


# ---------------------------------------------------------------- a tiny tenant in backup shape


def user(i):
    return {"id": f"U{i}", "email": f"u{i}@x.com"}


def net(i, name, **kw):
    return {"id": f"N{i}", "name": name, "location": "AWS", "networkType": "REGULAR", "isActive": True, **kw}


def group(i, name, members=(), type="MANUAL", policy=None, **kw):
    return {
        "id": f"G{i}", "name": name, "type": type, "isActive": True, "securityPolicy": policy,
        "users": [user(m) for m in members], "resources": [], **kw,
    }


def grant(principal, policy=None, access_policy=None, approval="MANUAL", expires=None, kind="Group"):
    return {
        "principal": {"type": kind, "id": principal["id"], "name": principal["name"]}, "securityPolicy": policy,
        "accessPolicy": access_policy or MANUAL, "approvalMode": approval, "expiresAt": expires,
    }


def resource(i, name, network, access=(), **kw):
    return {
        "id": f"R{i}", "type": "NETWORK", "name": name, "alias": None, "isActive": True,
        "remoteNetwork": {"id": network["id"], "name": network["name"]},
        "address": {"type": "DNS", "value": f"{name.lower()}.internal"}, "protocols": PROTOCOLS, "tags": [],
        "isVisible": True, "isBrowserShortcutEnabled": False, "securityPolicy": None, "accessPolicy": MANUAL,
        "approvalMode": "MANUAL", "routingMode": "THROUGH_TWINGATE", "approverGroups": [], "access": list(access), **kw,
    }


STRICT = {"id": "P1", "name": "Strict"}
HQ, DR = net(1, "HQ"), net(2, "DR")
ENG, OPS = group(1, "Eng", [1, 2], policy=STRICT), group(2, "Ops", [3])
WIKI = resource(1, "Wiki", HQ, [grant(ENG, policy=STRICT), grant(OPS)])
SA = {"id": "S1", "name": "Bot"}


def healthy():
    return {
        "remote_networks": [dict(HQ), dict(DR)], "groups": [dict(ENG), dict(OPS)], "resources": [dict(WIKI)],
        "users": [user(i) for i in range(1, 5)], "security_policies": [dict(STRICT)], "service_accounts": [dict(SA)],
    }


def backup_of(items: dict) -> Backup:
    return Backup(Path("backup"), {"tenant": "t", "createdAt": "2026-01-01T00:00:00+00:00"}, {k: [dict(i) for i in v] for k, v in items.items()})


def plan_for(backup_items: dict, current_items: dict, **kw):
    return build_plan(backup_of(backup_items), current_items, **kw)


def damaged(**edits):
    """The healthy tenant with each named type replaced (a callable edits the list of that type)."""
    current = {k: [dict(i) for i in v] for k, v in healthy().items()}
    for key, edit in edits.items():
        current[key] = edit(current[key])
    return current


def row(plan, kind, name):
    found = [r for r in plan.rows if r.kind == kind and r.name == name]
    assert len(found) == 1, f"{kind} {name}: {[(r.kind, r.name) for r in plan.rows]}"
    return found[0]


def rename(items, item_id, name):
    return [{**i, "name": name} if i["id"] == item_id else i for i in items]


def without(items, item_id):
    return [i for i in items if i["id"] != item_id]


def without_words(plan_row) -> str:
    return plan_row.detail


# ---------------------------------------------------------------- nothing wrong


class TestNothingToDo:
    def test_a_tenant_that_matches_its_backup_has_nothing_to_restore(self):
        plan = plan_for(healthy(), healthy())
        assert {r.action for r in plan.rows} == {EXISTS}
        assert [(r.kind, r.name) for r in plan.rows] == [
            ("remote network", "HQ"), ("remote network", "DR"), ("group", "Eng"), ("group", "Ops"), ("resource", "Wiki")]
        assert write_count(plan.rows) == 0

    def test_what_was_created_after_the_backup_is_left_alone_and_counted(self):
        current = damaged(
            groups=lambda g: [*g, group(9, "New")], remote_networks=lambda n: [*n, net(9, "Fresh")],
            resources=lambda r: [*r, resource(9, "Newer", HQ)],
        )
        plan = plan_for(healthy(), current)
        assert {r.action for r in plan.rows} == {EXISTS}
        assert plan.created_after == {"remote networks": 1, "groups": 1, "resources": 1}


# ---------------------------------------------------------------- matching: the ID is the identity


class TestRenames:
    def test_a_renamed_group_is_renamed_back_not_made_again(self):
        plan = plan_for(healthy(), damaged(groups=lambda g: rename(g, "G1", "Engineering")))
        r = row(plan, "group", "Eng")
        assert (r.action, r.existing_id, r.group_update) == (UPDATE, "G1", {"name": "Eng"})
        assert not [x for x in plan.rows if x.action == CREATE]
        assert "rename from 'Engineering'" in r.detail

    def test_a_renamed_network_is_renamed_back(self):
        r = row(plan_for(healthy(), damaged(remote_networks=lambda n: rename(n, "N1", "Oops"))), "remote network", "HQ")
        assert (r.action, r.network_update) == (UPDATE, {"name": "HQ"})

    def test_a_renamed_resource_is_renamed_back_and_its_address_restored(self):
        current = damaged(resources=lambda r: [{**r[0], "name": "Oops", "address": {"type": "DNS", "value": "evil.example.com"}}])
        r = row(plan_for(healthy(), current), "resource", "Wiki")
        assert r.action == UPDATE and r.resource_update == {"name": "Wiki", "address": "wiki.internal"}

    def test_an_object_deleted_and_made_again_by_hand_is_taken_to_be_the_original(self):
        recreated = damaged(groups=lambda g: [{**g[0], "id": "G99"}, g[1]])
        plan = plan_for(healthy(), recreated)
        r = row(plan, "group", "Eng")
        assert r.action in (UPDATE, EXISTS) and r.existing_id == "G99"
        assert any("original was deleted" in w for w in r.warnings)
        assert not [x for x in plan.rows if x.action == CREATE]

    def test_two_candidates_with_the_same_name_are_never_guessed(self):
        current = damaged(groups=lambda g: [{**g[0], "id": "G98"}, {**g[0], "id": "G99"}, g[1]])
        plan = plan_for(healthy(), current)
        r = row(plan, "group", "Eng")
        assert r.action == BLOCKED and "cannot be told" in r.detail

    def test_two_deleted_objects_sharing_a_name_with_one_candidate_are_not_guessed_either(self):
        twin = group(7, "Eng", [1])
        backup = {**healthy(), "groups": [dict(ENG), dict(twin), dict(OPS)]}
        current = damaged(groups=lambda g: [{**g[0], "id": "G99"}, g[1]])
        assert [r.action for r in plan_for(backup, current).rows if r.name == "Eng" and r.kind == "group"].count(BLOCKED) == 2


# ---------------------------------------------------------------- groups


class TestGroups:
    def test_members_who_were_removed_are_added_back_by_email(self):
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1)]}, g[1]])
        r = row(plan_for(healthy(), current), "group", "Eng")
        assert (r.action, r.member_ids) == (UPDATE, ["U2"])

    def test_a_member_whose_user_was_made_again_is_found_by_email(self):
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1)]}, g[1]], users=lambda u: [{"id": "U22", "email": "u2@x.com"}, *u[:1], *u[2:]])
        assert row(plan_for(healthy(), current), "group", "Eng").member_ids == ["U22"]

    def test_a_member_who_no_longer_exists_is_a_warning_not_a_failure(self):
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1)]}, g[1]], users=lambda u: [x for x in u if x["id"] != "U2"])
        r = row(plan_for(healthy(), current), "group", "Eng")
        assert r.member_ids == [] and r.warnings == ["member not found: u2@x.com"]

    def test_extra_members_stay_unless_prune_is_given(self):
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1), user(2), user(4)]}, g[1]])
        assert row(plan_for(healthy(), current), "group", "Eng").remove_member_ids == []
        r = row(plan_for(healthy(), current, prune=True), "group", "Eng")
        assert (r.action, r.remove_member_ids) == (UPDATE, ["U4"])

    def test_the_security_policy_is_put_back(self):
        current = damaged(groups=lambda g: [{**g[0], "securityPolicy": {"id": "P9", "name": "Other"}}, g[1]], security_policies=lambda p: [*p, {"id": "P9", "name": "Other"}])
        assert row(plan_for(healthy(), current), "group", "Eng").group_policy_id == "P1"

    def test_a_policy_that_was_made_again_is_found_by_name(self):
        current = damaged(groups=lambda g: [{**g[0], "securityPolicy": None}, g[1]], security_policies=lambda p: [{"id": "P77", "name": "Strict"}])
        assert row(plan_for(healthy(), current), "group", "Eng").group_policy_id == "P77"

    def test_a_policy_that_is_gone_is_a_warning_and_the_group_is_still_repaired(self):
        current = damaged(groups=lambda g: [{**g[0], "name": "Oops", "securityPolicy": None}, g[1]], security_policies=lambda p: [])
        r = row(plan_for(healthy(), current), "group", "Eng")
        assert r.group_policy_id is None and r.group_update == {"name": "Eng"}
        assert any("Security Policy not restored" in w and "no longer exists" in w for w in r.warnings)

    def test_a_security_policy_the_backup_never_had_is_not_cleared(self):
        current = damaged(groups=lambda g: [g[0], {**g[1], "securityPolicy": STRICT}])
        assert row(plan_for(healthy(), current), "group", "Ops").action == EXISTS

    def test_a_deleted_group_is_created_again_with_members_and_policy(self):
        plan = plan_for(healthy(), damaged(groups=lambda g: without(g, "G1")))
        r = row(plan, "group", "Eng")
        assert (r.action, r.member_ids, r.policy_id) == (CREATE, ["U1", "U2"], "P1")

    def test_a_deleted_group_whose_policy_is_gone_is_blocked_not_made_with_a_different_policy(self):
        r = row(plan_for(healthy(), damaged(groups=lambda g: without(g, "G1"), security_policies=lambda p: [])), "group", "Eng")
        assert r.action == BLOCKED and "different policy" in r.detail

    def test_a_disabled_group_is_enabled_again(self):
        r = row(plan_for(healthy(), damaged(groups=lambda g: [{**g[0], "isActive": False}, g[1]])), "group", "Eng")
        assert r.group_update == {"isActive": True}

    def test_a_deleted_disabled_group_comes_back_disabled(self):
        backup = {**healthy(), "groups": [{**ENG, "isActive": False}, dict(OPS)]}
        assert row(plan_for(backup, damaged(groups=lambda g: without(g, "G1"))), "group", "Eng").group_update == {"isActive": False}

    def test_synced_groups_are_never_touched_and_the_plan_says_so(self):
        synced = group(5, "Okta Eng", [1], type="SYNCED")
        backup = {**healthy(), "groups": [dict(ENG), dict(OPS), synced]}
        current = damaged(groups=lambda g: [*g, {**synced, "name": "Renamed", "users": []}])
        plan = plan_for(backup, current)
        assert not [r for r in plan.rows if "Okta" in r.name or r.name == "Renamed"]
        assert plan.left_alone == ["1 Synced Group (names and members belong to your identity provider)"]

    def test_a_deleted_synced_group_is_not_created(self):
        synced = group(5, "Okta Eng", [1], type="SYNCED")
        backup = {**healthy(), "groups": [dict(ENG), dict(OPS), synced]}
        assert not [r for r in plan_for(backup, healthy()).rows if r.name == "Okta Eng"]


class TestReferencesThatAreNotUnique:
    def test_a_policy_name_that_two_policies_now_share_is_not_guessed(self):
        current = damaged(groups=lambda g: [{**g[0], "securityPolicy": None}, g[1]], security_policies=lambda p: [{"id": "P7", "name": "Strict"}, {"id": "P8", "name": "Strict"}])
        r = row(plan_for(healthy(), current), "group", "Eng")
        assert r.group_policy_id is None and any("matches 2 objects now" in w for w in r.warnings)

    def test_an_email_two_users_share_is_not_guessed_when_the_original_user_is_gone(self):
        current = damaged(
            groups=lambda g: [{**g[0], "users": [user(1)]}, g[1]],
            users=lambda u: [x for x in u if x["id"] != "U2"] + [{"id": "U22", "email": "u2@x.com"}, {"id": "U23", "email": "U2@x.com"}],
        )
        r = row(plan_for(healthy(), current), "group", "Eng")
        assert r.member_ids == [] and r.warnings == ["member matches 2 users, not added: u2@x.com"]

    def test_a_user_who_still_exists_is_found_by_id_even_when_another_user_has_the_same_email(self):
        twin = {"id": "U22", "email": "u2@x.com"}
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1)]}, g[1]], users=lambda u: [*u, twin])
        assert row(plan_for(healthy(), current), "group", "Eng").member_ids == ["U2"]

    def test_the_twin_being_a_member_does_not_count_as_the_original_being_one(self):
        twin = {"id": "U22", "email": "u2@x.com"}
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1), twin]}, g[1]], users=lambda u: [*u, twin])
        r = row(plan_for(healthy(), current, prune=True), "group", "Eng")
        assert (r.member_ids, r.remove_member_ids) == (["U2"], ["U22"])

    def test_prune_keeps_a_member_who_was_made_again_under_a_new_id(self):
        remade = {"id": "U22", "email": "u2@x.com"}
        current = damaged(groups=lambda g: [{**g[0], "users": [user(1), remade]}, g[1]], users=lambda u: [x for x in u if x["id"] != "U2"] + [remade])
        r = row(plan_for(healthy(), current, prune=True), "group", "Eng")
        assert (r.action, r.member_ids, r.remove_member_ids) == (EXISTS, [], [])

    def test_two_deleted_groups_with_one_name_get_no_access_back_because_which_is_which_is_unknown(self):
        twin = group(7, "Ops", [4])
        backup = {**healthy(), "groups": [dict(ENG), dict(OPS), twin], "resources": [{**WIKI, "access": [grant(OPS), grant(twin)]}]}
        plan = plan_for(backup, damaged(groups=lambda g: without(g, "G2"), resources=lambda _: [{**WIKI, "access": [grant(ENG, policy=STRICT)]}]))
        assert [r.action for r in plan.rows if r.kind == "group" and r.name == "Ops"] == [CREATE, CREATE]
        assert row(plan, "resource", "Wiki").grants == []
        assert all(any("another deleted group has this name" in w for w in r.warnings) for r in plan.rows if r.kind == "group" and r.name == "Ops")


# ---------------------------------------------------------------- networks


class TestNetworks:
    def test_a_disabled_network_is_turned_back_on_and_the_location_restored(self):
        r = row(plan_for(healthy(), damaged(remote_networks=lambda n: [{**n[0], "isActive": False, "location": "AZURE"}, n[1]])), "remote network", "HQ")
        assert r.network_update == {"location": "AWS", "isActive": True}

    def test_a_network_type_the_api_cannot_change_is_a_warning(self):
        r = row(plan_for(healthy(), damaged(remote_networks=lambda n: [{**n[0], "networkType": "EXIT"}, n[1]])), "remote network", "HQ")
        assert r.action == EXISTS and "cannot change it" in r.warnings[0]

    def test_a_deleted_network_is_created_again_and_the_resource_in_it_with_it(self):
        current = damaged(remote_networks=lambda n: without(n, "N1"), resources=lambda r: [])
        plan = plan_for(healthy(), current)
        assert row(plan, "remote network", "HQ").action == CREATE
        wiki = row(plan, "resource", "Wiki")
        assert (wiki.action, wiki.network_id) == (CREATE, None)  # the new network's ID is only known once it exists


# ---------------------------------------------------------------- resources


class TestResources:
    def test_changed_settings_are_put_back(self):
        changed = {**WIKI, "alias": "wiki.corp", "isVisible": False, "approvalMode": "AUTOMATIC", "tags": [{"key": "k", "value": "v"}],
                   "protocols": {"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 22, "end": 22}]}, "udp": ALL}}
        r = row(plan_for(healthy(), damaged(resources=lambda _: [changed])), "resource", "Wiki")
        assert r.action == UPDATE
        assert r.resource_update == {
            "isVisible": True, "approvalMode": "MANUAL",
            "protocols": {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}},
        }  # an alias or tag the backup does not have is not cleared (nothing is, without --prune for tags)

    def test_a_disabled_resource_is_enabled_again(self):
        r = row(plan_for(healthy(), damaged(resources=lambda _: [{**WIKI, "isActive": False}])), "resource", "Wiki")
        assert r.resource_update == {"isActive": True}

    def test_a_resource_moved_to_another_network_is_moved_back(self):
        moved = {**WIKI, "remoteNetwork": {"id": "N2", "name": "DR"}}
        r = row(plan_for(healthy(), damaged(resources=lambda _: [moved])), "resource", "Wiki")
        assert r.resource_update == {"remoteNetworkId": "N1"}

    def test_a_resource_moved_out_of_a_network_that_was_deleted_waits_for_it_to_be_created(self):
        moved = {**WIKI, "remoteNetwork": {"id": "N2", "name": "DR"}}
        plan = plan_for(healthy(), damaged(resources=lambda _: [moved], remote_networks=lambda n: without(n, "N1")))
        r = row(plan, "resource", "Wiki")
        assert (r.move_to_network, r.resource_update) == ("HQ", {})
        assert write_count([r]) == 1

    def test_approver_groups_are_named_as_not_restored_not_as_not_imported(self):
        with_approvers = {**WIKI, "approverGroups": [{"id": "G1", "name": "Eng"}]}
        for current in (damaged(resources=lambda _: [dict(with_approvers)]), damaged(resources=lambda _: [])):
            r = row(plan_for({**healthy(), "resources": [with_approvers]}, current), "resource", "Wiki")
            assert r.warnings == ["approver groups are not restored"]

    def test_a_deleted_resource_is_created_again_with_its_access(self):
        plan = plan_for(healthy(), damaged(resources=lambda _: []))
        r = row(plan, "resource", "Wiki")
        assert (r.action, r.network_id) == (CREATE, "N1")
        assert [(g.group, g.group_id, g.policy_id) for g in r.grants] == [("Eng", "G1", "P1"), ("Ops", "G2", None)]

    def test_a_resource_in_a_network_that_cannot_be_found_is_blocked(self):
        r = row(plan_for(healthy(), damaged(resources=lambda _: [], remote_networks=lambda n: without(n, "N1")) | {}), "resource", "Wiki")
        assert r.action == CREATE  # the network is created in the same plan

    def test_a_policy_that_is_gone_leaves_the_resources_policy_as_it_is_and_the_rest_is_repaired(self):
        backup = {**healthy(), "resources": [{**WIKI, "securityPolicy": STRICT}]}
        current = damaged(resources=lambda _: [{**WIKI, "securityPolicy": {"id": "P9", "name": "Other"}, "alias": "changed", "isVisible": False}], security_policies=lambda p: [])
        r = row(plan_for(backup, current), "resource", "Wiki")
        assert r.resource_update == {"isVisible": True} and any("Security Policy not restored" in w for w in r.warnings)

    def test_a_deleted_resource_whose_policy_is_gone_is_blocked(self):
        backup = {**healthy(), "resources": [{**WIKI, "securityPolicy": STRICT}]}
        r = row(plan_for(backup, damaged(resources=lambda _: [], security_policies=lambda p: [])), "resource", "Wiki")
        assert r.action == BLOCKED and "no longer exists" in r.detail

    def test_a_deleted_disabled_resource_is_made_and_then_disabled(self):
        backup = {**healthy(), "resources": [{**WIKI, "isActive": False}]}
        assert row(plan_for(backup, damaged(resources=lambda _: [])), "resource", "Wiki").resource_update == {"isActive": False}

    def test_a_resource_made_again_by_hand_is_taken_to_be_the_original(self):
        recreated = {**WIKI, "id": "R99"}
        plan = plan_for(healthy(), damaged(resources=lambda _: [recreated]))
        r = row(plan, "resource", "Wiki")
        assert r.existing_id == "R99" and not [x for x in plan.rows if x.action == CREATE]

    def test_resources_with_the_same_name_network_and_address_are_told_apart_by_id(self):
        twin = {**WIKI, "id": "R2"}
        backup = {**healthy(), "resources": [dict(WIKI), twin]}
        plan = plan_for(backup, damaged(resources=lambda _: [dict(WIKI), dict(twin)]))
        assert [r.action for r in plan.rows if r.kind == "resource"] == [EXISTS, EXISTS]

    def test_other_resource_types_only_get_their_access_back(self):
        ssh = {**WIKI, "type": "SSH", "id": "R5", "name": "Box", "access": [grant(ENG)]}
        backup = {**healthy(), "resources": [ssh]}
        current = damaged(resources=lambda _: [{**ssh, "access": [], "alias": "changed"}])
        r = row(plan_for(backup, current), "resource", "Box")
        assert r.action == UPDATE and r.resource_update == {} and [g.group for g in r.grants] == ["Eng"]
        assert "only its access is restored" in " ".join(r.warnings)

    def test_a_deleted_ssh_resource_is_skipped_and_named(self):
        ssh = {**WIKI, "type": "SSH", "id": "R5", "name": "Box"}
        r = row(plan_for({**healthy(), "resources": [ssh]}, damaged(resources=lambda _: [])), "resource", "Box")
        assert r.action == SKIP and "Gateway" in r.detail


# ---------------------------------------------------------------- access


class TestAccess:
    def test_removed_access_is_given_back(self):
        r = row(plan_for(healthy(), damaged(resources=lambda _: [{**WIKI, "access": [grant(ENG, policy=STRICT)]}])), "resource", "Wiki")
        assert [g.group for g in r.grants] == ["Ops"] and r.grant_updates == []

    def test_changed_grant_settings_are_put_back(self):
        changed = {**WIKI, "access": [grant(ENG, policy=None, approval="AUTOMATIC"), grant(OPS)]}
        r = row(plan_for(healthy(), damaged(resources=lambda _: [changed])), "resource", "Wiki")
        assert r.grants == [] and len(r.grant_updates) == 1
        update = r.grant_updates[0]
        assert (update.group_id, update.policy_id, update.approval_mode) == ("G1", "P1", "MANUAL")

    def test_an_expiry_that_was_added_is_not_removed_but_one_that_was_changed_is_put_back(self):
        future = "2999-01-01T00:00:00Z"
        backup = {**healthy(), "resources": [{**WIKI, "access": [grant(OPS, expires=future)]}]}
        current = damaged(resources=lambda _: [{**WIKI, "access": [grant(OPS, expires="2998-01-01T00:00:00Z")]}])
        r = row(plan_for(backup, current), "resource", "Wiki")
        assert [(u.group, u.expires_at) for u in r.grant_updates] == [("Ops", future)]

    def test_an_expired_grant_is_never_made_permanent(self):
        backup = {**healthy(), "resources": [{**WIKI, "access": [grant(OPS, expires="2020-01-01T00:00:00Z")]}]}
        r = row(plan_for(backup, damaged(resources=lambda _: [{**WIKI, "access": []}])), "resource", "Wiki")
        assert r.grants == [] and any("expired on" in w for w in r.warnings)

    def test_access_for_a_group_that_was_made_again_goes_to_the_new_group_in_the_same_run(self):
        plan = plan_for(healthy(), damaged(groups=lambda g: without(g, "G2"), resources=lambda _: [{**WIKI, "access": [grant(ENG, policy=STRICT)]}]))
        wiki = row(plan, "resource", "Wiki")
        assert [(g.group, g.group_id) for g in wiki.grants] == [("Ops", None)]  # None: apply uses the ID of the group it just created

    def test_access_for_a_group_whose_original_is_gone_for_good_is_a_warning(self):
        backup = {**healthy(), "groups": [dict(ENG), dict(OPS), group(8, "Ghost", type="OTHER")], "resources": [{**WIKI, "access": [grant(group(8, "Ghost"))]}]}
        r = row(plan_for(backup, healthy()), "resource", "Wiki")
        assert r.grants == [] and any("Ghost" in w and "no longer exists" in w for w in r.warnings)

    def test_access_for_a_deleted_synced_group_goes_to_the_one_the_identity_provider_made_again(self):
        old = group(5, "Okta Eng", type="SYNCED")
        new = {**old, "id": "G55"}
        backup = {**healthy(), "groups": [dict(ENG), dict(OPS), old], "resources": [{**WIKI, "access": [grant(old)]}]}
        current = damaged(groups=lambda g: [*g, new], resources=lambda _: [{**WIKI, "access": []}])
        r = row(plan_for(backup, current), "resource", "Wiki")
        assert [(g.group, g.group_id) for g in r.grants] == [("Okta Eng", "G55")]

    def test_a_group_the_backup_describes_but_that_is_gone_is_not_replaced_by_a_group_that_merely_has_its_name(self):
        gone = group(5, "Okta Eng", type="SYNCED")
        backup = {**healthy(), "groups": [dict(ENG), dict(OPS), gone], "resources": [{**WIKI, "access": [grant(gone)]}]}
        current = damaged(groups=lambda g: [*g, group(55, "Okta Eng")], resources=lambda _: [{**WIKI, "access": []}])  # a Manual Group with the name
        r = row(plan_for(backup, current), "resource", "Wiki")
        assert r.grants == [] and any("no longer exists" in w for w in r.warnings)

    def test_without_groups_in_the_backup_access_is_matched_to_groups_by_name(self):
        backup = {"resources": [dict(WIKI)], "remote_networks": [dict(HQ)]}
        current = damaged(resources=lambda _: [{**WIKI, "access": []}])
        r = row(plan_for(backup, current), "resource", "Wiki")
        assert sorted((g.group, g.group_id) for g in r.grants) == [("Eng", "G1"), ("Ops", "G2")]

    def test_a_service_accounts_grant_is_given_back_with_no_settings(self):
        backup = {**healthy(), "resources": [{**WIKI, "access": [grant(SA, kind="ServiceAccount")]}]}
        r = row(plan_for(backup, damaged(resources=lambda _: [{**WIKI, "access": []}])), "resource", "Wiki")
        assert [(g.group, g.group_id, g.kind) for g in r.grants] == [("Bot", "S1", "service account")]

    def test_a_deleted_service_account_is_a_warning(self):
        backup = {**healthy(), "resources": [{**WIKI, "access": [grant(SA, kind="ServiceAccount")]}]}
        current = damaged(resources=lambda _: [{**WIKI, "access": []}], service_accounts=lambda _: [])
        assert any("service account 'Bot' not restored" in w for w in row(plan_for(backup, current), "resource", "Wiki").warnings)

    def test_a_service_account_grant_the_api_would_widen_is_refused(self):
        backup = {**healthy(), "resources": [{**WIKI, "access": [grant(SA, kind="ServiceAccount", expires="2999-01-01T00:00:00Z")]}]}
        r = row(plan_for(backup, damaged(resources=lambda _: [{**WIKI, "access": []}])), "resource", "Wiki")
        assert r.grants == [] and any("wider" in w for w in r.warnings)

    def test_extra_access_stays_unless_prune_is_given(self):
        extra = {**WIKI, "access": [*WIKI["access"], grant(group(3, "Intruders"))]}
        current = damaged(groups=lambda g: [*g, group(3, "Intruders")], resources=lambda _: [extra])
        assert row(plan_for(healthy(), current), "resource", "Wiki").action == EXISTS
        r = row(plan_for(healthy(), current, prune=True), "resource", "Wiki")
        assert (r.action, r.remove_access_ids) == (UPDATE, ["G3"])

    def test_a_grant_whose_policy_is_gone_is_left_out_not_given_without_it(self):
        r = row(plan_for(healthy(), damaged(resources=lambda _: [{**WIKI, "access": [grant(OPS)]}], security_policies=lambda p: [])), "resource", "Wiki")
        assert r.grants == [] and any("Strict" in w for w in r.warnings)


# ---------------------------------------------------------------- what is named as not covered


class TestNotCompared:
    def test_types_restore_does_not_cover_or_the_backup_lacks_are_named(self):
        plan = plan_for(healthy(), healthy())
        text = "; ".join(plan.not_compared)
        assert "users (restore does not cover them yet)" in text
        assert "service accounts (restore does not cover them yet)" in text
        assert "devices (not in this backup)" in text and "gateways (not in this backup)" in text
        assert "groups" not in text and "resources" not in text

    def test_an_older_backup_without_a_covered_type_names_it_and_still_restores_the_rest(self):
        old = {"groups": [dict(ENG)], "remote_networks": [dict(HQ)]}
        plan = plan_for(old, damaged(groups=lambda g: rename(g, "G1", "Oops")))
        assert "resources (not in this backup)" in plan.not_compared
        assert row(plan, "group", "Eng").group_update == {"name": "Eng"}

    def test_a_type_that_could_not_be_read_from_the_tenant_is_named_and_nothing_is_planned_for_it(self):
        current = healthy()
        del current["groups"]
        plan = plan_for(healthy(), current)
        assert "groups (could not be read from the tenant)" in plan.not_compared
        assert not [r for r in plan.rows if r.kind == "group"]


# ---------------------------------------------------------------- applying: the tenant really comes back


def to_api(items: dict) -> FakeApi:
    """A fake tenant holding these items (the same shape the planner reads)."""
    users = items["users"]
    api = FakeApi(
        networks=[dict(n) for n in items["remote_networks"]],
        users=[dict(u) for u in users],
        policies=[{"id": p["id"], "name": p["name"], "policyType": "RESOURCE"} for p in items["security_policies"]],
        service_accounts=[dict(a) for a in items["service_accounts"]],
    )
    api.groups = [
        {"id": g["id"], "name": g["name"], "type": g["type"], "isActive": g.get("isActive", True), "members": {u["id"] for u in g["users"]},
         "securityPolicyId": (g.get("securityPolicy") or {}).get("id")}
        for g in items["groups"]
    ]
    api.resources = []
    for r in items["resources"]:
        entry = {
            "id": r["id"], "name": r["name"], "network": r["remoteNetwork"]["name"], "address": r["address"]["value"], "isActive": r["isActive"],
            "alias": r["alias"], "protocols": r["protocols"], "tags": r["tags"], "isVisible": r["isVisible"],
            "isBrowserShortcutEnabled": r["isBrowserShortcutEnabled"], "approvalMode": r["approvalMode"], "accessPolicy": r["accessPolicy"],
            "securityPolicy": r["securityPolicy"], "routingMode": r["routingMode"], "access": {},
        }
        for g in r["access"]:
            entry["access"][g["principal"]["id"]] = {
                "principalId": g["principal"]["id"], "securityPolicyId": (g["securityPolicy"] or {}).get("id"),
                "accessPolicy": g["accessPolicy"], "approvalMode": g["approvalMode"], "expiresAt": g["expiresAt"],
            }
        api.resources.append(entry)
    api.counter = 100
    return api


def read(api: FakeApi) -> dict:
    """What a backup of the fake tenant would hold, in the shape the planner compares."""
    policies = {p["id"]: p for p in api.policies}
    networks = {n["name"]: n for n in api.networks}
    names = {x["id"]: x["name"] for x in [*api.groups, *api.service_accounts]}
    emails = {u["id"]: u["email"] for u in api.users}
    resources = []
    for r in api.resources:
        detail = resource_detail(r)
        resources.append({
            "id": r["id"], "type": "NETWORK", "name": r["name"], "isActive": r.get("isActive", True),
            "remoteNetwork": {"id": networks[r["network"]]["id"], "name": r["network"]}, "address": {"type": "DNS", "value": r["address"]},
            "approverGroups": [], **detail,
            "access": [
                {"principal": {"type": "ServiceAccount" if p in {a["id"] for a in api.service_accounts} else "Group", "id": p, "name": names[p]},
                 "securityPolicy": {"id": e["securityPolicyId"], "name": policies[e["securityPolicyId"]]["name"]} if e.get("securityPolicyId") else None,
                 "accessPolicy": e.get("accessPolicy") or MANUAL, "approvalMode": e.get("approvalMode", "MANUAL"), "expiresAt": e.get("expiresAt")}
                for p, e in sorted(r["access"].items())
            ],
        })
    return {
        "remote_networks": [{"isActive": True, "location": "AWS", "networkType": "REGULAR", **n} for n in api.networks],
        "groups": [
            {"id": g["id"], "name": g["name"], "type": g["type"], "isActive": g.get("isActive", True), "resources": [],
             "securityPolicy": {"id": g["securityPolicyId"], "name": policies[g["securityPolicyId"]]["name"]} if g.get("securityPolicyId") else None,
             "users": [{"id": u, "email": emails[u]} for u in sorted(g["members"])]}
            for g in api.groups
        ],
        "resources": resources,
        "users": [dict(u) for u in api.users], "security_policies": [{"id": p["id"], "name": p["name"]} for p in api.policies],
        "service_accounts": [dict(a) for a in api.service_accounts],
    }


def rename_network(api: FakeApi, network_id: str, name: str) -> None:
    """What renaming a network does: its resources stay in it."""
    network = next(n for n in api.networks if n["id"] == network_id)
    for res in api.resources:
        if res["network"] == network["name"]:
            res["network"] = name
    network["name"] = name


def restore(api: FakeApi, backup_items: dict, **kw):
    plan = build_plan(backup_of(backup_items), read(api), **kw)
    apply_plan(api, plan.rows)
    return plan


def full_world():
    sa_grant = grant(SA, kind="ServiceAccount")
    other = resource(2, "Docs", DR, [grant(ENG, policy=STRICT, approval="AUTOMATIC", access_policy={"mode": "AUTO_LOCK", "durationSeconds": 86400}), sa_grant])
    items = healthy()
    items["resources"] = [dict(WIKI), other]
    items["users"] = [user(i) for i in range(1, 5)]
    return items


class TestApplyRestoresTheTenant:
    def test_a_healthy_tenant_makes_no_writes(self):
        api = to_api(full_world())
        restore(api, full_world())
        assert api.writes == []

    def test_every_kind_of_damage_at_once_is_repaired_and_a_second_plan_finds_nothing(self):
        world = full_world()
        api = to_api(world)
        # damage: rename, remove a member, change policy, disable, delete a group, delete a network and its resource, edit a resource
        api.groups[0]["name"] = "Engineering"
        api.groups[0]["members"] = {"U1"}
        api.groups[0]["securityPolicyId"] = None
        api.groups[1]["isActive"] = False
        rename_network(api, "N1", "Oops")
        api.resources[0]["name"] = "Hacked"
        api.resources[0]["alias"] = "x.corp"
        api.resources[0]["isVisible"] = False
        api.resources[0]["isActive"] = False
        api.resources[0]["access"] = {}
        del api.resources[1]
        api.networks = [n for n in api.networks if n["id"] != "N2"]
        plan = restore(api, world)
        assert not [r for r in plan.rows if r.status in ("error", "blocked")], [(r.name, r.error or r.detail) for r in plan.rows]
        after = read(api)
        names = lambda key: sorted(i["name"] for i in after[key])  # noqa: E731
        assert names("groups") == ["Eng", "Ops"] and names("remote_networks") == ["DR", "HQ"] and names("resources") == ["Docs", "Wiki"]
        eng = next(g for g in after["groups"] if g["name"] == "Eng")
        assert sorted(u["email"] for u in eng["users"]) == ["u1@x.com", "u2@x.com"] and eng["securityPolicy"]["id"] == "P1"
        assert next(g for g in after["groups"] if g["name"] == "Ops")["isActive"] is True
        wiki = next(r for r in after["resources"] if r["name"] == "Wiki")
        assert (wiki["id"], wiki["isVisible"], wiki["isActive"], len(wiki["access"])) == ("R1", True, True, 2)
        docs = next(r for r in after["resources"] if r["name"] == "Docs")
        assert docs["remoteNetwork"]["name"] == "DR"
        eng_grant = next(g for g in docs["access"] if g["principal"]["name"] == "Eng")
        assert (eng_grant["accessPolicy"], eng_grant["approvalMode"]) == ({"mode": "AUTO_LOCK", "durationSeconds": 86400}, "AUTOMATIC")
        assert sorted(g["principal"]["name"] for g in docs["access"]) == ["Bot", "Eng"]
        again = build_plan(backup_of(world), read(api))
        assert {r.action for r in again.rows} == {EXISTS}, [(r.kind, r.name, r.detail) for r in again.rows if r.action != EXISTS]
        # the alias the backup never had is left as it is (nothing is cleared)
        assert wiki["alias"] == "x.corp"

    def test_a_deleted_group_and_the_access_it_had_come_back_together(self):
        world = full_world()
        api = to_api(world)
        deleted = api.groups.pop(1)  # Ops: no longer a member of anything, no access anywhere
        for r in api.resources:
            r["access"].pop(deleted["id"], None)
        restore(api, world)
        after = read(api)
        ops = next(g for g in after["groups"] if g["name"] == "Ops")
        assert ops["id"] != "G2" and [u["email"] for u in ops["users"]] == ["u3@x.com"]
        wiki = next(r for r in after["resources"] if r["name"] == "Wiki")
        assert ops["id"] in [g["principal"]["id"] for g in wiki["access"]]

    def test_a_deleted_network_is_made_before_the_resource_that_goes_back_into_it(self):
        world = full_world()
        api = to_api(world)
        api.networks = [n for n in api.networks if n["id"] != "N1"]
        api.resources = [r for r in api.resources if r["id"] != "R1"]
        plan = restore(api, world)
        assert [r.kind for r in plan.rows if r.action == CREATE] == ["remote network", "resource"]
        assert [name for name, _ in api.writes][:2] == ["importNetwork", "importResource"]

    def test_a_resource_moved_out_of_a_deleted_network_goes_into_the_network_made_again(self):
        world = full_world()
        api = to_api(world)
        api.networks = [n for n in api.networks if n["id"] != "N1"]
        api.resources[0]["network"] = "DR"
        restore(api, world)
        wiki = next(r for r in read(api)["resources"] if r["id"] == "R1")
        assert wiki["remoteNetwork"]["name"] == "HQ"

    def test_a_deleted_disabled_resource_and_group_come_back_disabled(self):
        world = full_world()
        world["groups"] = [{**ENG, "isActive": False}, dict(OPS)]
        world["resources"] = [{**WIKI, "isActive": False}, world["resources"][1]]
        api = to_api(world)
        api.groups = [g for g in api.groups if g["id"] != "G1"]
        api.resources = [r for r in api.resources if r["id"] != "R1"]
        for r in api.resources:
            r["access"].pop("G1", None)
        restore(api, world)
        after = read(api)
        assert next(g for g in after["groups"] if g["name"] == "Eng")["isActive"] is False
        assert next(r for r in after["resources"] if r["name"] == "Wiki")["isActive"] is False

    def test_prune_takes_out_what_the_backup_does_not_have(self):
        world = full_world()
        api = to_api(world)
        api.groups.append({"id": "G9", "name": "Intruders", "type": "MANUAL", "isActive": True, "members": set(), "securityPolicyId": None})
        api.resources[0]["access"]["G9"] = {"principalId": "G9"}
        api.groups[0]["members"].add("U4")
        restore(api, world, prune=True)
        after = read(api)
        assert [g["principal"]["name"] for g in next(r for r in after["resources"] if r["name"] == "Wiki")["access"]] == ["Eng", "Ops"]
        assert sorted(u["email"] for u in next(g for g in after["groups"] if g["name"] == "Eng")["users"]) == ["u1@x.com", "u2@x.com"]
        assert "Intruders" in [g["name"] for g in after["groups"]]  # an object is never deleted

    def test_nothing_is_deleted_without_prune(self):
        world = full_world()
        api = to_api(world)
        api.groups[0]["members"].add("U4")
        restore(api, world)
        assert "U4" in api.groups[0]["members"]
        assert not [w for w in api.writes if w[0] == "importAccessRemove"]

    def test_a_refused_write_is_reported_on_its_row_and_the_others_still_run(self):
        world = full_world()
        api = to_api(world)
        api.groups[0]["name"] = "Engineering"
        rename_network(api, "N1", "Oops")
        api.fail["importNetworkUpdate"] = "no thanks"
        plan = restore(api, world)
        assert row(plan, "remote network", "HQ").status == "error" and "no thanks" in row(plan, "remote network", "HQ").error
        assert row(plan, "group", "Eng").status == "updated" and api.groups[0]["name"] == "Eng"

    def test_write_requests_are_counted_for_the_dry_run_estimate(self):
        world = full_world()
        api = to_api(world)
        api.groups[0]["name"] = "Engineering"
        rename_network(api, "N1", "Oops")
        api.resources[0]["access"] = {}
        plan = build_plan(backup_of(world), read(api))
        before = write_count(plan.rows)
        api.requests.clear()
        apply_plan(api, plan.rows)
        assert before == len(api.writes) == 3
