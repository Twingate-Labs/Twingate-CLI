"""Each follow-up query must select exactly the fields its list or show query selects, so added items match."""

from __future__ import annotations

import re

import pytest

from tgcli.queries import accounts, dns_profiles, groups, keys, mappings, networks, policies, resources, users
from tgcli.queries.nested import connection, continuation

squash = lambda text: re.sub(r"\s+", " ", text)

# (query text, {field: continuation query}, {field: edge selection the query must contain})
CASES = {
    "group list": (groups.LIST_GROUPS, groups.GROUP_CONTINUATIONS, groups._NESTED),
    "group show": (groups.SHOW_GROUP, groups.GROUP_CONTINUATIONS, groups._NESTED),
    "network list": (networks.LIST_NETWORKS, networks.NETWORK_CONTINUATIONS, networks._NESTED),
    "network show": (networks.SHOW_NETWORK, networks.NETWORK_CONTINUATIONS, networks._NESTED),
    "user list": (users.LIST_USERS, users.USER_LIST_CONTINUATIONS, users._LIST_NESTED),
    "user show": (users.SHOW_USER, users.USER_SHOW_CONTINUATIONS, users._SHOW_NESTED),
    "policy show": (policies.SHOW_POLICY, policies.POLICY_CONTINUATIONS, policies._NESTED),
    "account show": (accounts.SHOW_ACCOUNT, accounts.ACCOUNT_SHOW_CONTINUATIONS, accounts._SHOW_NESTED),
    "account listKeys": (accounts.LIST_ACCOUNT_KEYS, accounts.ACCOUNT_KEYS_CONTINUATIONS, accounts._KEYS_NESTED),
    "dns-profile show": (dns_profiles.SHOW_DNS_PROFILE, dns_profiles.DNS_PROFILE_CONTINUATIONS, dns_profiles._NESTED),
    "key list": (keys.LIST_KEYS, keys.KEYS_CONTINUATIONS, keys._NESTED),
    "resource list": (resources.LIST_RESOURCES, resources.RESOURCE_LIST_CONTINUATIONS, {"access": resources._ACCESS_EDGE}),
    "resource list --detail": (
        resources.LIST_RESOURCES_DETAIL, resources.RESOURCE_DETAIL_CONTINUATIONS,
        {"access": resources._ACCESS_EDGE, "approverGroups": resources._APPROVER_EDGE},
    ),
    "resource show": (resources.SHOW_RESOURCE, resources.RESOURCE_SHOW_CONTINUATIONS, {"approverGroups": resources._APPROVER_EDGE}),
    "group create": (groups.CREATE_GROUP, groups.GROUP_CONTINUATIONS, groups._NESTED),
    "group addUsers": (groups.ADD_USERS_TO_GROUP, groups.GROUP_USERS_CONTINUATIONS, {"users": groups._NESTED["users"]}),
    "group removeUsers": (groups.REMOVE_USERS_FROM_GROUP, groups.GROUP_USERS_CONTINUATIONS, {"users": groups._NESTED["users"]}),
    "group assignPolicy": (groups.ASSIGN_POLICY_TO_GROUP, groups.GROUP_USERS_CONTINUATIONS, {"users": groups._NESTED["users"]}),
    "group addResources": (groups.ADD_RESOURCES_TO_GROUP, groups.GROUP_RESOURCES_ECHO_CONTINUATIONS, {"resources": groups._ECHO_RESOURCE_EDGE}),
    "group removeResources": (groups.REMOVE_RESOURCES_FROM_GROUP, groups.GROUP_RESOURCES_ECHO_CONTINUATIONS, {"resources": groups._ECHO_RESOURCE_EDGE}),
    "account addResources": (accounts.ADD_RESOURCES_TO_ACCOUNT, accounts.ACCOUNT_RESOURCES_CONTINUATIONS, {"resources": accounts._SHOW_NESTED["resources"]}),
    "account removeResources": (accounts.REMOVE_RESOURCES_FROM_ACCOUNT, accounts.ACCOUNT_RESOURCES_CONTINUATIONS, {"resources": accounts._SHOW_NESTED["resources"]}),
    "policy update": (policies.UPDATE_POLICY_GROUPS, policies.POLICY_CONTINUATIONS, policies._NESTED),
    "user role": (users.UPDATE_USER_ROLE, users.USER_LIST_CONTINUATIONS, users._LIST_NESTED),
    "mappings user-network": (mappings.LIST_USER_RN_MAPPINGS, mappings.USER_GROUPS_CONTINUATIONS, {"groups": mappings._GROUP_EDGE}),
    "mappings group resources": (mappings.LIST_USER_RN_MAPPINGS, mappings.GROUP_RESOURCES_CONTINUATIONS, {"resources": mappings._RESOURCE_EDGE}),
    "mappings user-resource": (mappings.GET_USER_BY_EMAIL, mappings.USER_BY_EMAIL_CONTINUATIONS, {"groups": "node { id }"}),
}


@pytest.mark.parametrize("name", CASES)
class TestQueriesStayInSync:
    def test_the_query_selects_each_nested_list_with_its_count_and_cursor(self, name):
        query, continuations, edges = CASES[name]
        for field, edge in edges.items():
            assert connection(field, edge) in squash(query), field

    def test_each_follow_up_selects_the_same_edge_fields(self, name):
        query, continuations, edges = CASES[name]
        assert set(continuations) == set(edges)
        for field, edge in edges.items():
            assert edge in squash(continuations[field]), field

    def test_follow_ups_take_an_id_and_a_cursor_that_may_be_null(self, name):
        for query in CASES[name][1].values():
            assert query.startswith("query($id: ID!, $cursor: String)")

    def test_braces_balance_and_no_template_marker_is_left(self, name):
        query = CASES[name][0]
        assert query.count("{") == query.count("}") and "@@" not in query


class TestBuilders:
    def test_continuation_spreads_over_implementations_when_asked(self):
        text = continuation("resource", "approverGroups", "node { id }", on=("A", "B"))
        assert text.count("... on A {") == 1 and text.count("... on B {") == 1
        assert text.count("approverGroups(after: $cursor)") == 2

    def test_continuation_without_types_has_no_fragments(self):
        assert "..." not in continuation("group", "users", "node { id }")

    def test_connection_asks_for_the_count_and_cursor_literally(self):
        # Written out in full on purpose: the fake APIs in other tests always supply these, so only this
        # test notices a query that forgets to request them (truncation would then go undetected).
        assert squash(connection("users", "node { id }")) == (
            "users { totalCount pageInfo { hasNextPage endCursor } edges { node { id } } }"
        )

    def test_continuation_asks_for_the_cursor_and_takes_the_after_argument_literally(self):
        assert squash(continuation("group", "users", "node { id }")) == (
            "query($id: ID!, $cursor: String) { group(id: $id) { users(after: $cursor) "
            "{ pageInfo { hasNextPage endCursor } edges { node { id } } } } }"
        )

    def test_mappings_group_selection_includes_the_id_needed_to_follow_it(self):
        assert mappings._GROUP_EDGE.startswith("node { id ")


def selection_tree(query: str) -> list[tuple[str, list]]:
    """Parse a GraphQL selection set into [(field, children)], ignoring arguments and treating fragments as fields."""
    tokens = re.findall(r"\.\.\.\s*on\s+\w+|[A-Za-z_]\w*|[{}]", re.sub(r"\([^()]*\)", "", query))
    pos = 0

    def parse() -> list[tuple[str, list]]:
        nonlocal pos
        fields: list[tuple[str, list]] = []
        while pos < len(tokens):
            token = tokens[pos]
            pos += 1
            if token == "}":
                return fields
            if token == "{":
                continue
            children: list = []
            if pos < len(tokens) and tokens[pos] == "{":
                pos += 1
                children = parse()
            fields.append((token, children))
        return fields

    return parse()


def connections_without_page_info(query: str) -> list[str]:
    bad: list[str] = []

    def walk(fields: list[tuple[str, list]], path: list[str]) -> None:
        names = {name for name, _ in fields}
        if "edges" in names and "pageInfo" not in names:
            bad.append(" > ".join(path))
        for name, children in fields:
            walk(children, path + [name])

    walk(selection_tree(query), [])
    return bad


def all_queries() -> dict[str, str]:
    import importlib
    import pkgutil

    import tgcli.queries as package

    found: dict[str, str] = {}
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"tgcli.queries.{module_info.name}")
        for name, value in vars(module).items():
            values = {name: value} if isinstance(value, str) else {f"{name}[{k}]": v for k, v in value.items()} if isinstance(value, dict) else {}
            for label, text in values.items():
                if not label.startswith("_") and isinstance(text, str) and text.lstrip().startswith(("query", "mutation")):
                    found[f"{module_info.name}.{label}"] = text
    return found


class TestEveryQueryPaginates:
    """A connection that does not request pageInfo cannot be followed past its first page of 50.

    This covers writes too: a write echoes the changed object, and its lists are cut at 50 like any other.
    """

    def test_the_checker_finds_a_connection_that_forgets_page_info(self):
        assert connections_without_page_info("query { groups { edges { node { id } } } }") == ["query > groups"]
        assert connections_without_page_info("query { groups { pageInfo { hasNextPage } edges { node { id } } } }") == []

    def test_the_checker_looks_inside_nested_selections_and_fragments(self):
        nested = "query { a { pageInfo { x } edges { node { b { edges { node { id } } } } } } }"
        assert connections_without_page_info(nested) == ["query > a > edges > node > b"]
        fragment = "query { r { ... on X { approvers { edges { node { id } } } } } }"
        assert connections_without_page_info(fragment) == ["query > r > ... on X > approvers"]

    def test_there_are_queries_to_check(self):
        found = all_queries()
        assert len(found) > 70 and any(text.lstrip().startswith("mutation") for text in found.values())

    @pytest.mark.parametrize("name", sorted(all_queries()))
    def test_every_connection_requests_page_info(self, name):
        assert connections_without_page_info(all_queries()[name]) == []


class TestWriteEchoesKeepTheirFields:
    """Written out literally on purpose: these are what each write command has always printed, and the shared
    definitions would otherwise let an accidental change to them slip through unnoticed."""

    LISTS = {
        "users": "users { totalCount pageInfo { hasNextPage endCursor } edges { node { id email firstName lastName } } }",
        "group resources": "resources { totalCount pageInfo { hasNextPage endCursor } edges { node { id name } } }",
        "group create resources": (
            "resources { totalCount pageInfo { hasNextPage endCursor } edges { node { id name address { type value } isActive } } }"
        ),
        "groups of a policy": "groups { totalCount pageInfo { hasNextPage endCursor } edges { node { id name } } }",
        "groups of a user": "groups { totalCount pageInfo { hasNextPage endCursor } edges { node { id } } }",
    }
    CASES = {
        "group create": (groups.CREATE_GROUP, ["users", "group create resources"]),
        "group addUsers": (groups.ADD_USERS_TO_GROUP, ["users"]),
        "group removeUsers": (groups.REMOVE_USERS_FROM_GROUP, ["users"]),
        "group assignPolicy": (groups.ASSIGN_POLICY_TO_GROUP, ["users"]),
        "group addResources": (groups.ADD_RESOURCES_TO_GROUP, ["group resources"]),
        "group removeResources": (groups.REMOVE_RESOURCES_FROM_GROUP, ["group resources"]),
        "account addResources": (accounts.ADD_RESOURCES_TO_ACCOUNT, ["group resources"]),
        "account removeResources": (accounts.REMOVE_RESOURCES_FROM_ACCOUNT, ["group resources"]),
        "policy update": (policies.UPDATE_POLICY_GROUPS, ["groups of a policy"]),
        "user role": (users.UPDATE_USER_ROLE, ["groups of a user"]),
    }

    @pytest.mark.parametrize("name", CASES)
    def test_each_write_echoes_the_same_list_fields_as_before(self, name):
        query, lists = self.CASES[name]
        for key in lists:
            assert self.LISTS[key] in squash(query), (name, key)

    def test_assign_policy_still_echoes_the_policy(self):
        assert "securityPolicy { id name policyType }" in squash(groups.ASSIGN_POLICY_TO_GROUP)
