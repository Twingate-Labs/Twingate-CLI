"""Writes that only `tgcli restore` makes: the things it puts back that `import` never touches.

Every optional argument is a nullable variable, so a restore sends only what it is putting back.
"""

from __future__ import annotations

CREATE_SERVICE_ACCOUNT = """
mutation restoreServiceAccountCreate($name: String!) {
  serviceAccountCreate(name: $name) { ok error entity { id name } }
}
"""

UPDATE_SERVICE_ACCOUNT = """
mutation restoreServiceAccountUpdate($id: ID!, $name: String) {
  serviceAccountUpdate(id: $id, name: $name) { ok error entity { id name } }
}
"""

CREATE_GATEWAY = """
mutation restoreGatewayCreate($address: String!, $remoteNetworkId: ID!, $x509CAId: ID!, $sshCAId: ID) {
  gatewayCreate(address: $address, remoteNetworkId: $remoteNetworkId, x509CAId: $x509CAId, sshCAId: $sshCAId) { ok error entity { id address } }
}
"""

UPDATE_GATEWAY = """
mutation restoreGatewayUpdate($id: ID!, $address: String, $remoteNetworkId: ID, $x509CAId: ID, $sshCAId: ID) {
  gatewayUpdate(id: $id, address: $address, remoteNetworkId: $remoteNetworkId, x509CAId: $x509CAId, sshCAId: $sshCAId) { ok error entity { id address } }
}
"""

UPDATE_USER_ROLE = """
mutation restoreUserRole($id: ID!, $role: UserRole) {
  userRoleUpdate(id: $id, role: $role) { ok error entity { id email role } }
}
"""

CREATE_CONNECTOR = """
mutation restoreConnectorCreate($name: String, $remoteNetworkId: ID!, $hasStatusNotificationsEnabled: Boolean) {
  connectorCreate(name: $name, remoteNetworkId: $remoteNetworkId, hasStatusNotificationsEnabled: $hasStatusNotificationsEnabled) {
    ok error entity { id name }
  }
}
"""

UPDATE_CONNECTOR = """
mutation restoreConnectorUpdate($id: ID!, $name: String, $hasStatusNotificationsEnabled: Boolean) {
  connectorUpdate(id: $id, name: $name, hasStatusNotificationsEnabled: $hasStatusNotificationsEnabled) { ok error entity { id name } }
}
"""

UPDATE_DEVICE_TRUST = """
mutation restoreDeviceTrust($id: ID!, $isTrusted: Boolean!) {
  deviceUpdate(id: $id, isTrusted: $isTrusted) { ok error entity { id isTrusted } }
}
"""

# One mutation per move between the three device states; a move between BLOCKED and ARCHIVED goes through ACTIVE.
DEVICE_STATE = {
    "block": """mutation restoreDeviceBlock($id: ID!) { deviceBlock(id: $id) { ok error entity { id activeState } } }""",
    "unblock": """mutation restoreDeviceUnblock($id: ID!) { deviceUnblock(id: $id) { ok error entity { id activeState } } }""",
    "archive": """mutation restoreDeviceArchive($id: ID!) { deviceArchive(id: $id) { ok error entity { id activeState } } }""",
    "unarchive": """mutation restoreDeviceUnarchive($id: ID!) { deviceUnarchive(id: $id) { ok error entity { id activeState } } }""",
}
DEVICE_STATE_FIELD = {"block": "deviceBlock", "unblock": "deviceUnblock", "archive": "deviceArchive", "unarchive": "deviceUnarchive"}
# (state now, state wanted) -> the moves
DEVICE_MOVES = {
    ("ACTIVE", "BLOCKED"): ("block",), ("ACTIVE", "ARCHIVED"): ("archive",),
    ("BLOCKED", "ACTIVE"): ("unblock",), ("BLOCKED", "ARCHIVED"): ("unblock", "archive"),
    ("ARCHIVED", "ACTIVE"): ("unarchive",), ("ARCHIVED", "BLOCKED"): ("unarchive", "block"),
}

CREATE_DNS_PROFILE = """
mutation restoreDnsProfileCreate($name: String!) {
  dnsFilteringProfileCreate(name: $name) { ok error entity { id name } }
}
"""

UPDATE_DNS_PROFILE = """
mutation restoreDnsProfileUpdate(
  $id: ID!, $name: String, $priority: Float, $fallbackMethod: DohFallbackMethod, $allowedDomains: [String!], $deniedDomains: [String!],
  $groups: [String!], $contentCategoryConfig: ContentCategoryConfigInput, $securityCategoryConfig: SecurityCategoryConfigInput,
  $privacyCategoryConfig: PrivacyCategoryConfigInput
) {
  dnsFilteringProfileUpdate(
    id: $id, name: $name, priority: $priority, fallbackMethod: $fallbackMethod, allowedDomains: $allowedDomains, deniedDomains: $deniedDomains,
    groups: $groups, contentCategoryConfig: $contentCategoryConfig, securityCategoryConfig: $securityCategoryConfig,
    privacyCategoryConfig: $privacyCategoryConfig
  ) { ok error entity { id name } }
}
"""
