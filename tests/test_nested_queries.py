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


def read_queries() -> dict[str, str]:
    import importlib
    import pkgutil

    import tgcli.queries as package

    found: dict[str, str] = {}
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"tgcli.queries.{module_info.name}")
        for name, value in vars(module).items():
            values = {name: value} if isinstance(value, str) else {f"{name}[{k}]": v for k, v in value.items()} if isinstance(value, dict) else {}
            for label, text in values.items():
                if not label.startswith("_") and isinstance(text, str) and text.lstrip().startswith("query"):
                    found[f"{module_info.name}.{label}"] = text
    return found


class TestEveryReadQueryPaginates:
    """A connection that does not request pageInfo cannot be followed past its first page of 50."""

    def test_the_checker_finds_a_connection_that_forgets_page_info(self):
        assert connections_without_page_info("query { groups { edges { node { id } } } }") == ["query > groups"]
        assert connections_without_page_info("query { groups { pageInfo { hasNextPage } edges { node { id } } } }") == []

    def test_the_checker_looks_inside_nested_selections_and_fragments(self):
        nested = "query { a { pageInfo { x } edges { node { b { edges { node { id } } } } } } }"
        assert connections_without_page_info(nested) == ["query > a > edges > node > b"]
        fragment = "query { r { ... on X { approvers { edges { node { id } } } } } }"
        assert connections_without_page_info(fragment) == ["query > r > ... on X > approvers"]

    def test_there_are_read_queries_to_check(self):
        assert len(read_queries()) > 40

    @pytest.mark.parametrize("name", sorted(read_queries()))
    def test_every_connection_requests_page_info(self, name):
        assert connections_without_page_info(read_queries()[name]) == []
