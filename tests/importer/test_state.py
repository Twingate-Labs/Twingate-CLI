"""Reading the tenant's side of an import: only what the file mentions, and only as many requests as needed."""

from __future__ import annotations

import re

from tgcli.importer.load import AccessSpec, GroupSpec, NetworkSpec, ResourceSpec, Specs
from tgcli.importer.state import fetch_state
from tests.importer.fake_api import FakeApi


def grp(name, members=(), policy=None):
    return GroupSpec(name=name, members=list(members), security_policy=policy)


def res(name, network="HQ", access=(), policy=None):
    return ResourceSpec(name=name, network=network, address=f"{name.lower()}.internal", access=[AccessSpec(a) for a in access], security_policy=policy)


def roots(api):
    return [re.search(r"(\w+)\(after: \$cursor, filter", q).group(1) for q, _ in api.lookups]


def test_each_kind_is_looked_up_once_and_kinds_the_file_does_not_name_are_not_looked_up():
    api = FakeApi(networks=[{"id": "N1", "name": "HQ"}])
    fetch_state(api, Specs(networks=[NetworkSpec(name="HQ")], resources=[res("Wiki", "HQ")]))
    assert roots(api) == ["remoteNetworks", "resources"]  # no groups, users or policies named


def test_everything_a_file_names_is_looked_up_exactly_once_per_kind():
    api = FakeApi()
    specs = Specs(
        networks=[NetworkSpec(name="A")], groups=[grp("G", ["a@x.com"], policy="P")],
        resources=[res("R", "B", access=["G", "H"], policy="P")],
    )
    fetch_state(api, specs)
    assert sorted(roots(api)) == ["groups", "remoteNetworks", "resources", "securityPolicies", "users"]
    by_root = dict(zip(roots(api), (v["names"] for _, v in api.lookups)))
    assert by_root["groups"] == ["G", "H"] and by_root["remoteNetworks"] == ["A", "B"] and by_root["securityPolicies"] == ["P"]


def test_emails_are_asked_for_as_written_and_in_lowercase_and_matched_ignoring_case():
    api = FakeApi(users=[{"id": "U1", "email": "ann@x.com"}, {"id": "U2", "email": "Bob@X.com"}])
    state = fetch_state(api, Specs(groups=[grp("G", ["Ann@x.com", "Bob@X.com"])]))
    asked = next(v["names"] for q, v in api.lookups if "users(" in q)
    assert asked == ["Ann@x.com", "Bob@X.com", "ann@x.com", "bob@x.com"]
    assert {k: [n["id"] for n in v] for k, v in state.users.items()} == {"ann@x.com": ["U1"], "bob@x.com": ["U2"]}


def test_long_name_lists_go_in_chunks_and_every_page_of_every_chunk_is_followed():
    names = [f"net-{i}" for i in range(450)]
    api = FakeApi(networks=[{"id": f"N{i}", "name": n} for i, n in enumerate(names)])
    state = fetch_state(api, Specs(networks=[NetworkSpec(name=n) for n in names]))
    chunks = [len(v["names"]) for _, v in api.lookups if v.get("cursor") is None]
    assert chunks == [200, 200, 50]
    assert len(state.networks) == 450  # the fake pages by 2, so this also proves cursors were followed


def test_members_are_read_only_for_existing_manual_groups_that_the_file_gives_members():
    users = [{"id": f"U{i}", "email": f"u{i}@x.com"} for i in range(5)]
    api = FakeApi(
        groups=[{"id": "G1", "name": "Eng", "type": "MANUAL", "members": {f"U{i}" for i in range(5)}},
                {"id": "G2", "name": "Okta", "type": "SYNCED", "members": {"U1"}},
                {"id": "G3", "name": "Quiet", "type": "MANUAL", "members": {"U1"}}],
        users=users,
    )
    specs = Specs(groups=[grp("Eng", ["u0@x.com"]), grp("Okta", ["u0@x.com"]), grp("Quiet"), grp("New", ["u0@x.com"])])
    state = fetch_state(api, specs)
    assert state.group_members == {"G1": {f"U{i}" for i in range(5)}}  # 5 members over pages of 2
    assert len([q for q, _ in api.requests if "group(id: $id)" in q]) == 3  # pages


def test_access_is_read_only_for_existing_resources_that_the_file_gives_access():
    api = FakeApi(
        networks=[{"id": "N1", "name": "HQ"}],
        resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "access": {"G1": {}, "G2": {}, "G3": {}}},
                   {"id": "R2", "name": "Plain", "network": "HQ", "access": {"G1": {}}},
                   {"id": "R3", "name": "Wiki", "network": "Lab", "access": {"G9": {}}}],
    )
    state = fetch_state(api, Specs(resources=[res("Wiki", "HQ", access=["x"]), res("Plain", "HQ"), res("New", "HQ", access=["x"])]))
    assert state.resource_access == {"R1": {"G1", "G2", "G3"}}
    assert set(state.resources) == {("Wiki", "HQ", "wiki.internal"), ("Wiki", "Lab", "wiki.internal"), ("Plain", "HQ", "plain.internal")}  # the other Wiki is found but not matched


def test_access_is_not_read_for_a_resource_with_the_same_name_and_network_but_another_address():
    api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "address": "other.internal", "access": {"G1": {}}}])
    state = fetch_state(api, Specs(resources=[res("Wiki", "HQ", access=["x"])]))
    assert state.resource_access == {} and not [q for q, _ in api.requests if "resource(id: $id)" in q]


def test_a_file_with_nothing_to_look_up_makes_no_requests():
    api = FakeApi()
    fetch_state(api, Specs())
    assert api.requests == []


def test_service_accounts_are_looked_up_by_name_apart_from_groups():
    api = FakeApi(groups=[{"id": "G1", "name": "ops", "type": "MANUAL"}], service_accounts=[{"id": "S1", "name": "ci"}, {"id": "S2", "name": "ops"}])
    access = [AccessSpec("ops"), AccessSpec("ci", kind="service account"), AccessSpec("ops", kind="service account")]
    state = fetch_state(api, Specs(resources=[ResourceSpec(name="R", network="HQ", address="r", access=access)]))
    by_root = dict(zip(roots(api), (v["names"] for _, v in api.lookups)))
    assert by_root["groups"] == ["ops"] and by_root["serviceAccounts"] == ["ci", "ops"]
    assert [n["id"] for n in state.groups["ops"]] == ["G1"] and sorted(state.service_accounts) == ["ci", "ops"]


def test_no_service_account_lookup_when_the_file_names_none():
    api = FakeApi()
    fetch_state(api, Specs(resources=[res("Wiki", access=["Eng"])]))
    assert "serviceAccounts" not in roots(api)
