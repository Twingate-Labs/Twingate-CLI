"""GraphQL queries for `tgcli backup`.

Every query is composed from the selections below, so the first page of a nested list and the
follow-up pages that complete it can never drift apart.
"""

from __future__ import annotations

from typing import NamedTuple


class Entity(NamedTuple):
    key: str  # internal key, e.g. "remote_networks"
    file: str  # file name inside the backup, e.g. "remote-networks.json"
    label: str  # for progress output
    root: str  # top-level connection field, e.g. "remoteNetworks"
    parent: str  # single-object query field, e.g. "remoteNetwork"
    nested: tuple[str, ...]  # nested connections that may need follow-up pages


ENTITIES = (
    Entity("groups", "groups.json", "groups", "groups", "group", ("users", "resources")),
    Entity("users", "users.json", "users", "users", "user", ("groups",)),
    Entity("resources", "resources.json", "resources", "resources", "resource", ("access", "approverGroups")),
    Entity("connectors", "connectors.json", "connectors", "connectors", "connector", ()),
    Entity(
        "remote_networks", "remote-networks.json", "remote networks", "remoteNetworks", "remoteNetwork",
        ("connectors", "resources", "gateways"),
    ),
)

_REF = "node { id name }"
_ACCESS_EDGE = """
  node {
    __typename
    ... on Group { id name }
    ... on ServiceAccount { id name }
  }
  securityPolicy { id name }
  accessPolicy { mode durationSeconds }
  approvalMode
  expiresAt
"""

# What each nested connection carries per edge.
NESTED_EDGES = {
    ("groups", "users"): "node { id email }",
    ("groups", "resources"): _REF,
    ("users", "groups"): _REF,
    ("resources", "access"): _ACCESS_EDGE,
    ("resources", "approverGroups"): _REF,
    ("remote_networks", "connectors"): _REF,
    ("remote_networks", "resources"): _REF,
    ("remote_networks", "gateways"): "node { id address }",
}

# The API returns at most 50 items per page and silently clamps any larger `first`, so every list
# is followed by cursor to its end and checked against the API's own totalCount.
_PAGE_INFO = "pageInfo { hasNextPage endCursor }"


def _connection(entity: str, field: str) -> str:
    return f"{field} {{ totalCount {_PAGE_INFO} edges {{ {NESTED_EDGES[(entity, field)]} }} }}"


def _list_query(root: str, selection: str) -> str:
    return (
        f"query($cursor: String) {{ {root}(after: $cursor) {{ totalCount {_PAGE_INFO} "
        f"edges {{ node {{ {selection} }} }} }} }}"
    )


# Resource is a GraphQL interface: some fields exist only on each implementation.
RESOURCE_TYPES = ("NetworkResource", "SSHResource", "WebAppResource", "KubernetesResource")
_RESOURCE_COMMON = """
  __typename id name alias createdAt updatedAt isActive
  remoteNetwork { id name }
  address { type value }
  protocols { allowIcmp tcp { policy ports { start end } } udp { policy ports { start end } } }
  tags { key value }
"""
_RESOURCE_EACH_TYPE = (
    "isVisible isBrowserShortcutEnabled securityPolicy { id name } accessPolicy { mode durationSeconds } approvalMode "
    + _connection("resources", "approverGroups")
)
_RESOURCE_ONLY_ON = {
    "NetworkResource": "routingMode",
    "SSHResource": "gateway { id address } upstream { port } downstream { port }",
    "WebAppResource": (
        "gateway { id address } upstream { port tlsMode } downstream { port tlsMode } requestHeaderRewrites { key value }"
    ),
    "KubernetesResource": "gateway { id address } clusterRef upstream { port } downstream { port }",
}
_RESOURCE_SELECTION = (
    _RESOURCE_COMMON
    + _connection("resources", "access")
    + " "
    + " ".join(f"... on {t} {{ {_RESOURCE_EACH_TYPE} {_RESOURCE_ONLY_ON[t]} }}" for t in RESOURCE_TYPES)
)

SELECTIONS = {
    "groups": (
        "id name originId type isActive createdAt updatedAt securityPolicy { id name } "
        + _connection("groups", "users") + " " + _connection("groups", "resources")
    ),
    "users": (
        "id email firstName lastName role state type avatarUrl createdAt updatedAt " + _connection("users", "groups")
    ),
    "resources": _RESOURCE_SELECTION,
    "connectors": (
        "id name state hostname version publicIP privateIPs lastHeartbeatAt createdAt updatedAt "
        "hasStatusNotificationsEnabled remoteNetwork { id name }"
    ),
    "remote_networks": (
        "id name location networkType isActive createdAt updatedAt "
        + " ".join(_connection("remote_networks", f) for f in ("connectors", "resources", "gateways"))
    ),
}

LIST_QUERIES = {e.key: _list_query(e.root, SELECTIONS[e.key]) for e in ENTITIES}


def _continuation(entity: str, parent: str, field: str) -> str:
    inner = f"{field}(after: $cursor) {{ {_PAGE_INFO} edges {{ {NESTED_EDGES[(entity, field)]} }} }}"
    if entity == "resources" and field == "approverGroups":
        inner = " ".join(f"... on {t} {{ {inner} }}" for t in RESOURCE_TYPES)
    return f"query($id: ID!, $cursor: String) {{ {parent}(id: $id) {{ {inner} }} }}"


# Completes a nested list that did not fit in one page, starting from the cursor the first page ended on.
CONTINUATION_QUERIES = {(e.key, f): _continuation(e.key, e.parent, f) for e in ENTITIES for f in e.nested}
