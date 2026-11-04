"""GraphQL queries and mutations for `tgcli import`.

The writes declare every optional argument as a nullable variable. A variable that is not passed is simply absent from the
call, so the importer sends only what the file actually says and leaves everything else to the API's defaults.
"""

from __future__ import annotations

GROUP_USERS = """
query($id: ID!, $cursor: String) {
  group(id: $id) { users(after: $cursor) { pageInfo { hasNextPage endCursor } edges { node { id } } } }
}
"""

RESOURCE_ACCESS = """
query($id: ID!, $cursor: String) {
  resource(id: $id) {
    access(after: $cursor) { pageInfo { hasNextPage endCursor } edges { node { ... on Group { id } ... on ServiceAccount { id } } } }
  }
}
"""

# What --sync compares an existing resource with. Looked up with the name filter, like everything else.
RESOURCE_DETAIL = """__typename id name address { value } remoteNetwork { name } alias isVisible isBrowserShortcutEnabled approvalMode
  securityPolicy { id } accessPolicy { mode durationSeconds } protocols { allowIcmp tcp { policy ports { start end } } udp { policy ports { start end } } }
  tags { key value } ... on NetworkResource { routingMode }
  ... on SSHResource { gateway { id } upstream { port } downstream { port } }
  ... on WebAppResource { gateway { id } upstream { port tlsMode } downstream { port tlsMode } requestHeaderRewrites { key value } }
  ... on KubernetesResource { gateway { id } clusterRef upstream { port } downstream { port } }"""

# What a lookup selects of every resource it finds: the type is needed because the API cannot change one.
RESOURCE_KEYS = "__typename id name address { value } remoteNetwork { name }"

# Gateways have no name; the file names one by its address, and its Remote Network tells two with the same address apart.
GATEWAYS = """
query($cursor: String) {
  gateways(after: $cursor) { pageInfo { hasNextPage endCursor } edges { node { id address remoteNetwork { id name } sshCA { id } } } }
}
"""

GROUP_DETAIL = "id name type securityPolicy { id }"

GROUP_USERS_DETAIL = """
query($id: ID!, $cursor: String) {
  group(id: $id) { users(after: $cursor) { pageInfo { hasNextPage endCursor } edges { node { id email } } } }
}
"""

RESOURCE_GRANTS = """
query($id: ID!, $cursor: String) {
  resource(id: $id) {
    access(after: $cursor) {
      pageInfo { hasNextPage endCursor }
      edges {
        node { ... on Group { id name } ... on ServiceAccount { id name } }
        securityPolicy { id } accessPolicy { mode durationSeconds } approvalMode expiresAt
      }
    }
  }
}
"""

CREATE_NETWORK = """
mutation importNetwork($name: String!, $location: RemoteNetworkLocation, $networkType: RemoteNetworkType, $isActive: Boolean) {
  remoteNetworkCreate(name: $name, location: $location, networkType: $networkType, isActive: $isActive) {
    ok error entity { id name }
  }
}
"""

CREATE_GROUP = """
mutation importGroup($name: String!, $securityPolicyId: ID) {
  groupCreate(name: $name, securityPolicyId: $securityPolicyId) { ok error entity { id name } }
}
"""

ADD_GROUP_USERS = """
mutation importGroupUsers($id: ID!, $userIds: [ID]) {
  groupUpdate(id: $id, addedUserIds: $userIds) { ok error entity { id } }
}
"""

CREATE_RESOURCE = """
mutation importResource(
  $name: String!, $address: String!, $remoteNetworkId: ID!, $protocols: ProtocolsInput, $alias: String,
  $securityPolicyId: ID, $isVisible: Boolean, $isBrowserShortcutEnabled: Boolean, $routingMode: RoutingMode,
  $tags: [TagInput!], $accessPolicy: AccessPolicyInput, $approvalMode: AccessApprovalMode, $approverGroupIds: [ID!]
) {
  resourceCreate(
    name: $name, address: $address, remoteNetworkId: $remoteNetworkId, protocols: $protocols, alias: $alias,
    securityPolicyId: $securityPolicyId, isVisible: $isVisible, isBrowserShortcutEnabled: $isBrowserShortcutEnabled,
    routingMode: $routingMode, tags: $tags, accessPolicy: $accessPolicy, approvalMode: $approvalMode, approverGroupIds: $approverGroupIds
  ) { ok error entity { id name } }
}
"""

ADD_RESOURCE_ACCESS = """
mutation importAccess($id: ID!, $access: [AccessInput!]!) {
  resourceAccessAdd(resourceId: $id, access: $access) { ok error entity { id } }
}
"""

UPDATE_DEVICE_TRUST = """
mutation importDeviceTrust($id: ID!, $isTrusted: Boolean!) {
  deviceUpdate(id: $id, isTrusted: $isTrusted) { ok error entity { id isTrusted } }
}
"""

UPDATE_RESOURCE = """
mutation importResourceUpdate(
  $id: ID!, $name: String, $address: String, $remoteNetworkId: ID, $isActive: Boolean, $alias: String, $protocols: ProtocolsInput, $securityPolicyId: ID, $isVisible: Boolean, $isBrowserShortcutEnabled: Boolean,
  $routingMode: RoutingMode, $tags: [TagInput!], $accessPolicy: AccessPolicyInput, $approvalMode: AccessApprovalMode,
  $addedApproverGroupIds: [ID!], $removedApproverGroupIds: [ID!]
) {
  resourceUpdate(
    id: $id, name: $name, address: $address, remoteNetworkId: $remoteNetworkId, isActive: $isActive, alias: $alias, protocols: $protocols, securityPolicyId: $securityPolicyId, isVisible: $isVisible,
    isBrowserShortcutEnabled: $isBrowserShortcutEnabled, routingMode: $routingMode, tags: $tags, accessPolicy: $accessPolicy,
    approvalMode: $approvalMode, addedApproverGroupIds: $addedApproverGroupIds, removedApproverGroupIds: $removedApproverGroupIds
  ) { ok error entity { id } }
}
"""

REMOVE_RESOURCE_ACCESS = """
mutation importAccessRemove($id: ID!, $principalIds: [ID!]!) {
  resourceAccessRemove(resourceId: $id, principalIds: $principalIds) { ok error entity { id } }
}
"""

SYNC_GROUP = """
mutation importGroupSync($id: ID!, $name: String, $isActive: Boolean, $securityPolicyId: ID, $removedUserIds: [ID]) {
  groupUpdate(id: $id, name: $name, isActive: $isActive, securityPolicyId: $securityPolicyId, removedUserIds: $removedUserIds) { ok error entity { id } }
}
"""

UPDATE_NETWORK = """
mutation importNetworkUpdate($id: ID!, $name: String, $location: RemoteNetworkLocation, $isActive: Boolean) {
  remoteNetworkUpdate(id: $id, name: $name, location: $location, isActive: $isActive) { ok error entity { id } }
}
"""


# SSH, web app and Kubernetes resources. Like the rest of this file, every optional argument is a nullable variable.
_TYPED_COMMON = [
    ("name", "String"), ("address", "String"), ("alias", "String"), ("securityPolicyId", "ID"), ("isVisible", "Boolean"),
    ("tags", "[TagInput!]"), ("accessPolicy", "AccessPolicyInput"), ("approvalMode", "AccessApprovalMode"),
]
_TYPED_PARTS = {
    # type: (create mutation, update mutation, gateway type on create, [(variable, type)] only this type has)
    "SSH": ("sshResourceCreate", "sshResourceUpdate", "ID!", [("upstream", "SSHUpstreamInput"), ("downstream", "SSHDownstreamInput")]),
    "WEB_APP": (
        "webAppResourceCreate", "webAppResourceUpdate", "ID!",
        [("upstream", "WebAppUpstreamInput"), ("downstream", "WebAppDownstreamInput"), ("requestHeaderRewrites", "[KeyValueInputObject!]")],
    ),
    "KUBERNETES": (
        "kubernetesResourceCreate", "kubernetesResourceUpdate", "ID",
        [("clusterRef", "String"), ("upstream", "KubernetesUpstreamInput"), ("downstream", "KubernetesDownstreamInput")],
    ),
}


def _typed(kind: str, create: bool) -> str:
    create_field, update_field, gateway_type, own = _TYPED_PARTS[kind]
    field = create_field if create else update_field
    if create:
        # name, address and the Remote Network are required to create.
        common = [(n, "String!" if n in ("name", "address") else t) for n, t in _TYPED_COMMON]
        # The API requires both sides of a web app, so there the variable cannot be nullable.
        own = [(n, t + "!" if kind == "WEB_APP" and n in ("upstream", "downstream") else t) for n, t in own]
        variables = common + [("remoteNetworkId", "ID!"), ("gatewayId", gateway_type), ("approverGroupIds", "[ID!]")] + own
    else:
        variables = [("id", "ID!")] + _TYPED_COMMON + [
            ("remoteNetworkId", "ID"), ("gatewayId", "ID"), ("isActive", "Boolean"),
            ("addedApproverGroupIds", "[ID!]"), ("removedApproverGroupIds", "[ID!]"),
        ] + own
    declared = ", ".join(f"${n}: {t}" for n, t in variables)
    passed = ", ".join(f"{n}: ${n}" for n, _ in variables)
    return f"mutation import{field[0].upper()}{field[1:]}({declared}) {{ {field}({passed}) {{ ok error entity {{ id name }} }} }}"


CREATE_TYPED = {kind: _typed(kind, True) for kind in _TYPED_PARTS}
UPDATE_TYPED = {kind: _typed(kind, False) for kind in _TYPED_PARTS}
CREATE_TYPED_FIELD = {kind: parts[0] for kind, parts in _TYPED_PARTS.items()}
UPDATE_TYPED_FIELD = {kind: parts[1] for kind, parts in _TYPED_PARTS.items()}
