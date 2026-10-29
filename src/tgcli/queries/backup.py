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
    paged: bool = True  # False when the root field is a plain list of light objects (DNS profiles) that DETAIL_QUERIES fills in
    optional: bool = False  # True when failing to read it is reported, instead of failing the whole backup


ENTITIES = (
    Entity("groups", "groups.json", "groups", "groups", "group", ("users", "resources")),
    Entity("users", "users.json", "users", "users", "user", ("groups",)),
    Entity("resources", "resources.json", "resources", "resources", "resource", ("access", "approverGroups")),
    Entity("connectors", "connectors.json", "connectors", "connectors", "connector", ()),
    Entity(
        "remote_networks", "remote-networks.json", "remote networks", "remoteNetworks", "remoteNetwork",
        ("connectors", "resources", "gateways"),
    ),
    # Added later than the five above. A tenant or API key that cannot read one of these still gets everything else.
    Entity("devices", "devices.json", "devices", "devices", "device", (), optional=True),
    Entity(
        "service_accounts", "service-accounts.json", "service accounts", "serviceAccounts", "serviceAccount",
        ("resources", "keys"), optional=True,
    ),
    Entity(
        "security_policies", "security-policies.json", "security policies", "securityPolicies", "securityPolicy",
        ("groups",), optional=True,
    ),
    Entity(
        "dns_profiles", "dns-profiles.json", "DNS profiles", "dnsFilteringProfiles", "dnsFilteringProfile",
        ("groups",), paged=False, optional=True,
    ),
    Entity("gateways", "gateways.json", "gateways", "gateways", "gateway", (), optional=True),
    Entity(
        "certificate_authorities", "certificate-authorities.json", "certificate authorities", "certificateAuthorities",
        "certificateAuthority", (), optional=True,
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
    ("service_accounts", "resources"): _REF,
    ("service_accounts", "keys"): "node { id name status createdAt updatedAt expiresAt revokedAt }",
    ("security_policies", "groups"): _REF,
    ("dns_profiles", "groups"): _REF,
}

# The API returns at most 50 items per page and silently clamps any larger `first`, so every list
# is followed by cursor to its end and checked against the API's own totalCount.
_PAGE_INFO = "pageInfo { hasNextPage endCursor }"


def _connection(entity: str, field: str) -> str:
    return f"{field} {{ totalCount {_PAGE_INFO} edges {{ {NESTED_EDGES[(entity, field)]} }} }}"


def _list_query(root: str, selection: str, paged: bool = True) -> str:
    if not paged:
        return f"query {{ {root} {{ id }} }}"
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

_REF_FIELDS = "id name fingerprint"
_CATEGORY_CONFIGS = (
    "contentCategoryConfig { blockGambling blockDating blockAdultContent blockSocialMedia blockGames blockStreaming "
    "blockPiracy enableYoutubeRestrictedMode enableSafeSearch } "
    "securityCategoryConfig { enableThreatIntelligenceFeeds enableGoogleSafeBrowsing blockCryptojacking "
    "blockIdnHomographs blockTyposquatting blockDnsRebinding blockNewlyRegisteredDomains "
    "blockDomainGenerationAlgorithms blockParkedDomains } "
    "privacyCategoryConfig { blockAffiliate blockDisguisedTrackers blockAdsAndTrackers }"
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
    "devices": (
        "id name isTrusted activeState deviceType osName osVersion hardwareModel manufacturerName hostname username "
        "serialNumber clientVersion internetSecurityConfiguration lastSuccessfulLoginAt lastFailedLoginAt "
        "user { id email }"
    ),
    "service_accounts": (
        "id name createdAt updatedAt " + _connection("service_accounts", "resources") + " "
        + _connection("service_accounts", "keys")
    ),
    "security_policies": "id name policyType createdAt updatedAt " + _connection("security_policies", "groups"),
    "dns_profiles": (
        "id name priority fallbackMethod allowedDomains deniedDomains " + _CATEGORY_CONFIGS + " "
        + _connection("dns_profiles", "groups")
    ),
    "gateways": (
        "id address remoteNetwork { id name } x509CA { " + _REF_FIELDS + " } sshCA { " + _REF_FIELDS + " }"
    ),
    "certificate_authorities": (
        "__typename ... on X509CertificateAuthority { " + _REF_FIELDS + " } "
        "... on SSHCertificateAuthority { " + _REF_FIELDS + " }"
    ),
}

LIST_QUERIES = {e.key: _list_query(e.root, SELECTIONS[e.key], e.paged) for e in ENTITIES}


# For a plain-list root: the API's list holds only a summary of each object (DnsFilteringProfileMetadata), so each one
# is then read in full by its ID.
DETAIL_QUERIES = {
    e.key: f"query($id: ID!) {{ {e.parent}(id: $id) {{ {SELECTIONS[e.key]} }} }}" for e in ENTITIES if not e.paged
}


def _continuation(entity: str, parent: str, field: str) -> str:
    inner = f"{field}(after: $cursor) {{ {_PAGE_INFO} edges {{ {NESTED_EDGES[(entity, field)]} }} }}"
    if entity == "resources" and field == "approverGroups":
        inner = " ".join(f"... on {t} {{ {inner} }}" for t in RESOURCE_TYPES)
    return f"query($id: ID!, $cursor: String) {{ {parent}(id: $id) {{ {inner} }} }}"


# Completes a nested list that did not fit in one page, starting from the cursor the first page ended on.
CONTINUATION_QUERIES = {(e.key, f): _continuation(e.key, e.parent, f) for e in ENTITIES for f in e.nested}
