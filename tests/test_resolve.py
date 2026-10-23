"""Names as well as IDs: an ID passes through untouched, anything else is looked up by exact name, and never guessed."""

from __future__ import annotations

import base64
import re

import pytest

from tgcli.client.exceptions import TwingateAPIError
from tgcli.resolve import GROUP, NETWORK, POLICY, SERVICE_ACCOUNT, ResolveError, looks_like_id, resolve


def make_id(kind: str, number) -> str:
    return base64.b64encode(f"{kind}:{number}".encode()).decode()


class TestLooksLikeId:
    @pytest.mark.parametrize("kind,number", [
        ("Group", 77817), ("Group", 1), ("RemoteNetwork", 12345678), ("SecurityPolicy", 61870), ("Resource", 3775231),
        ("ServiceAccount", "6f8f57ce-63e1-4a43-9a0b-3c1f1d9a2b77"), ("User", 191692), ("Device", 2381009),
    ])
    def test_real_shaped_ids(self, kind, number):
        assert looks_like_id(make_id(kind, number))

    @pytest.mark.parametrize("value", [
        "Everyone", "Contractors", "Trainees", "Licenses", "Team", "Admins", "DBAs", "Floor1", "Dev", "AWS Apps",
        "Cloud Applications", "Default Policy", "Okta App Users Group", "Ops, EMEA", "Engineering", "My Network 2",
        "Ελληνικά", "日本語", "", " ", "====", "a", "abcd", "AAAA", "R3JvdXA6", "R3JvdXA6MQ==\n", " R3JvdXA6MQ==",
        "R3JvdXA6MQ=", "R3JvdXA6MQ===", base64.b64encode(b"hello world").decode(), base64.b64encode(b"no colon here").decode(),
        base64.b64encode(b"Group:").decode(), base64.b64encode(b"Group: 1").decode(), base64.b64encode(b"\xff\xfe:1").decode(),
    ])
    def test_names_and_malformed_values_are_not_ids(self, value):
        assert not looks_like_id(value)

    def test_a_name_that_is_not_valid_base64_is_not_an_id_even_with_the_right_length(self):
        assert not looks_like_id("Team")  # four characters, valid alphabet, but decodes to bytes with no "Type:value"


PAGE = 2


class FakeClient:
    """A tenant with named objects, answering the name-lookup query the way the API does (exact match, `in`, paged)."""

    def __init__(self, **tenant):
        self.tenant = tenant
        self.page = PAGE
        self.requests: list[tuple[str, dict]] = []
        self.error: Exception | None = None

    def execute(self, query: str, variables: dict | None = None) -> dict:
        variables = variables or {}
        self.requests.append((query, variables))
        if self.error:
            raise self.error
        root = re.search(r"(\w+)\(after: \$cursor, filter: \{name: \{in: \$names\}\}\)", query).group(1)
        hits = [o for o in self.tenant.get(root, []) if o["name"] in variables["names"]]
        start = 0 if variables["cursor"] is None else int(variables["cursor"][1:])
        more = start + self.page < len(hits)
        return {"data": {root: {
            "pageInfo": {"hasNextPage": more, "endCursor": f"c{start + self.page}" if more else None},
            "edges": [{"node": o} for o in hits[start : start + self.page]],
        }}}


def obj(kind, number, name):
    return {"id": make_id(kind, number), "name": name}


@pytest.fixture
def tenant():
    return FakeClient(
        groups=[obj("Group", 1, "Eng"), obj("Group", 2, "Ops"), obj("Group", 3, "Sales"), obj("Group", 4, "Dup"), obj("Group", 5, "Dup"), obj("Group", 6, "ops")],
        remoteNetworks=[obj("RemoteNetwork", 1, "Cloud Applications"), obj("RemoteNetwork", 2, "Office")],
        securityPolicies=[obj("SecurityPolicy", 1, "Default Policy"), obj("SecurityPolicy", 2, "Strict")],
        serviceAccounts=[obj("ServiceAccount", "11111111-1111-1111-1111-111111111111", "ci")],
    )


class TestResolve:
    def test_ids_pass_through_without_any_request(self, tenant):
        ids = [make_id("Group", 7), make_id("Group", 8)]
        assert resolve(tenant, GROUP, ids) == ids
        assert tenant.requests == []

    def test_an_empty_list_costs_nothing(self, tenant):
        assert resolve(tenant, GROUP, []) == []
        assert tenant.requests == []

    def test_a_name_becomes_its_id(self, tenant):
        assert resolve(tenant, GROUP, ["Eng"]) == [make_id("Group", 1)]

    @pytest.mark.parametrize("kind,name,expected", [
        (NETWORK, "Cloud Applications", make_id("RemoteNetwork", 1)),
        (POLICY, "Strict", make_id("SecurityPolicy", 2)),
        (SERVICE_ACCOUNT, "ci", make_id("ServiceAccount", "11111111-1111-1111-1111-111111111111")),
    ])
    def test_every_kind_looks_in_its_own_collection(self, tenant, kind, name, expected):
        assert resolve(tenant, kind, [name]) == [expected]
        assert kind.root in tenant.requests[0][0]

    def test_many_names_are_one_request(self, tenant):
        tenant.page = 50  # the API's real page size
        assert resolve(tenant, GROUP, ["Eng", "Ops", "Sales"]) == [make_id("Group", n) for n in (1, 2, 3)]
        assert len(tenant.requests) == 1
        assert tenant.requests[0][1]["names"] == ["Eng", "Ops", "Sales"]

    def test_ids_and_names_mix_and_keep_their_order_and_repeats(self, tenant):
        first, other = make_id("Group", 9), make_id("Group", 8)
        assert resolve(tenant, GROUP, [first, "Sales", "Eng", other, "Sales"]) == [first, make_id("Group", 3), make_id("Group", 1), other, make_id("Group", 3)]
        assert tenant.requests[0][1]["names"] == ["Sales", "Eng"]  # only the names are looked up, each once

    def test_matching_is_exact_and_case_sensitive(self, tenant):
        assert resolve(tenant, GROUP, ["Ops"]) == [make_id("Group", 2)]
        assert resolve(tenant, GROUP, ["ops"]) == [make_id("Group", 6)]
        with pytest.raises(ResolveError):
            resolve(tenant, GROUP, ["OPS"])

    def test_results_that_span_several_pages_are_all_used(self, tenant):
        tenant.tenant["groups"] += [obj("Group", n, f"G{n}") for n in range(10, 16)]
        names = [f"G{n}" for n in range(10, 16)]
        assert resolve(tenant, GROUP, names) == [make_id("Group", n) for n in range(10, 16)]
        assert len(tenant.requests) == 3  # six hits, two per page

    def test_an_unknown_name_is_an_error_that_says_so(self, tenant):
        with pytest.raises(ResolveError) as exc:
            resolve(tenant, NETWORK, ["Cloud Aplications"])
        assert exc.value.problems == ["no Remote Network named 'Cloud Aplications' (a name must match exactly, including capitals; you can also pass the ID)"]

    def test_an_ambiguous_name_is_an_error_listing_the_candidates(self, tenant):
        with pytest.raises(ResolveError) as exc:
            resolve(tenant, GROUP, ["Dup"])
        (problem,) = exc.value.problems
        assert "'Dup' matches 2 groups" in problem and make_id("Group", 4) in problem and make_id("Group", 5) in problem and "use the ID" in problem

    def test_every_problem_is_reported_together_and_nothing_is_returned(self, tenant):
        with pytest.raises(ResolveError) as exc:
            resolve(tenant, GROUP, ["Eng", "Nope", "Dup", "Also nope"])
        assert len(exc.value.problems) == 3 and "Nope" in exc.value.problems[0] and "Dup" in exc.value.problems[1]

    def test_the_same_unknown_name_twice_is_reported_once(self, tenant):
        with pytest.raises(ResolveError) as exc:
            resolve(tenant, GROUP, ["Nope", "Nope"])
        assert len(exc.value.problems) == 1

    @pytest.mark.parametrize("name", ['a"b\'c\\d', "Ελληνικά", "日本語", "x, y", "tab\there", "  padded  "])
    def test_unusual_names_are_sent_as_data_and_simply_not_found(self, tenant, name):
        with pytest.raises(ResolveError):
            resolve(tenant, GROUP, [name])
        assert tenant.requests[0][1]["names"] == [name]

    def test_a_name_with_special_characters_that_exists_is_found(self, tenant):
        tenant.tenant["groups"].append(obj("Group", 20, "Ops, EMEA \"x\" é"))
        assert resolve(tenant, GROUP, ["Ops, EMEA \"x\" é"]) == [make_id("Group", 20)]

    def test_api_errors_from_the_lookup_propagate_unchanged(self, tenant):
        tenant.error = TwingateAPIError("boom")
        with pytest.raises(TwingateAPIError, match="boom"):
            resolve(tenant, GROUP, ["Eng"])
