"""GraphQL queries and mutations for resources."""

from __future__ import annotations

LIST_RESOURCES = """
query listGroup($cursor: String!) {
  resources(after: $cursor, first: null) {
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
        usageBasedAutolockDurationDays
        tags {
          key
          value
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
    usageBasedAutolockDurationDays
    isActive
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
"""

CREATE_RESOURCE = """
mutation ObjCreate(
  $address: String!
  $alias: String
  $name: String!
  $remoteNetworkId: ID!
  $groupIds: [ID!]
  $protocols: ProtocolsInput!
  $securityPolicyId: ID!
  $isVisible: Boolean!
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
  ) {
    ok
    error
    entity {
      id
      name
      isVisible
      securityPolicy {
        id
      }
    }
  }
}
"""

DELETE_RESOURCE = """
mutation ObjDelete($id: ID!) {
  resourceDelete(id: $id) {
    ok
    error
  }
}
"""

ASSIGN_NETWORK_TO_RESOURCE = """
mutation ObjUpdate($itemid: ID!, $networkid: ID!) {
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
mutation ObjUpdate($itemid: ID!, $visibility: Boolean!) {
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
mutation ObjUpdate($itemid: ID!, $address: String!) {
  resourceUpdate(id: $itemid, address: $address) {
    ok
    error
    entity {
      id
      name
      alias
      usageBasedAutolockDurationDays
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
mutation ObjUpdate($itemid: ID!, $alias: String!) {
  resourceUpdate(id: $itemid, alias: $alias) {
    ok
    error
    entity {
      id
      name
      alias
      usageBasedAutolockDurationDays
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
mutation ObjUpdate($itemid: ID!, $securityPolicyId: ID!) {
  resourceUpdate(id: $itemid, securityPolicyId: $securityPolicyId) {
    ok
    error
    entity {
      id
      name
      alias
      usageBasedAutolockDurationDays
      securityPolicy {
        id
      }
    }
  }
}
"""

UPDATE_RESOURCE_AUTOLOCK = """
mutation ObjUpdate($itemid: ID!, $autolock: Int, $autoapprovemode: AccessApprovalMode!) {
  resourceUpdate(id: $itemid, usageBasedAutolockDurationDays: $autolock, approvalMode: $autoapprovemode) {
    ok
    error
    entity {
      id
      name
      alias
      usageBasedAutolockDurationDays
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
mutation ObjUpdate($itemid: ID!, $autoapprovemode: AccessApprovalMode!) {
  resourceUpdate(id: $itemid, approvalMode: $autoapprovemode) {
    ok
    error
    entity {
      id
      name
      alias
      usageBasedAutolockDurationDays
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
mutation ObjUpdate($accessids: [AccessInput!]!, $itemid: ID!) {
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
mutation ObjUpdate($accessids: [AccessInput!]!, $itemid: ID!) {
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
mutation ObjUpdate($itemid: ID!, $groupid: [ID!]!) {
  resourceAccessRemove(principalIds: $groupid, resourceId: $itemid) {
    ok
    error
    entity {
      id
    }
  }
}
"""

# Aliases used by commands/resources.py
UPDATE_RESOURCE_VISIBILITY = TOGGLE_RESOURCE_VISIBILITY
UPDATE_RESOURCE_NETWORK = ASSIGN_NETWORK_TO_RESOURCE
