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
RESOURCE_DETAIL = """id name address { value } remoteNetwork { name } alias isVisible isBrowserShortcutEnabled approvalMode
  securityPolicy { id } accessPolicy { mode durationSeconds } protocols { allowIcmp tcp { policy ports { start end } } udp { policy ports { start end } } }
  tags { key value } ... on NetworkResource { routingMode }"""

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
  $tags: [TagInput!], $accessPolicy: AccessPolicyInput, $approvalMode: AccessApprovalMode
) {
  resourceCreate(
    name: $name, address: $address, remoteNetworkId: $remoteNetworkId, protocols: $protocols, alias: $alias,
    securityPolicyId: $securityPolicyId, isVisible: $isVisible, isBrowserShortcutEnabled: $isBrowserShortcutEnabled,
    routingMode: $routingMode, tags: $tags, accessPolicy: $accessPolicy, approvalMode: $approvalMode
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
  $id: ID!, $alias: String, $protocols: ProtocolsInput, $securityPolicyId: ID, $isVisible: Boolean, $isBrowserShortcutEnabled: Boolean,
  $routingMode: RoutingMode, $tags: [TagInput!], $accessPolicy: AccessPolicyInput, $approvalMode: AccessApprovalMode
) {
  resourceUpdate(
    id: $id, alias: $alias, protocols: $protocols, securityPolicyId: $securityPolicyId, isVisible: $isVisible,
    isBrowserShortcutEnabled: $isBrowserShortcutEnabled, routingMode: $routingMode, tags: $tags, accessPolicy: $accessPolicy,
    approvalMode: $approvalMode
  ) { ok error entity { id } }
}
"""

REMOVE_RESOURCE_ACCESS = """
mutation importAccessRemove($id: ID!, $principalIds: [ID!]!) {
  resourceAccessRemove(resourceId: $id, principalIds: $principalIds) { ok error entity { id } }
}
"""

SYNC_GROUP = """
mutation importGroupSync($id: ID!, $securityPolicyId: ID, $removedUserIds: [ID]) {
  groupUpdate(id: $id, securityPolicyId: $securityPolicyId, removedUserIds: $removedUserIds) { ok error entity { id } }
}
"""
