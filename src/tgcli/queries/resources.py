"""GraphQL queries and mutations for resources."""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

# Selections that only exist on some Resource implementations (Resource is a GraphQL interface).
_TYPE_SPECIFIC_TEMPLATE = """
    ... on NetworkResource {
      routingMode
      accessPolicy {
        mode
        durationSeconds
      }
      approvalMode
      @@APPROVERS@@
    }
    ... on SSHResource {
      accessPolicy {
        mode
        durationSeconds
      }
      approvalMode
      @@APPROVERS@@
      gateway {
        id
        address
      }
      upstream {
        port
      }
      downstream {
        port
      }
    }
    ... on WebAppResource {
      accessPolicy {
        mode
        durationSeconds
      }
      approvalMode
      @@APPROVERS@@
      gateway {
        id
        address
      }
      upstream {
        port
        tlsMode
      }
      downstream {
        port
        tlsMode
      }
    }
    ... on KubernetesResource {
      accessPolicy {
        mode
        durationSeconds
      }
      approvalMode
      @@APPROVERS@@
      gateway {
        id
        address
      }
      clusterRef
      upstream {
        port
      }
      downstream {
        port
      }
    }
"""

# The API returns at most 50 items per page, so the resource commands follow each nested list to its end.
RESOURCE_TYPES = ("NetworkResource", "SSHResource", "WebAppResource", "KubernetesResource")
_APPROVER_EDGE = "node { id name }"
_ACCESS_EDGE = "node { ... on Group { id name } ... on ServiceAccount { id name } } securityPolicy { id name }"
_TYPE_SPECIFIC_FIELDS = _TYPE_SPECIFIC_TEMPLATE.replace("@@APPROVERS@@", connection("approverGroups", _APPROVER_EDGE))

_LIST_RESOURCES_TEMPLATE = """
query listGroup($cursor: String!) {
  resources(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        __typename
        id
        isActive
        name
        alias
        createdAt
        updatedAt
        isVisible
        isBrowserShortcutEnabled
@@TYPE_FIELDS@@        tags {
          key
          value
        }
        @@ACCESS@@
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

# Default listing: only what costs next to nothing. `resource list --detail` pays for the rest.
_LIST_TYPE_FIELDS = """    ... on NetworkResource {
      routingMode
    }
"""

LIST_RESOURCES = _LIST_RESOURCES_TEMPLATE.replace("@@TYPE_FIELDS@@", _LIST_TYPE_FIELDS).replace(
    "@@ACCESS@@", connection("access", _ACCESS_EDGE)
)
LIST_RESOURCES_DETAIL = _LIST_RESOURCES_TEMPLATE.replace("@@TYPE_FIELDS@@", _TYPE_SPECIFIC_FIELDS).replace(
    "@@ACCESS@@", connection("access", _ACCESS_EDGE)
)

_APPROVERS_CONTINUATION = continuation("resource", "approverGroups", _APPROVER_EDGE, on=RESOURCE_TYPES)
RESOURCE_LIST_CONTINUATIONS = {"access": continuation("resource", "access", _ACCESS_EDGE)}
RESOURCE_DETAIL_CONTINUATIONS = {**RESOURCE_LIST_CONTINUATIONS, "approverGroups": _APPROVERS_CONTINUATION}
RESOURCE_SHOW_CONTINUATIONS = {"approverGroups": _APPROVERS_CONTINUATION}

SHOW_RESOURCE = """
query getResource($itemID: ID!) {
  resource(id: $itemID) {
    __typename
    id
    name
    createdAt
    updatedAt
    isVisible
    isBrowserShortcutEnabled
    isActive
""" + _TYPE_SPECIFIC_FIELDS + """    remoteNetwork {
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
  $securityPolicyId: ID
  $isVisible: Boolean!
  $routingMode: RoutingMode
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
      securityPolicy {
        id
      }
    }
  }
}
"""

UPDATE_RESOURCE_AUTOLOCK = """
mutation ObjUpdate($itemid: ID!, $accessPolicy: AccessPolicyInput!, $autoapprovemode: AccessApprovalMode!) {
  resourceUpdate(id: $itemid, accessPolicy: $accessPolicy, approvalMode: $autoapprovemode) {
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

UPDATE_RESOURCE_AUTOAPPROVE = """
mutation ObjUpdate($itemid: ID!, $autoapprovemode: AccessApprovalMode!) {
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

UPDATE_RESOURCE_ROUTING_MODE = """
mutation ObjUpdate($itemid: ID!, $routingMode: RoutingMode!) {
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
mutation ObjUpdate($itemid: ID!) {
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
mutation ObjUpdate($itemid: ID!) {
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

# Aliases used by commands/resources.py
UPDATE_RESOURCE_VISIBILITY = TOGGLE_RESOURCE_VISIBILITY
UPDATE_RESOURCE_NETWORK = ASSIGN_NETWORK_TO_RESOURCE
