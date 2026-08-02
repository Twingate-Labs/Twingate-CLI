"""GraphQL queries and mutations for resources."""

from __future__ import annotations

LIST_RESOURCES = """
query listResources($cursor: String!) {
  resources(after: $cursor, first: null) {
    totalCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        isActive
        name
        alias
        createdAt
        updatedAt
        isVisible
        isBrowserShortcutEnabled
        accessPolicy {
          mode
          durationSeconds
        }
        ... on NetworkResource {
          routingMode
        }
        ... on SSHResource {
          upstream { port }
          downstream { port }
        }
        ... on KubernetesResource {
          upstream { port }
          downstream { port }
        }
        ... on WebAppResource {
          upstream { port }
          downstream { port }
        }
        tags {
          key
          value
        }
        approverGroups {
          edges {
            node {
              id
              name
            }
          }
        }
        access {
          edges {
            node {
              ... on Group {
                id
                name
              }
              ... on ServiceAccount {
                id
                name
              }
            }
            securityPolicy {
              id
              name
            }
          }
        }
        securityPolicy {
          id
          name
        }
        remoteNetwork {
          name
          id
        }
        address {
          type
          value
        }
        protocols {
          allowIcmp
          tcp {
            policy
            ports {
              start
              end
            }
          }
          udp {
            policy
            ports {
              start
              end
            }
          }
        }
      }
    }
  }
}
"""

SHOW_RESOURCE = """
query getResource($itemID: ID!) {
  resource(id: $itemID) {
    id
    name
    createdAt
    updatedAt
    isVisible
    isBrowserShortcutEnabled
    accessPolicy {
      mode
      durationSeconds
    }
    isActive
    ... on NetworkResource {
      routingMode
    }
    ... on SSHResource {
      upstream { port }
      downstream { port }
    }
    ... on KubernetesResource {
      upstream { port }
      downstream { port }
    }
    ... on WebAppResource {
      upstream { port }
      downstream { port }
    }
    remoteNetwork {
      name
      id
    }
    address {
      type
      value
    }
    protocols {
      allowIcmp
      tcp {
        policy
        ports {
          start
          end
        }
      }
      udp {
        policy
        ports {
          start
          end
        }
      }
    }
    tags {
      key
      value
    }
    approverGroups {
      edges {
        node {
          id
          name
        }
      }
    }
    access {
      edges {
        node {
          ... on Group {
            id
            name
          }
          ... on ServiceAccount {
            id
            name
          }
        }
        securityPolicy {
          id
          name
        }
      }
    }
  }
}
"""

CREATE_RESOURCE = """
mutation createResource(
  $address: String!
  $alias: String
  $name: String!
  $remoteNetworkId: ID!
  $groupIds: [ID!]
  $protocols: ProtocolsInput!
  $securityPolicyId: ID!
  $isVisible: Boolean!
  $routingMode: RoutingMode
  $tags: [TagInput!]
) {
  resourceCreate(
    protocols: $protocols
    address: $address
    alias: $alias
    groupIds: $groupIds
    name: $name
    remoteNetworkId: $remoteNetworkId
    securityPolicyId: $securityPolicyId
    isVisible: $isVisible
    routingMode: $routingMode
    tags: $tags
  ) {
    ok
    error
    entity {
      id
      name
      isVisible
      routingMode
      securityPolicy {
        id
      }
    }
  }
}
"""

DELETE_RESOURCE = """
mutation deleteResource($id: ID!) {
  resourceDelete(id: $id) {
    ok
    error
  }
}
"""

ASSIGN_NETWORK_TO_RESOURCE = """
mutation assignNetworkToResource($itemid: ID!, $networkid: ID!) {
  resourceUpdate(id: $itemid, remoteNetworkId: $networkid) {
    ok
    error
    entity {
      id
      name
      alias
      address {
        type
        value
      }
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

TOGGLE_RESOURCE_VISIBILITY = """
mutation toggleResourceVisibility($itemid: ID!, $visibility: Boolean!) {
  resourceUpdate(id: $itemid, isVisible: $visibility) {
    ok
    error
    entity {
      id
      name
      isVisible
      isBrowserShortcutEnabled
    }
  }
}
"""

UPDATE_RESOURCE_ADDRESS = """
mutation updateResourceAddress($itemid: ID!, $address: String!) {
  resourceUpdate(id: $itemid, address: $address) {
    ok
    error
    entity {
      id
      name
      alias
      accessPolicy {
        mode
        durationSeconds
      }
      address {
        type
        value
      }
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

UPDATE_RESOURCE_ALIAS = """
mutation updateResourceAlias($itemid: ID!, $alias: String!) {
  resourceUpdate(id: $itemid, alias: $alias) {
    ok
    error
    entity {
      id
      name
      alias
      accessPolicy {
        mode
        durationSeconds
      }
      address {
        type
        value
      }
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

UPDATE_RESOURCE_POLICY = """
mutation updateResourcePolicy($itemid: ID!, $securityPolicyId: ID!) {
  resourceUpdate(id: $itemid, securityPolicyId: $securityPolicyId) {
    ok
    error
    entity {
      id
      name
      alias
      accessPolicy {
        mode
        durationSeconds
      }
      securityPolicy {
        id
      }
    }
  }
}
"""

UPDATE_RESOURCE_AUTOLOCK = """
mutation updateResourceAccessPolicy($itemid: ID!, $accessPolicy: AccessPolicyInput!, $autoapprovemode: AccessApprovalMode!) {
  resourceUpdate(id: $itemid, accessPolicy: $accessPolicy, approvalMode: $autoapprovemode) {
    ok
    error
    entity {
      id
      name
      accessPolicy {
        mode
        durationSeconds
      }
      approvalMode
      address {
        type
        value
      }
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

UPDATE_RESOURCE_AUTOAPPROVE = """
mutation updateResourceAutoApprove($itemid: ID!, $autoapprovemode: AccessApprovalMode!) {
  resourceUpdate(id: $itemid, approvalMode: $autoapprovemode) {
    ok
    error
    entity {
      id
      name
      alias
      accessPolicy {
        mode
        durationSeconds
      }
      approvalMode
      address {
        type
        value
      }
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

RESOURCE_ACCESS_SET = """
mutation setResourceAccess($accessids: [AccessInput!]!, $itemid: ID!) {
  resourceAccessSet(access: $accessids, resourceId: $itemid) {
    ok
    error
    entity {
      id
      createdAt
      updatedAt
      name
    }
  }
}
"""

RESOURCE_ACCESS_ADD = """
mutation addResourceAccess($accessids: [AccessInput!]!, $itemid: ID!) {
  resourceAccessAdd(access: $accessids, resourceId: $itemid) {
    ok
    error
    entity {
      id
      createdAt
      updatedAt
      name
    }
  }
}
"""

RESOURCE_ACCESS_REMOVE = """
mutation removeResourceAccess($itemid: ID!, $groupid: [ID!]!) {
  resourceAccessRemove(principalIds: $groupid, resourceId: $itemid) {
    ok
    error
    entity {
      id
    }
  }
}
"""

UPDATE_RESOURCE_ROUTING_MODE = """
mutation updateResourceRoutingMode($itemid: ID!, $routingMode: RoutingMode!) {
  resourceUpdate(id: $itemid, routingMode: $routingMode) {
    ok
    error
    entity {
      id
      name
      routingMode
    }
  }
}
"""

DISABLE_RESOURCE = """
mutation disableResource($itemid: ID!) {
  resourceUpdate(id: $itemid, isActive: false) {
    ok
    error
    entity {
      id
      name
      isActive
    }
  }
}
"""

ENABLE_RESOURCE = """
mutation enableResource($itemid: ID!) {
  resourceUpdate(id: $itemid, isActive: true) {
    ok
    error
    entity {
      id
      name
      isActive
    }
  }
}
"""

RENAME_RESOURCE = """
mutation renameResource($itemid: ID!, $name: String!) {
  resourceUpdate(id: $itemid, name: $name) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

UPDATE_RESOURCE_PROTOCOLS = """
mutation updateResourceProtocols($itemid: ID!, $protocols: ProtocolsInput!) {
  resourceUpdate(id: $itemid, protocols: $protocols) {
    ok
    error
    entity {
      id
      name
      protocols {
        allowIcmp
        tcp {
          policy
          ports { start end }
        }
        udp {
          policy
          ports { start end }
        }
      }
    }
  }
}
"""

UPDATE_RESOURCE_BROWSER_SHORTCUT = """
mutation updateResourceBrowserShortcut($itemid: ID!, $isBrowserShortcutEnabled: Boolean!) {
  resourceUpdate(id: $itemid, isBrowserShortcutEnabled: $isBrowserShortcutEnabled) {
    ok
    error
    entity {
      id
      name
      isBrowserShortcutEnabled
    }
  }
}
"""

CREATE_SSH_RESOURCE = """
mutation createSshResource(
  $name: String!
  $address: String!
  $remoteNetworkId: ID!
  $gatewayId: ID!
  $securityPolicyId: ID!
  $groupIds: [ID!]
  $isVisible: Boolean!
  $upstreamPort: Int
  $downstreamPort: Int
) {
  sshResourceCreate(
    name: $name
    address: $address
    remoteNetworkId: $remoteNetworkId
    gatewayId: $gatewayId
    securityPolicyId: $securityPolicyId
    groupIds: $groupIds
    isVisible: $isVisible
    upstreamPort: $upstreamPort
    downstreamPort: $downstreamPort
  ) {
    ok
    error
    entity {
      id
      name
      address { type value }
      remoteNetwork { id name }
    }
  }
}
"""

UPDATE_SSH_RESOURCE = """
mutation updateSshResource(
  $id: ID!
  $name: String
  $address: String
  $gatewayId: ID
  $upstreamPort: Int
  $downstreamPort: Int
) {
  sshResourceUpdate(
    id: $id
    name: $name
    address: $address
    gatewayId: $gatewayId
    upstreamPort: $upstreamPort
    downstreamPort: $downstreamPort
  ) {
    ok
    error
    entity {
      id
      name
      address { type value }
    }
  }
}
"""

CREATE_KUBERNETES_RESOURCE = """
mutation createKubernetesResource(
  $name: String!
  $address: String!
  $remoteNetworkId: ID!
  $gatewayId: ID!
  $securityPolicyId: ID!
  $groupIds: [ID!]
  $isVisible: Boolean!
  $upstreamPort: Int
  $downstreamPort: Int
) {
  kubernetesResourceCreate(
    name: $name
    address: $address
    remoteNetworkId: $remoteNetworkId
    gatewayId: $gatewayId
    securityPolicyId: $securityPolicyId
    groupIds: $groupIds
    isVisible: $isVisible
    upstreamPort: $upstreamPort
    downstreamPort: $downstreamPort
  ) {
    ok
    error
    entity {
      id
      name
      address { type value }
      remoteNetwork { id name }
    }
  }
}
"""

UPDATE_KUBERNETES_RESOURCE = """
mutation updateKubernetesResource(
  $id: ID!
  $name: String
  $address: String
  $gatewayId: ID
  $upstreamPort: Int
  $downstreamPort: Int
) {
  kubernetesResourceUpdate(
    id: $id
    name: $name
    address: $address
    gatewayId: $gatewayId
    upstreamPort: $upstreamPort
    downstreamPort: $downstreamPort
  ) {
    ok
    error
    entity {
      id
      name
      address { type value }
    }
  }
}
"""

CREATE_WEBAPP_RESOURCE = """
mutation createWebAppResource(
  $name: String!
  $address: String!
  $remoteNetworkId: ID!
  $gatewayId: ID!
  $securityPolicyId: ID!
  $groupIds: [ID!]
  $isVisible: Boolean!
  $upstreamPort: Int
  $downstreamPort: Int
) {
  webAppResourceCreate(
    name: $name
    address: $address
    remoteNetworkId: $remoteNetworkId
    gatewayId: $gatewayId
    securityPolicyId: $securityPolicyId
    groupIds: $groupIds
    isVisible: $isVisible
    upstreamPort: $upstreamPort
    downstreamPort: $downstreamPort
  ) {
    ok
    error
    entity {
      id
      name
      address { type value }
      remoteNetwork { id name }
    }
  }
}
"""

UPDATE_WEBAPP_RESOURCE = """
mutation updateWebAppResource(
  $id: ID!
  $name: String
  $address: String
  $gatewayId: ID
  $upstreamPort: Int
  $downstreamPort: Int
) {
  webAppResourceUpdate(
    id: $id
    name: $name
    address: $address
    gatewayId: $gatewayId
    upstreamPort: $upstreamPort
    downstreamPort: $downstreamPort
  ) {
    ok
    error
    entity {
      id
      name
      address { type value }
    }
  }
}
"""

UPDATE_RESOURCE_TAGS = """
mutation updateResourceTags($itemid: ID!, $tags: [TagInput!]!) {
  resourceUpdate(id: $itemid, tags: $tags) {
    ok
    error
    entity {
      id
      name
      tags {
        key
        value
      }
    }
  }
}
"""

ADD_APPROVER_GROUPS = """
mutation addApproverGroups($itemid: ID!, $addedApproverGroupIds: [ID!]!) {
  resourceUpdate(id: $itemid, addedApproverGroupIds: $addedApproverGroupIds) {
    ok
    error
    entity {
      id
      name
      approverGroups {
        edges {
          node {
            id
            name
          }
        }
      }
    }
  }
}
"""

REMOVE_APPROVER_GROUPS = """
mutation removeApproverGroups($itemid: ID!, $removedApproverGroupIds: [ID!]!) {
  resourceUpdate(id: $itemid, removedApproverGroupIds: $removedApproverGroupIds) {
    ok
    error
    entity {
      id
      name
      approverGroups {
        edges {
          node {
            id
            name
          }
        }
      }
    }
  }
}
"""

SET_APPROVER_GROUPS = """
mutation setApproverGroups($itemid: ID!, $approverGroupIds: [ID!]!) {
  resourceUpdate(id: $itemid, approverGroupIds: $approverGroupIds) {
    ok
    error
    entity {
      id
      name
      approverGroups {
        edges {
          node {
            id
            name
          }
        }
      }
    }
  }
}
"""

# Aliases used by commands/resources.py
UPDATE_RESOURCE_VISIBILITY = TOGGLE_RESOURCE_VISIBILITY
UPDATE_RESOURCE_NETWORK = ASSIGN_NETWORK_TO_RESOURCE
