"""Carrying out a plan: order, exactly what is sent, partial failures, and that a second run finds nothing left to do."""

from __future__ import annotations

import pytest

from tests.importer.fake_api import FakeApi
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.importer.apply import apply_plan, write_count
from tgcli.importer.load import AccessSpec, GroupSpec, NetworkSpec, ResourceSpec, Specs
from tgcli.importer.plan import build_plan
from tgcli.importer.state import fetch_state

PROTOCOLS = {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}
USERS = [{"id": f"U{i}", "email": f"u{i}@x.com"} for i in range(5)]
POLICIES = [{"id": "P-STRICT", "name": "Strict", "policyType": "RESOURCE"}, {"id": "P-LAX", "name": "Lax", "policyType": "RESOURCE"}]


def net(name, **kw):
    return NetworkSpec(source=name, name=name, **kw)


def grp(name, members=(), **kw):
    return GroupSpec(source=name, name=name, members=list(members), **kw)


def res(name, network="HQ", access=(), **kw):
    return ResourceSpec(
        source=name, name=name, network=network, address=f"{name.lower()}.internal", protocols=PROTOCOLS,
        access=[a if isinstance(a, AccessSpec) else AccessSpec(a) for a in access], **kw,
    )


def run(api, specs):
    rows = build_plan(specs, fetch_state(api, specs))
    api.requests.clear()
    apply_plan(api, rows)
    return rows


def statuses(rows):
    return [(r.kind, r.name, r.status) for r in rows]


FULL = Specs(
    networks=[net("HQ", location="AWS", network_type="EXIT")],
    groups=[grp("Eng", ["u0@x.com", "u1@x.com"], security_policy="Strict"), grp("Ops")],
    resources=[res("Wiki", access=["Eng", AccessSpec("Ops", security_policy="Lax")])],
)


class TestCreate:
    def test_everything_is_created_in_dependency_order(self):
        api = FakeApi(users=USERS, policies=POLICIES)
        rows = run(api, FULL)
        assert statuses(rows) == [("remote network", "HQ", "created"), ("group", "Eng", "created"), ("group", "Ops", "created"), ("resource", "Wiki", "created")]
        assert [name for name, _ in api.writes] == ["importNetwork", "importGroup", "importGroupUsers", "importGroup", "importResource", "importAccess"]
        assert all(r.id and not r.error for r in rows)

    def test_a_network_is_created_with_its_settings(self):
        api = FakeApi()
        run(api, Specs(networks=[net("HQ", location="AWS", network_type="EXIT", is_active=False)]))
        assert api.writes == [("importNetwork", {"name": "HQ", "location": "AWS", "networkType": "EXIT", "isActive": False})]

    def test_a_group_gets_its_policy_and_its_members_in_a_separate_call(self):
        api = FakeApi(users=USERS, policies=POLICIES)
        run(api, Specs(groups=[grp("Eng", ["u0@x.com", "u1@x.com"], security_policy="Strict")]))
        assert api.writes[0] == ("importGroup", {"name": "Eng", "securityPolicyId": "P-STRICT"})
        assert api.writes[1] == ("importGroupUsers", {"id": "grp-1", "userIds": ["U0", "U1"]})

    def test_a_group_without_a_policy_or_members_sends_only_its_name(self):
        api = FakeApi()
        run(api, Specs(groups=[grp("Empty")]))
        assert api.writes == [("importGroup", {"name": "Empty"})]

    def test_members_go_in_batches_of_200(self):
        users = [{"id": f"U{i}", "email": f"u{i}@x.com"} for i in range(450)]
        api = FakeApi(users=users)
        run(api, Specs(groups=[grp("Big", [u["email"] for u in users])]))
        assert [len(v["userIds"]) for n, v in api.writes if n == "importGroupUsers"] == [200, 200, 50]
        assert len(api.groups[0]["members"]) == 450

    def test_a_resource_with_only_default_settings_sends_just_the_required_fields(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}])
        run(api, Specs(resources=[res("Wiki")]))
        (name, variables), = api.writes
        assert name == "importResource"
        assert variables == {"name": "Wiki", "address": "wiki.internal", "remoteNetworkId": "N1", "protocols": PROTOCOLS}

    def test_the_default_routing_mode_is_not_sent(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}])
        run(api, Specs(resources=[res("Wiki", routing_mode="THROUGH_TWINGATE")]))
        assert "routingMode" not in api.writes[0][1]

    def test_every_setting_the_file_sets_is_sent(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], policies=POLICIES)
        spec = res(
            "Wiki", alias="wiki.corp", security_policy="Strict", is_visible=False, browser_shortcut=True, routing_mode="BYPASS_TWINGATE",
            tags=[{"key": "env", "value": "prod"}], access_policy={"mode": "AUTO_LOCK", "durationSeconds": 60}, approval_mode="AUTOMATIC",
        )
        spec.protocols = {"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 80, "end": 80}]}, "udp": {"policy": "RESTRICTED", "ports": []}}
        run(api, Specs(resources=[spec]))
        (_, variables), = api.writes
        assert variables == {
            "name": "Wiki", "address": "wiki.internal", "remoteNetworkId": "N1", "protocols": spec.protocols, "alias": "wiki.corp",
            "securityPolicyId": "P-STRICT", "isVisible": False, "isBrowserShortcutEnabled": True, "routingMode": "BYPASS_TWINGATE",
            "tags": [{"key": "env", "value": "prod"}], "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 60}, "approvalMode": "AUTOMATIC",
        }

    def test_access_names_the_groups_by_id_with_per_group_settings_only_where_the_file_has_them(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], policies=POLICIES, groups=[
            {"id": "G1", "name": "Eng", "type": "MANUAL"}, {"id": "G2", "name": "Okta", "type": "SYNCED"}, {"id": "G3", "name": "Ops", "type": "MANUAL"}])
        access = [
            "Eng",
            AccessSpec("Okta", security_policy="Lax"),
            AccessSpec("Ops", access_policy={"mode": "ACCESS_REQUEST"}, approval_mode="MANUAL", expires_at="2999-01-01T00:00:00Z"),
        ]
        run(api, Specs(resources=[res("Wiki", access=access)]))
        (_, variables), = [w for w in api.writes if w[0] == "importAccess"]
        assert variables["access"] == [
            {"principalId": "G1"},
            {"principalId": "G2", "securityPolicyId": "P-LAX"},
            {"principalId": "G3", "accessPolicy": {"mode": "ACCESS_REQUEST"}, "approvalMode": "MANUAL", "expiresAt": "2999-01-01T00:00:00Z"},
        ]

    def test_access_for_a_group_created_by_the_same_run_uses_its_new_id(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}])
        run(api, Specs(groups=[grp("New")], resources=[res("Wiki", access=["New"])]))
        assert api.resources[0]["access"] == {"grp-1": {"principalId": "grp-1"}}

    def test_a_resource_in_a_network_created_by_the_same_run_uses_its_new_id(self):
        api = FakeApi()
        run(api, Specs(networks=[net("HQ")], resources=[res("Wiki")]))
        assert api.resources[0]["variables"]["remoteNetworkId"] == "net-1"

    def test_rows_with_nothing_to_do_send_nothing(self):
        api = FakeApi()
        blocked = res("Orphan", "Nowhere")
        synced = grp("Okta", type="SYNCED")
        rows = run(api, Specs(groups=[synced], resources=[blocked, res("Bastion", type="SSH")]))
        assert api.writes == [] and [r.status for r in rows] == ["skipped", "blocked", "skipped"]

    def test_a_large_grant_list_goes_in_batches_of_100(self):
        groups = [{"id": f"G{i}", "name": f"g{i}", "type": "MANUAL"} for i in range(230)]
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], groups=groups)
        run(api, Specs(resources=[res("Wiki", access=[g["name"] for g in groups])]))
        assert [len(v["access"]) for n, v in api.writes if n == "importAccess"] == [100, 100, 30]


class TestSecondRun:
    def test_running_the_same_import_again_finds_nothing_to_do(self):
        api = FakeApi(users=USERS, policies=POLICIES)
        run(api, FULL)
        before = (len(api.networks), len(api.groups), len(api.resources))
        rows = run(api, FULL)
        assert api.writes == [] and {r.status for r in rows} == {"exists"}
        assert (len(api.networks), len(api.groups), len(api.resources)) == before

    def test_an_interrupted_run_is_completed_by_running_it_again(self):
        api = FakeApi(users=USERS, policies=POLICIES)
        api.fail["importGroupUsers"] = "boom"
        first = run(api, FULL)
        assert [r.status for r in first if r.kind == "group"] == ["error", "created"]
        api.fail.clear()
        second = run(api, FULL)
        assert statuses(second) == [("remote network", "HQ", "exists"), ("group", "Eng", "updated"), ("group", "Ops", "exists"), ("resource", "Wiki", "exists")]
        assert api.groups[0]["members"] == {"U0", "U1"}

    def test_existing_members_and_access_are_never_removed_or_changed(self):
        api = FakeApi(
            users=USERS, networks=[{"id": "N1", "name": "HQ"}],
            groups=[{"id": "G1", "name": "Eng", "type": "MANUAL", "members": {"U4"}}, {"id": "G2", "name": "Ops", "type": "MANUAL"}],
            resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "access": {"G2": {"principalId": "G2", "securityPolicyId": "keep"}}}],
        )
        specs = Specs(groups=[grp("Eng", ["u0@x.com"])], resources=[res("Wiki", access=["Eng", "Ops"])])
        rows = run(api, specs)
        assert [r.status for r in rows] == ["updated", "updated"]
        assert api.groups[0]["members"] == {"U0", "U4"}
        assert api.resources[0]["access"]["G2"] == {"principalId": "G2", "securityPolicyId": "keep"}  # untouched
        assert api.resources[0]["access"]["G1"] == {"principalId": "G1"}
        assert [n for n, _ in api.writes] == ["importGroupUsers", "importAccess"]


class TestFailures:
    def test_a_refused_write_is_recorded_with_the_apis_message_and_the_others_still_run(self):
        api = FakeApi()
        api.fail["importNetwork"] = lambda v: "name taken" if v["name"] == "Bad" else None
        rows = run(api, Specs(networks=[net("Bad"), net("Good")]))
        assert [(r.name, r.status, r.error) for r in rows] == [("Bad", "error", "name taken"), ("Good", "created", "")]

    def test_resources_in_a_network_that_could_not_be_created_fail_with_that_reason(self):
        api = FakeApi()
        api.fail["importNetwork"] = "no"
        rows = run(api, Specs(networks=[net("HQ")], resources=[res("Wiki")]))
        assert [r.status for r in rows] == ["error", "error"] and "Remote Network 'HQ' was not created" in rows[1].error
        assert api.writes == [("importNetwork", api.writes[0][1])]

    def test_access_for_a_group_that_could_not_be_created_is_left_out_but_the_resource_is_made(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], groups=[{"id": "G1", "name": "Eng", "type": "MANUAL"}])
        api.fail["importGroup"] = "no"
        rows = run(api, Specs(groups=[grp("New")], resources=[res("Wiki", access=["New", "Eng"])]))
        assert [r.status for r in rows] == ["error", "created"]
        assert any("'New' not added: the group was not created" in w for w in rows[1].warnings)
        assert list(api.resources[0]["access"]) == ["G1"]

    def test_a_failure_part_way_through_members_says_how_far_it_got_and_keeps_the_group_id(self):
        users = [{"id": f"U{i}", "email": f"u{i}@x.com"} for i in range(450)]
        api = FakeApi(users=users)
        calls = []
        api.fail["importGroupUsers"] = lambda v: calls.append(1) or ("rate limited" if len(calls) == 2 else None)
        (row,) = run(api, Specs(groups=[grp("Big", [u["email"] for u in users])]))
        assert row.status == "error" and row.id == "grp-1"
        assert row.error.startswith("added 200 of 450 members, then: rate limited") and "Run the import again" in row.error

    def test_a_failure_part_way_through_access_says_how_far_it_got(self):
        groups = [{"id": f"G{i}", "name": f"g{i}", "type": "MANUAL"} for i in range(150)]
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], groups=groups)
        calls = []
        api.fail["importAccess"] = lambda v: calls.append(1) or ("nope" if len(calls) == 2 else None)
        (row,) = run(api, Specs(resources=[res("Wiki", access=[g["name"] for g in groups])]))
        assert row.status == "error" and row.error.startswith("added access for 100 of 150 groups, then: nope")

    def test_a_resource_created_but_not_given_access_is_an_error_that_a_rerun_repairs(self):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], groups=[{"id": "G1", "name": "Eng", "type": "MANUAL"}])
        api.fail["importAccess"] = "denied"
        (row,) = run(api, Specs(resources=[res("Wiki", access=["Eng"])]))
        assert row.status == "error" and row.id == "res-1"
        api.fail.clear()
        (again,) = run(api, Specs(resources=[res("Wiki", access=["Eng"])]))
        assert again.status == "updated" and list(api.resources[0]["access"]) == ["G1"]

    def test_an_api_error_on_one_row_does_not_stop_the_rest(self):
        api = FakeApi()
        api.raise_on["importNetwork"] = TwingateAPIError("HTTP 500")
        rows = run(api, Specs(networks=[net("A")], groups=[grp("G")]))
        assert [(r.status, r.error) for r in rows] == [("error", "HTTP 500"), ("created", "")]

    def test_rejected_credentials_stop_the_run_and_mark_what_was_not_attempted(self):
        api = FakeApi()
        api.raise_on["importGroup"] = TwingateAuthError("bad token")
        rows = run(api, Specs(networks=[net("A")], groups=[grp("G1"), grp("G2"), grp("Okta", type="SYNCED")], resources=[res("Wiki", "A")]))
        assert [(r.name, r.status) for r in rows] == [("A", "created"), ("G1", "error"), ("G2", "not-run"), ("Okta", "skipped"), ("Wiki", "not-run")]
        assert "authentication error: bad token" in rows[1].error and "not attempted" in rows[2].error
        assert len([w for w in api.writes if w[0] == "importGroup"]) == 1

    def test_a_reply_of_an_unexpected_shape_is_an_error_on_that_row_not_a_crash(self):
        api = FakeApi()
        original = api.execute
        api.execute = lambda q, v=None: {"data": {}} if "importGroup" in q else original(q, v)
        rows = run(api, Specs(groups=[grp("G")], networks=[net("A")]))
        assert [r.status for r in rows] == ["created", "error"] and rows[1].error.startswith("unexpected KeyError")

    @pytest.mark.parametrize("error", [None, "", "  "])
    def test_an_ok_false_reply_without_a_message_still_reports_something(self, error):
        api = FakeApi()
        api.execute = lambda q, v=None: {"data": {"groupCreate": {"ok": False, "error": error, "entity": None}}}
        (row,) = run_rows(api, Specs(groups=[grp("G")]))
        assert row.status == "error" and row.error == "groupCreate was refused without a reason"


def run_rows(api, specs):
    """Like run(), but the plan is built from an empty tenant so a fake that answers every query the same way is enough."""
    rows = build_plan(specs, fetch_state(FakeApi(), specs))
    apply_plan(api, rows)
    return rows


class TestWriteCount:
    def test_it_matches_the_writes_a_run_actually_makes(self):
        users = [{"id": f"U{i}", "email": f"u{i}@x.com"} for i in range(450)]
        groups = [{"id": f"G{i}", "name": f"g{i}", "type": "MANUAL"} for i in range(230)]
        api = FakeApi(users=users, groups=groups, policies=POLICIES, networks=[{"id": "N9", "name": "Old"}],
                      resources=[{"id": "R9", "name": "Old res", "network": "Old", "access": {}}])
        specs = Specs(
            networks=[net("HQ"), net("Old")],
            groups=[grp("Big", [u["email"] for u in users]), grp("Small", ["u0@x.com"]), grp("g1", ["u1@x.com"])],
            resources=[res("Wiki", access=[g["name"] for g in groups] + ["Big"]), res("Old res", "Old", access=["g1"]), res("Quiet", "Old")],
        )
        rows = build_plan(specs, fetch_state(api, specs))
        expected = write_count(rows)
        api.requests.clear()
        apply_plan(api, rows)
        assert expected == len(api.writes) and expected > 0

    def test_rows_with_nothing_to_do_count_for_nothing(self):
        assert write_count(build_plan(Specs(resources=[res("Orphan", "Nowhere")]), fetch_state(FakeApi(), Specs()))) == 0


@pytest.mark.parametrize("action,status", [("create", "created"), ("update", "updated"), ("exists", "exists"), ("skip", "skipped"), ("blocked", "blocked")])
def test_every_planned_action_has_a_finished_status(action, status):
    from tgcli.importer.apply import DONE_STATUS, DRY_RUN_STATUS
    assert DONE_STATUS[action] == status and DRY_RUN_STATUS[action] in (f"would-{action}", status)
