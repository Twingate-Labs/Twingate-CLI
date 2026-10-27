"""--sync and --prune: an existing object is brought in line with what the file states, and only with what it states."""

from __future__ import annotations

import json

from tests.importer.fake_api import ALL_PORTS, FakeApi
from tgcli.client.exceptions import TwingateAPIError
from tgcli.importer.apply import apply_plan, write_count
from tgcli.importer.load import AccessSpec, GroupSpec, ResourceSpec, Specs, load
from tgcli.importer.plan import BLOCKED, EXISTS, UPDATE, build_plan
from tgcli.importer.state import State, fetch_state

NETS = [{"id": "N1", "name": "HQ"}]
USERS = [{"id": f"U{i}", "email": f"u{i}@x.com"} for i in range(4)]
POLICIES = [{"id": "P-STRICT", "name": "Strict", "policyType": "RESOURCE"}, {"id": "P-LAX", "name": "Lax", "policyType": "RESOURCE"}]
GROUPS = [
    {"id": "G1", "name": "Eng", "type": "MANUAL"},
    {"id": "G2", "name": "Ops", "type": "MANUAL"},
    {"id": "G3", "name": "Okta", "type": "SYNCED", "members": {"U0"}},
]
ACCOUNTS = [{"id": "S1", "name": "ci"}]
RESTRICTED = {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]}


def api_with(*resources, groups=GROUPS):
    return FakeApi(networks=NETS, users=USERS, policies=POLICIES, groups=groups, service_accounts=ACCOUNTS, resources=[
        {"id": f"R{i}", "network": "HQ", **r} for i, r in enumerate(resources, start=1)
    ])


def rec(name="Wiki", **kw):
    return {"type": "NETWORK", "name": name, "remoteNetwork": {"name": "HQ"}, "address": {"value": f"{name.lower()}.internal"}, **kw}


def principal(name, kind="Group", **kw):
    return {"principal": {"type": kind, "name": name}, **kw}


def go(api, tmp_path, resources=(), groups=(), sync=True, prune=False, execute=True):
    if resources:
        (tmp_path / "resources.json").write_text(json.dumps(list(resources)), encoding="utf-8")
    if groups:
        (tmp_path / "groups.json").write_text(json.dumps(list(groups)), encoding="utf-8")
    specs = load(tmp_path)
    rows = build_plan(specs, fetch_state(api, specs, sync=sync), sync, prune)
    api.requests.clear()
    if execute:
        expected = write_count(rows)
        apply_plan(api, rows)
        if not any(r.error for r in rows):
            assert expected == len(api.writes), "write_count disagrees with what was sent"
    return rows


def only(rows):
    (row,) = rows
    return row


def updates(api):
    return [v for n, v in api.writes if n == "importResourceUpdate"]


def grant(api, resource="R1", principal="G1"):
    return next(r for r in api.resources if r["id"] == resource)["access"][principal]


class TestStatedAndNot:
    def test_a_json_key_states_something_and_a_missing_one_does_not(self, tmp_path):
        (tmp_path / "resources.json").write_text(json.dumps([rec(alias="w", isVisible=False, tags=[], access=[])]), encoding="utf-8")
        (spec,) = load(tmp_path).resources
        assert spec.given == {"alias", "visible", "tags", "access"}

    def test_a_blank_csv_cell_states_nothing_and_a_star_states_all_ports(self, tmp_path):
        (tmp_path / "resources.csv").write_text("name,network,address,alias,tcp_ports,udp_ports,visible,groups\nW,HQ,w.internal,,*,,,\n", encoding="utf-8")
        (spec,) = load(tmp_path).resources
        assert spec.given == {"tcp"}

    def test_a_csv_with_groups_states_the_access_and_one_without_does_not(self, tmp_path):
        (tmp_path / "resources.csv").write_text("name,network,address,groups\nA,HQ,a,Eng\nB,HQ,b,\n", encoding="utf-8")
        a, b = load(tmp_path).resources
        assert "access" in a.given and "access" not in b.given

    def test_json_access_entries_state_only_their_own_settings(self, tmp_path):
        access = [principal("Eng", securityPolicy=None, accessPolicy=None, approvalMode="MANUAL"), principal("Ops", accessPolicy={"mode": "MANUAL"}, expiresAt="2999-01-01T00:00:00Z")]
        (tmp_path / "resources.json").write_text(json.dumps([rec(access=access)]), encoding="utf-8")
        eng, ops = load(tmp_path).resources[0].access
        assert eng.given == {"approval_mode"} and ops.given == {"access_policy", "expires_at"}

    def test_group_members_are_stated_by_a_json_list_even_when_empty_but_not_by_a_blank_cell(self, tmp_path):
        (tmp_path / "groups.json").write_text(json.dumps([{"name": "A", "users": []}, {"name": "B"}]), encoding="utf-8")
        a, b = load(tmp_path).groups
        assert "members" in a.given and "members" not in b.given
        (tmp_path / "groups.json").unlink()
        (tmp_path / "groups.csv").write_text("name,members,security_policy\nA,,\nB,u0@x.com,Strict\n", encoding="utf-8")
        a, b = load(tmp_path).groups
        assert a.given == set() and b.given == {"members", "security_policy"}


class TestResourceSettings:
    def test_without_sync_an_existing_resource_is_left_exactly_as_it_is(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "old"})
        row = only(go(api, tmp_path, [rec(alias="new")], sync=False))
        assert row.action == EXISTS and api.writes == []

    def test_what_differs_is_changed_and_only_that_is_sent(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "old", "isVisible": True, "tags": [{"key": "env", "value": "dev"}]})
        row = only(go(api, tmp_path, [rec(alias="new", isVisible=False, tags=[{"key": "env", "value": "dev"}])]))
        assert row.action == UPDATE and row.status == "updated"
        assert row.detail == "already exists; change alias, visibility"
        assert updates(api) == [{"id": "R1", "alias": "new", "isVisible": False}]
        assert api.resources[0]["alias"] == "new" and api.resources[0]["isVisible"] is False

    def test_a_second_run_finds_nothing_to_do(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "old"})
        go(api, tmp_path, [rec(alias="new", protocols={"allowIcmp": False, "tcp": RESTRICTED, "udp": ALL_PORTS})])
        row = only(go(api, tmp_path, [rec(alias="new", protocols={"allowIcmp": False, "tcp": RESTRICTED, "udp": ALL_PORTS})]))
        assert row.action == EXISTS and api.writes == []

    def test_what_the_file_does_not_state_is_never_touched(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "keep", "isVisible": False, "protocols": {"allowIcmp": False, "tcp": RESTRICTED, "udp": RESTRICTED},
                        "securityPolicy": {"id": "P-STRICT"}})
        (tmp_path / "resources.csv").write_text("name,network,address,alias,tcp_ports,udp_ports,allow_icmp,visible,security_policy\nWiki,HQ,wiki.internal,,,,,,\n", encoding="utf-8")
        row = only(go(api, tmp_path))
        assert row.action == EXISTS and api.writes == []

    def test_a_json_backup_without_a_policy_does_not_take_one_away(self, tmp_path):
        api = api_with({"name": "Wiki", "securityPolicy": {"id": "P-STRICT"}})
        row = only(go(api, tmp_path, [rec(securityPolicy=None, alias=None)]))
        assert row.action == EXISTS and api.resources[0]["securityPolicy"] == {"id": "P-STRICT"}

    def test_only_the_protocol_the_file_states_changes_and_the_rest_is_sent_as_it_is(self, tmp_path):
        api = api_with({"name": "Wiki", "protocols": {"allowIcmp": False, "tcp": ALL_PORTS, "udp": RESTRICTED}})
        (tmp_path / "resources.csv").write_text("name,network,address,tcp_ports\nWiki,HQ,wiki.internal,443\n", encoding="utf-8")
        row = only(go(api, tmp_path))
        assert row.detail == "already exists; change TCP ports"
        assert updates(api) == [{"id": "R1", "protocols": {
            "allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]}, "udp": {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]},
        }}]

    def test_port_order_is_not_a_difference(self, tmp_path):
        two = {"policy": "RESTRICTED", "ports": [{"start": 80, "end": 80}, {"start": 443, "end": 443}]}
        api = api_with({"name": "Wiki", "protocols": {"allowIcmp": True, "tcp": two, "udp": ALL_PORTS}})
        reversed_two = {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}, {"start": 80, "end": 80}]}
        row = only(go(api, tmp_path, [rec(protocols={"allowIcmp": True, "tcp": reversed_two, "udp": ALL_PORTS})]))
        assert row.action == EXISTS

    def test_a_security_policy_is_changed_by_name(self, tmp_path):
        api = api_with({"name": "Wiki", "securityPolicy": {"id": "P-STRICT"}})
        go(api, tmp_path, [rec(securityPolicy={"name": "Lax"})])
        assert updates(api) == [{"id": "R1", "securityPolicyId": "P-LAX"}]

    def test_a_policy_that_does_not_exist_blocks_the_row(self, tmp_path):
        api = api_with({"name": "Wiki"})
        row = only(go(api, tmp_path, [rec(securityPolicy={"name": "Nope"})]))
        assert row.action == BLOCKED and api.writes == []

    def test_changing_the_access_policy_also_sends_the_approval_mode_the_api_would_otherwise_reset(self, tmp_path):
        api = api_with({"name": "Wiki", "approvalMode": "AUTOMATIC"})
        go(api, tmp_path, [rec(accessPolicy={"mode": "AUTO_LOCK", "durationSeconds": 3600})])
        assert updates(api) == [{"id": "R1", "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 3600}, "approvalMode": "AUTOMATIC"}]
        assert api.resources[0]["approvalMode"] == "AUTOMATIC"

    def test_an_access_policy_the_file_states_as_manual_replaces_auto_lock(self, tmp_path):
        api = api_with({"name": "Wiki", "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 60}})
        go(api, tmp_path, [rec(accessPolicy={"mode": "MANUAL"})])
        assert updates(api)[0]["accessPolicy"] == {"mode": "MANUAL"}

    def test_routing_and_browser_shortcut_and_approval_are_compared(self, tmp_path):
        api = api_with({"name": "Wiki"})
        row = only(go(api, tmp_path, [rec(routingMode="BYPASS_TWINGATE", isBrowserShortcutEnabled=False, approvalMode="AUTOMATIC")]))
        assert row.detail == "already exists; change browser shortcut, routing, approval mode"

    def test_tags_are_added_to_and_only_prune_removes_the_others(self, tmp_path):
        mine = {"name": "Wiki", "tags": [{"key": "env", "value": "dev"}, {"key": "team", "value": "a"}]}
        api = api_with(mine)
        go(api, tmp_path, [rec(tags=[{"key": "env", "value": "prod"}])])
        assert sorted((t["key"], t["value"]) for t in updates(api)[0]["tags"]) == [("env", "prod"), ("team", "a")]
        api = api_with(mine)
        go(api, tmp_path, [rec(tags=[{"key": "env", "value": "prod"}])], prune=True)
        assert updates(api)[0]["tags"] == [{"key": "env", "value": "prod"}]

    def test_icmp_and_udp_are_compared_on_their_own(self, tmp_path):
        api = api_with({"name": "Wiki"})
        row = only(go(api, tmp_path, [rec(protocols={"allowIcmp": False})]))
        assert row.detail == "already exists; change ICMP" and updates(api)[0]["protocols"]["allowIcmp"] is False
        api = api_with({"name": "Wiki"})
        row = only(go(api, tmp_path, [rec(protocols={"udp": RESTRICTED})]))
        assert row.detail == "already exists; change UDP ports"

    def test_a_different_auto_lock_duration_is_a_change(self, tmp_path):
        api = api_with({"name": "Wiki", "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 60}})
        go(api, tmp_path, [rec(accessPolicy={"mode": "AUTO_LOCK", "durationSeconds": 3600})])
        assert updates(api)[0]["accessPolicy"]["durationSeconds"] == 3600

    def test_tags_the_file_does_not_state_are_left_alone_even_under_prune(self, tmp_path):
        api = api_with({"name": "Wiki", "tags": [{"key": "env", "value": "dev"}]})
        row = only(go(api, tmp_path, [rec()], prune=True))
        assert row.action == EXISTS and api.writes == []

    def test_a_new_resource_is_created_as_before_with_sync(self, tmp_path):
        api = api_with()
        row = only(go(api, tmp_path, [rec(alias="w")]))
        assert row.status == "created" and [n for n, _ in api.writes] == ["importResource"]

    def test_the_update_comes_before_the_access_is_added(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "old"})
        go(api, tmp_path, [rec(alias="new", access=[principal("Eng")])])
        assert [n for n, _ in api.writes] == ["importResourceUpdate", "importAccess"]

    def test_a_refused_update_is_an_error_row_and_the_access_is_not_attempted(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "old"})
        api.fail["importResourceUpdate"] = "Bypass Resource cannot have a Security Policy"
        row = only(go(api, tmp_path, [rec(alias="new", access=[principal("Eng")])]))
        assert row.status == "error" and "Bypass Resource" in row.error
        assert [n for n, _ in api.writes] == ["importResourceUpdate"]


class TestGrantSettings:
    def edge(self, **kw):
        return {"principalId": "G1", **kw}

    def test_a_grant_whose_policy_differs_is_changed_with_only_that_setting(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge(securityPolicyId="P-STRICT", expiresAt="2999-01-01T00:00:00Z")}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng", securityPolicy={"name": "Lax"})])]))
        assert row.detail == "already exists; access settings to change for 1 group"
        assert api.writes == [("importAccess", {"id": "R1", "access": [{"principalId": "G1", "securityPolicyId": "P-LAX"}]})]
        assert grant(api)["expiresAt"] == "2999-01-01T00:00:00Z"  # not mentioned, so not touched

    def test_a_grant_that_already_matches_sends_nothing(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge(securityPolicyId="P-LAX", approvalMode="AUTOMATIC", expiresAt="2999-01-01T00:00:00Z")}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng", securityPolicy={"name": "Lax"}, approvalMode="AUTOMATIC", expiresAt="2999-01-01T00:00:00+00:00")])]))
        assert row.action == EXISTS and api.writes == []

    def test_a_new_expiry_is_set_but_one_in_the_past_only_warns(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge()}})
        go(api, tmp_path, [rec(access=[principal("Eng", expiresAt="2999-06-01T00:00:00Z")])])
        assert grant(api)["expiresAt"] == "2999-06-01T00:00:00Z"
        api = api_with({"name": "Wiki", "access": {"G1": self.edge()}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng", expiresAt="2001-01-01T00:00:00Z")])]))
        assert api.writes == [] and row.warnings == ["expiry of access for group 'Eng' not changed: it expired on 2001-01-01T00:00:00Z"]

    def test_an_access_policy_stated_as_manual_resets_auto_lock_and_keeps_the_approval_mode(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge(accessPolicy={"mode": "AUTO_LOCK", "durationSeconds": 60}, approvalMode="AUTOMATIC")}})
        go(api, tmp_path, [rec(access=[principal("Eng", accessPolicy={"mode": "MANUAL"})])])
        assert api.writes[0][1]["access"] == [{"principalId": "G1", "accessPolicy": {"mode": "MANUAL"}, "approvalMode": "AUTOMATIC"}]

    def test_without_sync_an_existing_grant_is_left_alone(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge(securityPolicyId="P-STRICT")}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng", securityPolicy={"name": "Lax"})])], sync=False))
        assert row.action == EXISTS and api.writes == []

    def test_a_service_account_that_has_access_is_left_alone(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"S1": {"principalId": "S1"}}})
        row = only(go(api, tmp_path, [rec(access=[principal("ci", "ServiceAccount")])]))
        assert row.action == EXISTS and api.writes == []

    def test_new_grants_and_changed_ones_go_in_the_same_call(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge(securityPolicyId="P-STRICT")}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng", securityPolicy={"name": "Lax"}), principal("Ops")])]))
        assert [n for n, _ in api.writes] == ["importAccess"] and len(api.writes[0][1]["access"]) == 2
        assert row.detail == "already exists; access to add for 1 group; access settings to change for 1 group"

    def test_a_different_approval_mode_is_a_change(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge()}})
        go(api, tmp_path, [rec(access=[principal("Eng", approvalMode="AUTOMATIC")])])
        assert api.writes[0][1]["access"] == [{"principalId": "G1", "approvalMode": "AUTOMATIC"}]

    def test_a_failure_says_that_it_added_or_changed_access(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": self.edge(securityPolicyId="P-STRICT")}})
        api.fail["importAccess"] = "no"
        row = only(go(api, tmp_path, [rec(access=[principal("Eng", securityPolicy={"name": "Lax"})])]))
        assert row.status == "error" and row.error.startswith("added or changed access for 0 of 1 groups, then: no")


class TestGroups:
    def test_a_groups_security_policy_is_changed_when_the_file_states_a_different_one(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "securityPolicyId": "P-STRICT"}, *GROUPS[1:]])
        row = only(go(api, tmp_path, groups=[{"name": "Eng", "securityPolicy": {"name": "Lax"}}]))
        assert row.detail == "already exists; Security Policy to change"
        assert api.writes == [("importGroupSync", {"id": "G1", "securityPolicyId": "P-LAX"})]
        assert api.groups[0]["securityPolicyId"] == "P-LAX"

    def test_a_group_whose_policy_matches_or_is_not_stated_is_left_alone(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "securityPolicyId": "P-LAX"}, *GROUPS[1:]])
        assert only(go(api, tmp_path, groups=[{"name": "Eng", "securityPolicy": {"name": "Lax"}}])).action == EXISTS
        assert only(go(api, tmp_path, groups=[{"name": "Eng"}])).action == EXISTS and api.writes == []

    def test_without_sync_the_policy_is_not_touched(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "securityPolicyId": "P-STRICT"}, *GROUPS[1:]])
        go(api, tmp_path, groups=[{"name": "Eng", "securityPolicy": {"name": "Lax"}}], sync=False)
        assert api.writes == []

    def test_a_synced_group_is_never_changed(self, tmp_path):
        api = api_with()
        row = only(go(api, tmp_path, groups=[{"name": "Okta", "type": "SYNCED", "securityPolicy": {"name": "Lax"}, "users": []}], prune=True))
        assert row.action == "skip" and api.writes == []

    def test_sync_alone_adds_members_but_never_removes_any(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "members": {"U0", "U1"}}, *GROUPS[1:]])
        go(api, tmp_path, groups=[{"name": "Eng", "users": [{"email": "u2@x.com"}]}])
        assert api.groups[0]["members"] == {"U0", "U1", "U2"}

    def test_prune_removes_the_members_the_file_leaves_out(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "members": {"U0", "U1", "U2"}}, *GROUPS[1:]])
        row = only(go(api, tmp_path, groups=[{"name": "Eng", "users": [{"email": "U0@x.com"}, {"email": "u3@x.com"}]}], prune=True))
        assert api.groups[0]["members"] == {"U0", "U3"}
        assert row.detail == "already exists; 1 member to add; 2 members to remove (u1@x.com, u2@x.com)"
        assert [n for n, _ in api.writes] == ["importGroupUsers", "importGroupSync"]  # added before anything is removed

    def test_prune_with_the_members_not_stated_removes_nobody(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "members": {"U0"}}, *GROUPS[1:]])
        (tmp_path / "groups.csv").write_text("name,members,security_policy\nEng,,\n", encoding="utf-8")
        row = only(go(api, tmp_path, prune=True))
        assert row.action == EXISTS and api.groups[0]["members"] == {"U0"}

    def test_a_json_group_stating_no_members_empties_the_group_under_prune(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "members": {"U0", "U1"}}, *GROUPS[1:]])
        go(api, tmp_path, groups=[{"name": "Eng", "users": []}], prune=True)
        assert api.groups[0]["members"] == set()

    def test_removals_and_the_policy_change_share_the_first_call_and_removals_are_batched(self, tmp_path):
        users = [{"id": f"V{i}", "email": f"v{i}@x.com"} for i in range(450)]
        api = FakeApi(networks=NETS, users=users, policies=POLICIES, groups=[{"id": "G1", "name": "Eng", "type": "MANUAL", "members": {u["id"] for u in users}, "securityPolicyId": "P-STRICT"}])
        go(api, tmp_path, groups=[{"name": "Eng", "users": [], "securityPolicy": {"name": "Lax"}}], prune=True)
        sizes = [len(v.get("removedUserIds", ())) for n, v in api.writes]
        assert sizes == [200, 200, 50] and "securityPolicyId" in api.writes[0][1] and "securityPolicyId" not in api.writes[1][1]
        assert api.groups[0]["members"] == set()

    def test_a_failed_removal_says_how_far_it_got(self, tmp_path):
        api = api_with(groups=[{**GROUPS[0], "members": {"U0"}}, *GROUPS[1:]])
        api.fail["importGroupSync"] = "no"
        row = only(go(api, tmp_path, groups=[{"name": "Eng", "users": []}], prune=True))
        assert row.status == "error" and row.error.startswith("removed 0 of 1 members, then: no")


class TestPruneAccess:
    def test_access_the_file_leaves_out_is_removed_after_the_rest_is_added(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}, "S1": {"principalId": "S1"}}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng")])], prune=True))
        assert [n for n, _ in api.writes] == ["importAccess", "importAccessRemove"]
        assert set(api.resources[0]["access"]) == {"G1"}
        assert row.detail == "already exists; access to add for 1 group; access to remove for 2 principals (Ops, ci)"

    def test_sync_alone_never_removes_access(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}}})
        row = only(go(api, tmp_path, [rec(access=[principal("Eng")])]))
        assert "G2" in api.resources[0]["access"] and row.detail == "already exists; access to add for 1 group"

    def test_access_not_stated_is_not_pruned(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}}})
        (tmp_path / "resources.csv").write_text("name,network,address,groups,service_accounts\nWiki,HQ,wiki.internal,,\n", encoding="utf-8")
        assert only(go(api, tmp_path, prune=True)).action == EXISTS and "G2" in api.resources[0]["access"]
        assert only(go(api, tmp_path, [], prune=True)).action == EXISTS

    def test_a_json_resource_without_an_access_key_is_not_pruned(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}}})
        row = only(go(api, tmp_path, [rec()], prune=True))
        assert row.action == EXISTS and "G2" in api.resources[0]["access"]

    def test_an_empty_json_access_list_removes_all_access_under_prune(self, tmp_path):
        (tmp_path / "resources.csv").unlink(missing_ok=True)
        api = api_with({"name": "Wiki", "access": {"G1": {"principalId": "G1"}, "G2": {"principalId": "G2"}}})
        go(api, tmp_path, [rec(access=[])], prune=True)
        assert api.resources[0]["access"] == {}

    def test_a_principal_the_file_names_is_kept_even_when_it_is_not_added(self, tmp_path):
        two = [{"id": "G1", "name": "Eng", "type": "MANUAL"}, {"id": "G9", "name": "Eng", "type": "MANUAL"}]
        api = api_with({"name": "Wiki", "access": {"G1": {"principalId": "G1"}, "G9": {"principalId": "G9"}}}, groups=two)
        row = only(go(api, tmp_path, [rec(access=[principal("Eng")])], prune=True))
        assert set(api.resources[0]["access"]) == {"G1", "G9"} and row.remove_access_ids == []

    def test_a_group_that_expired_in_the_file_is_still_named_so_it_stays(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G1": {"principalId": "G1"}}})
        go(api, tmp_path, [rec(access=[principal("Eng", expiresAt="2001-01-01T00:00:00Z"), principal("Ops")])], prune=True)
        assert set(api.resources[0]["access"]) == {"G1", "G2"}

    def test_nothing_is_ever_deleted_only_access_and_members(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}}}, groups=[{**GROUPS[0], "members": {"U1"}}, *GROUPS[1:]])
        go(api, tmp_path, [rec(access=[principal("Eng")])], groups=[{"name": "Eng", "users": []}], prune=True)
        assert {n for n, _ in api.writes} <= {"importAccess", "importAccessRemove", "importGroupSync", "importGroupUsers", "importResourceUpdate"}
        assert len(api.resources) == 1 and len(api.groups) == 3

    def test_a_failed_add_means_nothing_is_removed(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}}})
        api.fail["importAccess"] = "no"
        row = only(go(api, tmp_path, [rec(access=[principal("Eng")])], prune=True))
        assert row.status == "error" and "G2" in api.resources[0]["access"]

    def test_a_removal_the_api_refuses_is_an_error_row(self, tmp_path):
        api = api_with({"name": "Wiki", "access": {"G2": {"principalId": "G2"}}})
        api.fail["importAccessRemove"] = "no"
        row = only(go(api, tmp_path, [rec(access=[principal("Eng")])], prune=True))
        assert row.status == "error" and row.error.startswith("removed access for 0 of 1 principals, then: no")

    def test_access_beyond_one_page_is_read_in_full(self, tmp_path):
        many = {f"G{i}": {"principalId": f"G{i}"} for i in range(10, 17)}
        groups = [*GROUPS, *[{"id": f"G{i}", "name": f"g{i}", "type": "MANUAL"} for i in range(10, 17)]]
        api = api_with({"name": "Wiki", "access": many}, groups=groups)
        go(api, tmp_path, [rec(access=[principal("Eng")])], prune=True)
        assert set(api.resources[0]["access"]) == {"G1"}


class TestDryRun:
    def test_a_dry_run_plans_the_changes_and_sends_no_write(self, tmp_path):
        api = api_with({"name": "Wiki", "alias": "old", "access": {"G2": {"principalId": "G2"}}})
        row = only(go(api, tmp_path, [rec(alias="new", access=[principal("Eng")])], prune=True, execute=False))
        assert row.action == UPDATE and row.resource_update == {"alias": "new"} and row.remove_access_ids == ["G2"]
        assert api.writes == []

    def test_the_state_is_read_with_the_settings_only_for_a_sync(self, tmp_path):
        (tmp_path / "resources.json").write_text(json.dumps([rec(access=[principal("Eng")])]), encoding="utf-8")
        specs = load(tmp_path)
        api = api_with({"name": "Wiki", "access": {"G1": {"principalId": "G1"}}})
        fetch_state(api, specs)
        assert not any("alias isVisible" in q or "approvalMode expiresAt" in q for q, _ in api.requests)
        api = api_with({"name": "Wiki", "access": {"G1": {"principalId": "G1"}}})
        fetch_state(api, specs, sync=True)
        assert any("alias isVisible" in q for q, _ in api.requests) and any("approvalMode expiresAt" in q for q, _ in api.requests)

    def test_an_api_error_while_reading_the_settings_propagates(self, tmp_path):
        api = api_with({"name": "Wiki"})
        api.raise_on["query"] = TwingateAPIError("boom")
        try:
            go(api, tmp_path, [rec()], execute=False)
        except TwingateAPIError:
            return
        raise AssertionError("expected the error to propagate")


class TestPlanGates:
    """The plan does not rely on the state having been read selectively: it checks what the file states itself."""

    def state(self):
        node = {"id": "R1", "name": "Wiki", "network": "HQ", "address": "a", "alias": None, "isVisible": True, "protocols": None}
        return State(
            networks={"HQ": [NETS[0]]}, groups={"Eng": [GROUPS[0]], "Ops": [GROUPS[1]]}, users={},
            resources={("Wiki", "HQ", "a"): [node]}, resource_access={"R1": {"G2"}}, grants={"R1": {"G2": {"name": "Ops"}}},
            group_members={"G1": {"U0"}}, member_emails={"G1": {"U0": "u0@x.com"}},
        )

    def test_members_that_the_file_does_not_state_are_not_pruned(self):
        rows = build_plan(Specs(groups=[GroupSpec(name="Eng", source="g")]), self.state(), sync=True, prune=True)
        assert only(rows).action == EXISTS

    def test_members_the_file_states_are_pruned(self):
        spec = GroupSpec(name="Eng", source="g", given={"members"})
        assert only(build_plan(Specs(groups=[spec]), self.state(), sync=True, prune=True)).remove_member_ids == ["U0"]

    def test_access_that_the_file_does_not_state_is_not_pruned(self):
        spec = ResourceSpec(name="Wiki", network="HQ", address="a", source="r", access=[AccessSpec("Eng")])
        row = only(build_plan(Specs(resources=[spec]), self.state(), sync=True, prune=True))
        assert row.remove_access_ids == []

    def test_access_the_file_states_is_pruned(self):
        spec = ResourceSpec(name="Wiki", network="HQ", address="a", source="r", access=[AccessSpec("Eng")], given={"access"})
        assert only(build_plan(Specs(resources=[spec]), self.state(), sync=True, prune=True)).remove_access_ids == ["G2"]


class TestCreateSendsAStatedBrowserShortcut:
    """The API turns the browser shortcut ON for a new resource unless told otherwise, so a file that says off must say so."""

    def test_a_stated_false_is_sent_and_a_second_sync_run_finds_nothing(self, tmp_path):
        api = api_with()
        go(api, tmp_path, [rec(isBrowserShortcutEnabled=False)])
        assert api.writes[0][1]["isBrowserShortcutEnabled"] is False
        assert only(go(api, tmp_path, [rec(isBrowserShortcutEnabled=False)])).action == EXISTS

    def test_a_file_that_says_nothing_leaves_it_to_the_api(self, tmp_path):
        api = api_with()
        go(api, tmp_path, [rec()])
        assert "isBrowserShortcutEnabled" not in api.writes[0][1]
