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
