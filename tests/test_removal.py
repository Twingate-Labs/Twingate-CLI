"""Remove: reading the file, what the plan says for each situation, and that the deletes go out in the right order."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError, TwingateThrottleError
from tgcli.removal import (
    BLOCKED, ERROR, GROUP, NETWORK, NOT_RUN, REMOVE, REMOVED, RESOURCE, SKIP, LoadError, Target, apply_plan, build_plan, counts, kind_of, load_targets,
)


def grant(principal_id, kind="Group"):
    return {"principal": {"type": kind, "id": principal_id, "name": principal_id}}


def res(i, name, network, access=(), address=None, type="NETWORK", approvers=()):
    return {
        "id": f"R{i}", "type": type, "name": name, "remoteNetwork": {"id": network["id"], "name": network["name"]},
        "address": {"type": "DNS", "value": address or f"{name.lower()}.internal"}, "access": [grant(a) for a in access],
        "approverGroups": [{"id": a, "name": a} for a in approvers],
    }


def grp(i, name, type="MANUAL", members=2, resources=()):
    return {"id": f"G{i}", "name": name, "type": type, "users": [{"id": f"U{n}", "email": f"u{n}@x.com"} for n in range(members)], "resources": [{"id": r, "name": r} for r in resources]}


def net(i, name, resources=(), connectors=(), gateways=()):
    return {
        "id": f"N{i}", "name": name, "resources": [{"id": r, "name": r} for r in resources],
        "connectors": [{"id": c, "name": c} for c in connectors], "gateways": [{"id": g, "address": g} for g in gateways],
    }


HQ, DR = net(1, "HQ", resources=["R1", "R2"], connectors=["C1"]), net(2, "DR", resources=["R3"])
WORLD = {
    "remote_networks": [HQ, DR],
    "groups": [
        grp(1, "Eng", resources=["R1", "R2"]), grp(2, "Ops", resources=["R1"]), grp(3, "Okta Staff", type="SYNCED", members=50), grp(4, "Everyone", type="SYSTEM"),
    ],
    "resources": [
        res(1, "Wiki", HQ, ["G1", "G2"]), res(2, "Git", HQ, ["G1"]), res(3, "Docs", DR, ["G1"]),
        res(4, "Docs", HQ, ["G2"], address="docs2.internal"),
    ],
}


def plan(*lines, world=None):
    """lines: (kind, id, name) tuples; returns the rows keyed by (kind, name) for the removals and others."""
    targets = [Target(kind, id=i, name=n, source=f"line {k}") for k, (kind, i, n) in enumerate(lines, start=1)]
    return build_plan(targets, WORLD if world is None else world)


def one(*lines, world=None):
    rows = plan(*lines, world=world)
    assert len(rows) == 1, rows
    return rows[0]


# ---------------------------------------------------------------- reading the file


class TestLoad:
    def write(self, tmp_path, name, text):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_csv_with_a_kind_column(self, tmp_path):
        targets = load_targets(self.write(tmp_path, "x.csv", "kind,id,name,network,address\ngroup,,Old,,\nresource,,Docs,HQ,docs2.internal\nnetwork,N2,,,\n"))
        assert [(t.kind, t.id, t.name, t.network, t.address) for t in targets] == [
            ("group", "", "Old", "", ""), ("resource", "", "Docs", "HQ", "docs2.internal"), ("remote network", "N2", "", "", "")]
        assert not any(t.problems for t in targets)

    def test_kind_spellings_and_header_case(self, tmp_path):
        targets = load_targets(self.write(tmp_path, "x.csv", "Kind,Name\nRemote Network,A\nremote-network,B\nnetworks,C\nGROUP,D\n"))
        assert [t.kind for t in targets] == ["remote network"] * 3 + ["group"]

    def test_a_csv_without_a_kind_uses_the_default_kind(self, tmp_path):
        targets = load_targets(self.write(tmp_path, "x.csv", "name\nA\n"), kind_of("group"))
        assert targets[0].kind == "group" and not targets[0].problems

    def test_a_csv_without_a_kind_and_no_default_is_a_problem_not_a_guess(self, tmp_path):
        target = load_targets(self.write(tmp_path, "x.csv", "name\nA\n"))[0]
        assert "no kind" in target.problems[0]

    def test_an_unknown_kind_and_a_line_with_nothing_to_go_on_are_problems(self, tmp_path):
        targets = load_targets(self.write(tmp_path, "x.csv", "kind,id,name\nconnector,,C1\ngroup,,\n"))
        assert "not one of resource, group or network" in targets[0].problems[0]
        assert "neither an id nor a name" in targets[1].problems[0]

    def test_blank_csv_lines_are_ignored(self, tmp_path):
        assert len(load_targets(self.write(tmp_path, "x.csv", "kind,name\ngroup,A\n,\n"))) == 1

    def test_json(self, tmp_path):
        path = self.write(tmp_path, "x.json", json.dumps([{"kind": "group", "name": "A"}, {"type": "network", "id": "N1"}, 5]))
        targets = load_targets(path)
        assert [(t.kind, t.name, t.id) for t in targets[:2]] == [("group", "A", ""), ("remote network", "", "N1")]
        assert targets[2].problems == ["not an object"]

    def test_json_that_is_not_a_list_is_an_error(self, tmp_path):
        with pytest.raises(LoadError, match="list of objects"):
            load_targets(self.write(tmp_path, "x.json", '{"kind": "group"}'))

    def test_broken_json_is_an_error(self, tmp_path):
        with pytest.raises(LoadError, match="not valid JSON"):
            load_targets(self.write(tmp_path, "x.json", "[{"))

    def test_a_plain_list_needs_a_kind(self, tmp_path):
        path = self.write(tmp_path, "ids.txt", "# these\nG1\n\nOld group\n")
        assert all(t.problems for t in load_targets(path))
        targets = load_targets(path, kind_of("group"))
        assert [t.id for t in targets] == ["G1", "Old group"] and not any(t.problems for t in targets)

    def test_an_empty_file_is_an_error(self, tmp_path):
        with pytest.raises(LoadError, match="names nothing"):
            load_targets(self.write(tmp_path, "x.csv", "kind,name\n"))

    def test_a_missing_file_is_an_error(self, tmp_path):
        with pytest.raises(LoadError, match="cannot read"):
            load_targets(tmp_path / "nope.csv")

    def test_a_utf16_file_from_powershell_is_read(self, tmp_path):
        path = tmp_path / "x.csv"
        path.write_bytes("kind,name\ngroup,Café\n".encode("utf-16"))
        assert load_targets(path)[0].name == "Café"

    def test_a_file_that_is_not_text_is_an_error(self, tmp_path):
        path = tmp_path / "x.csv"
        path.write_bytes(b"\xff\xfe\x00\x81\x82")
        with pytest.raises(LoadError):
            load_targets(path)


# ---------------------------------------------------------------- matching


class TestMatching:
    def test_a_name_matches_exactly_and_by_case(self):
        assert one((GROUP, "", "Ops")).action == REMOVE
        assert one((GROUP, "", "ops")).action == SKIP

    def test_an_id_matches_with_no_name(self):
        row = one((GROUP, "G2", ""))
        assert row.action == REMOVE and row.name == "Ops" and row.id == "G2"

    def test_an_id_whose_object_has_another_name_blocks(self):
        row = one((GROUP, "G2", "Eng"))
        assert row.action == BLOCKED and "is 'Ops', not 'Eng'" in row.reason

    def test_an_id_and_the_right_name_is_fine(self):
        assert one((GROUP, "G2", "Ops")).action == REMOVE

    def test_a_missing_object_is_skipped_not_blocked(self):
        row = one((GROUP, "", "Never existed"))
        assert row.action == SKIP and "not found" in row.reason

    def test_a_name_used_twice_blocks_and_lists_the_candidates(self):
        row = one((RESOURCE, "", "Docs"))
        assert row.action == BLOCKED and "matches 2 resources" in row.reason and "R3" in row.reason and "R4" in row.reason and "DR" in row.reason

    def test_the_network_or_address_narrows_a_resource_name(self):
        assert one((RESOURCE, "", "Docs"), world=WORLD).action == BLOCKED
        targets = [Target(RESOURCE, name="Docs", network="DR")]
        row = build_plan(targets, WORLD)[0]
        assert row.action == REMOVE and row.id == "R3"
        row = build_plan([Target(RESOURCE, name="Docs", address="docs2.internal")], WORLD)[0]
        assert row.action == REMOVE and row.id == "R4"

    def test_an_id_beats_a_duplicate_name(self):
        row = one((RESOURCE, "R4", "Docs"))
        assert row.action == REMOVE and row.id == "R4"

    def test_a_group_name_is_not_a_resource_name(self):
        assert one((RESOURCE, "", "Eng")).action == SKIP

    def test_the_same_object_named_twice_is_one_row(self):
        rows = plan((GROUP, "", "Ops"), (GROUP, "G2", ""), (GROUP, "", "Ops"))
        assert len(rows) == 1

    def test_an_unreadable_line_blocks_with_its_reason_and_source(self):
        rows = build_plan([Target("", name="x", source="f.csv row 7", problems=["no kind given"])], WORLD)
        assert rows[0].action == BLOCKED and rows[0].reason == "no kind given" and rows[0].source == "f.csv row 7"

    def test_every_kind_is_looked_for_only_among_its_own(self):
        assert one((NETWORK, "", "Eng")).action == SKIP

    def test_the_world_having_no_such_collection_is_just_not_found(self):
        assert one((GROUP, "", "Ops"), world={}).action == SKIP


# ---------------------------------------------------------------- safety rules


class TestRules:
    def test_synced_groups_are_never_removed(self):
        row = one((GROUP, "", "Okta Staff"))
        assert row.action == BLOCKED and "identity provider" in row.reason

    def test_the_system_group_is_never_removed(self):
        assert one((GROUP, "", "Everyone")).action == BLOCKED

    def test_a_group_of_unknown_type_is_not_removed(self):
        world = {**WORLD, "groups": [{"id": "G9", "name": "Odd", "users": [], "resources": []}]}
        assert one((GROUP, "", "Odd"), world=world).action == BLOCKED

    def test_a_network_with_resources_not_in_the_file_is_blocked(self):
        row = one((NETWORK, "", "DR"))
        assert row.action == BLOCKED and "1 resource still in it" in row.reason and "R3" in row.reason

    def test_a_network_goes_when_all_its_resources_are_in_the_file(self):
        rows = plan((NETWORK, "", "DR"), (RESOURCE, "R3", ""))
        assert [(r.kind, r.action) for r in rows] == [(RESOURCE, REMOVE), (NETWORK, REMOVE)]
        assert "all of them in the file" in rows[1].detail

    def test_a_network_with_a_connector_is_blocked_even_when_its_resources_go(self):
        rows = plan((NETWORK, "", "HQ"), (RESOURCE, "R1", ""), (RESOURCE, "R2", ""), (RESOURCE, "R4", ""))
        network = [r for r in rows if r.kind == NETWORK][0]
        assert network.action == BLOCKED and "1 Connector" in network.reason and "C1" in network.reason and "R1" not in network.reason

    def test_a_network_with_a_gateway_is_blocked(self):
        world = {**WORLD, "remote_networks": [net(5, "GW", gateways=["gw1"])]}
        row = one((NETWORK, "", "GW"), world=world)
        assert row.action == BLOCKED and "1 Gateway" in row.reason

    def test_an_empty_network_goes(self):
        world = {**WORLD, "remote_networks": [net(5, "Empty")]}
        row = one((NETWORK, "", "Empty"), world=world)
        assert row.action == REMOVE and "nothing in it" in row.detail

    def test_a_long_list_of_leftovers_is_cut_short(self):
        big = net(6, "Big", resources=[f"X{i}" for i in range(9)])
        row = one((NETWORK, "", "Big"), world={**WORLD, "remote_networks": [big]})
        assert "9 resources" in row.reason and "..." in row.reason and "X5" not in row.reason

    def test_resources_go_before_groups_before_networks_whatever_the_file_order(self):
        rows = plan((NETWORK, "", "DR"), (GROUP, "", "Ops"), (RESOURCE, "R3", ""))
        assert [r.kind for r in rows] == [RESOURCE, GROUP, NETWORK]

    def test_blocked_and_skipped_lines_are_kept_in_the_list(self):
        rows = plan((GROUP, "", "Ops"), (GROUP, "", "Okta Staff"), (GROUP, "", "Nope"))
        assert sorted(r.action for r in rows) == [BLOCKED, REMOVE, SKIP]


# ---------------------------------------------------------------- consequences shown in the list


class TestConsequences:
    def test_a_resource_says_where_it_is_and_who_loses_access(self):
        row = one((RESOURCE, "R1", ""))
        assert row.detail == "resource wiki.internal in network 'HQ'; access for 2 groups or service accounts is removed with it"

    def test_one_grant_is_singular(self):
        assert "access for 1 group or service account is removed" in one((RESOURCE, "R2", "")).detail

    def test_a_resource_nobody_can_reach_says_so(self):
        world = {**WORLD, "resources": [res(9, "Orphan", HQ)]}
        assert "nobody has access to it" in one((RESOURCE, "R9", ""), world=world).detail

    def test_other_resource_types_are_named(self):
        world = {**WORLD, "resources": [res(7, "Box", HQ, type="SSH")]}
        assert one((RESOURCE, "R7", ""), world=world).detail.startswith("SSH resource")

    def test_a_group_says_its_members_and_its_resources(self):
        row = one((GROUP, "", "Eng"))
        assert "2 members lose what it gave them" in row.detail and "access to 3 resources" not in row.detail

    def test_a_group_with_one_member_is_singular(self):
        world = {**WORLD, "groups": [grp(8, "Solo", members=1)]}
        assert "1 member lose" in one((GROUP, "", "Solo"), world=world).detail

    def test_a_resource_left_with_nobody_is_called_out(self):
        # Git (R2) is reachable only through Eng; removing Eng strands it.
        row = one((GROUP, "", "Eng"))
        assert "resources would be left with nobody" in row.detail or "resource would be left with nobody" in row.detail

    def test_it_is_not_stranded_when_another_group_still_has_it(self):
        world = {**WORLD, "resources": [res(2, "Git", HQ, ["G1", "G2"])], "groups": [grp(1, "Eng", resources=["R2"]), grp(2, "Ops")]}
        assert "left with nobody" not in one((GROUP, "", "Eng"), world=world).detail

    def test_it_is_not_stranded_when_the_resource_goes_too(self):
        rows = plan((GROUP, "", "Eng"), (RESOURCE, "R2", ""), (RESOURCE, "R1", ""), (RESOURCE, "R3", ""))
        group = [r for r in rows if r.kind == GROUP][0]
        assert "left with nobody" not in group.detail

    def test_it_is_stranded_when_everyone_who_could_reach_it_is_removed(self):
        rows = plan((GROUP, "", "Eng"), (GROUP, "", "Ops"))
        assert all("left with nobody" in r.detail for r in rows if r.name == "Eng")

    def test_a_group_that_approves_requests_says_so(self):
        world = {**WORLD, "resources": [res(1, "Wiki", HQ, ["G1"], approvers=["G2"])]}
        assert "approves access requests for 1 resource" in one((GROUP, "", "Ops"), world=world).detail

    def test_it_does_not_mention_approving_a_resource_that_goes_too(self):
        world = {**WORLD, "resources": [res(1, "Wiki", HQ, ["G1"], approvers=["G2"])]}
        rows = plan((GROUP, "", "Ops"), (RESOURCE, "R1", ""), world=world)
        assert "approves" not in [r for r in rows if r.kind == GROUP][0].detail


# ---------------------------------------------------------------- applying


class FakeClient:
    def __init__(self, refuse=(), raise_for=None):
        self.calls: list = []
        self.refuse, self.raise_for = dict.fromkeys(refuse, "no way"), raise_for

    def execute(self, query, variables=None):
        key = next(iter(variables.values()))
        self.calls.append((query.split("{")[1].split("(")[0].strip(), key))
        if self.raise_for and key in self.raise_for:
            raise self.raise_for[key]
        name = query.split("{")[1].split("(")[0].strip()
        if key in self.refuse:
            return {"data": {name: {"ok": False, "error": self.refuse[key]}}}
        return {"data": {name: {"ok": True, "error": None}}}


class TestApply:
    def test_the_right_mutation_goes_out_for_each_kind_in_order(self):
        rows = plan((NETWORK, "", "DR"), (GROUP, "", "Ops"), (RESOURCE, "R3", ""))
        client = FakeClient()
        apply_plan(client, rows)
        assert client.calls == [("resourceDelete", "R3"), ("groupDelete", "G2"), ("remoteNetworkDelete", "N2")]
        assert [r.status for r in rows] == [REMOVED] * 3

    def test_only_remove_rows_are_sent(self):
        rows = plan((GROUP, "", "Ops"), (GROUP, "", "Okta Staff"), (GROUP, "", "Nope"))
        client = FakeClient()
        apply_plan(client, rows)
        assert client.calls == [("groupDelete", "G2")]
        assert sorted(r.status for r in rows) == ["blocked", "not-found", REMOVED]

    def test_a_refusal_is_recorded_and_the_rest_carry_on(self):
        rows = plan((RESOURCE, "R1", ""), (RESOURCE, "R2", ""), (GROUP, "", "Ops"))
        client = FakeClient(refuse=["R1"])
        apply_plan(client, rows)
        assert [(r.name, r.status) for r in rows] == [("Wiki", ERROR), ("Git", REMOVED), ("Ops", REMOVED)]
        assert rows[0].error == "no way"

    def test_a_network_is_not_attempted_when_a_resource_of_it_failed(self):
        rows = plan((NETWORK, "", "DR"), (RESOURCE, "R3", ""))
        client = FakeClient(refuse=["R3"])
        apply_plan(client, rows)
        assert ("remoteNetworkDelete", "N2") not in client.calls
        assert [r.status for r in rows] == [ERROR, NOT_RUN]

    def test_a_network_is_still_attempted_when_the_failure_was_in_another_network(self):
        world = {**WORLD, "remote_networks": [net(1, "A", resources=["R1"]), net(2, "B", resources=["R3"])]}
        rows = plan((NETWORK, "", "B"), (RESOURCE, "R1", ""), (RESOURCE, "R3", ""), world=world)
        client = FakeClient(refuse=["R1"])
        apply_plan(client, rows)
        assert ("remoteNetworkDelete", "N2") in client.calls

    def test_an_api_error_about_one_object_is_recorded(self):
        rows = plan((RESOURCE, "R1", ""), (RESOURCE, "R2", ""))
        client = FakeClient(raise_for={"R1": TwingateAPIError("boom")})
        apply_plan(client, rows)
        assert [(r.status, r.error) for r in rows] == [(ERROR, "boom"), (REMOVED, "")]

    @pytest.mark.parametrize("exc", [TwingateThrottleError("slow down"), TwingateAuthError("bad key")])
    def test_being_rate_limited_out_or_logged_out_stops_the_run(self, exc):
        rows = plan((RESOURCE, "R1", ""), (RESOURCE, "R2", ""))
        client = FakeClient(raise_for={"R1": exc})
        with pytest.raises(type(exc)):
            apply_plan(client, rows)
        assert client.calls == [("resourceDelete", "R1")]

    def test_a_response_with_no_result_is_an_error_not_a_success(self):
        class Silent:
            def execute(self, query, variables=None):
                return {"data": {}}

        rows = plan((GROUP, "", "Ops"))
        apply_plan(Silent(), rows)
        assert rows[0].status == ERROR and "did not say why" in rows[0].error

    def test_progress_is_reported_per_removal(self):
        seen = []
        apply_plan(FakeClient(), plan((GROUP, "", "Ops"), (RESOURCE, "R3", "")), progress=lambda row: seen.append(row.name))
        assert seen == ["Docs", "Ops"]

    def test_counts(self):
        rows = plan((GROUP, "", "Ops"), (RESOURCE, "R3", ""), (GROUP, "", "Okta Staff"))
        assert counts(rows) == {RESOURCE: 1, GROUP: 1}


class TestTemplate:
    TEMPLATE = Path(__file__).resolve().parents[1] / "examples" / "remove" / "remove.csv"

    def test_the_template_has_the_columns_remove_reads_and_names_nothing(self):
        import csv

        with open(self.TEMPLATE, newline="", encoding="utf-8") as handle:
            assert next(csv.reader(handle)) == ["kind", "id", "name", "network", "address"]
        with pytest.raises(LoadError, match="names nothing"):
            load_targets(self.TEMPLATE)

    def test_a_copy_with_the_documented_example_lines_reads_clean(self, tmp_path):
        path = tmp_path / "r.csv"
        path.write_text("kind,id,name,network,address\ngroup,,Contractors 2024,,\nresource,,Wiki,HQ,wiki.internal\nnetwork,,Old Datacentre,,\n", encoding="utf-8")
        targets = load_targets(path)
        assert [(t.kind, t.name) for t in targets] == [("group", "Contractors 2024"), ("resource", "Wiki"), ("remote network", "Old Datacentre")]
        assert not any(t.problems for t in targets)
