"""GraphQL queries and mutations for groups."""

from __future__ import annotations

LIST_GROUPS = """
query listGroups($cursor: String!) {
  groups(after: $cursor, first: null) {
    totalCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        createdAt
        updatedAt
        isActive
        type
        originId
        securityPolicy {
          id
          name
          policyType
        }
        users {
          edges {
            node {
              id
              email
              firstName
              lastName
            }
          }
        }
        resources {
          edges {
            node {
              id
              name
              address {
                type
                value
              }
              isActive
            }
          }
        }
      }
    }
  }
}
"""

SHOW_GROUP = """
query getObj($itemID: ID!) {
  group(id: $itemID) {
    id
    name
    createdAt
    updatedAt
    isActive
    type
    originId
    securityPolicy {
      id
      name
      policyType
    }
    users {
      edges {
        node {
          id
          email
          firstName
          lastName
        }
      }
    }
    resources {
      edges {
        node {
          id
          name
          address {
            type
            value
          }
          isActive
        }
      }
    }
  }
}
"""

CREATE_GROUP = """
mutation createGroup(
  $groupName: String!
  $userIDS: [ID!]
  $resourceIDS: [ID!]
  $securityPolicyId: ID
) {
  groupCreate(
    name: $groupName
    resourceIds: $resourceIDS
    userIds: $userIDS
    securityPolicyId: $securityPolicyId
  ) {
    ok
    error
    entity {
      id
      name
      isActive
      type
      createdAt
      updatedAt
      users {
        edges {
          node {
            id
            email
            firstName
            lastName
          }
        }
      }
      resources {
        edges {
          node {
            id
            name
            address {
              type
              value
            }
            isActive
          }
        }
      }
    }
  }
}
"""

DELETE_GROUP = """
mutation deleteGroup($groupId: ID!) {
  groupDelete(id: $groupId) {
    ok
    error
  }
}
"""

ADD_USERS_TO_GROUP = """
mutation addUsersToGroup($groupID: ID!, $userIDS: [ID!]) {
  groupUpdate(id: $groupID, addedUserIds: $userIDS) {
    ok
    error
    entity {
      id
      name
      isActive
      createdAt
      updatedAt
      type
      users {
        edges {
          node {
            id
            email
            firstName
            lastName
          }
        }
      }
    }
  }
}
"""

REMOVE_USERS_FROM_GROUP = """
mutation removeUsersFromGroup($groupID: ID!, $userIDS: [ID!]) {
  groupUpdate(id: $groupID, removedUserIds: $userIDS) {
    ok
    error
    entity {
      id
      name
      isActive
      createdAt
      updatedAt
      type
      users {
        edges {
          node {
            id
            email
            firstName
            lastName
          }
        }
      }
    }
  }
}
"""

ADD_RESOURCES_TO_GROUP = """
mutation addResToGroup($groupID: ID!, $resourceIDS: [ID!]) {
  groupUpdate(id: $groupID, addedResourceIds: $resourceIDS) {
    ok
    error
    entity {
      id
      name
      isActive
      createdAt
      updatedAt
      type
      resources {
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

REMOVE_RESOURCES_FROM_GROUP = """
mutation removeResToGroup($groupID: ID!, $resourceIDS: [ID!]) {
  groupUpdate(id: $groupID, removedResourceIds: $resourceIDS) {
    ok
    error
    entity {
      id
      name
      isActive
      createdAt
      updatedAt
      type
      resources {
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

LIST_GROUP_USERS = """
query groupUsers($id: ID!, $after: String) {
  group(id: $id) {
    users(first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges { node { id email } }
    }
  }
}
"""

LIST_GROUP_RESOURCES = """
query groupResources($id: ID!, $after: String) {
  group(id: $id) {
    resources(first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges { node { id name } }
    }
  }
}
"""

ASSIGN_POLICY_TO_GROUP = """
mutation assignPolicyToGrp($groupID: ID!, $policyID: ID!) {
  groupUpdate(id: $groupID, securityPolicyId: $policyID) {
    ok
    error
    entity {
      id
      name
      isActive
      securityPolicy {
        id
        name
        policyType
      }
      type
      users {
        edges {
          node {
            id
            email
            firstName
            lastName
          }
        }
      }
    }
  }
}
"""

RENAME_GROUP = """
mutation renameGroup($groupID: ID!, $name: String!) {
  groupUpdate(id: $groupID, name: $name) {
    ok
    error
    entity {
      id
      name
      isActive
      type
    }
  }
}
"""

UPDATE_GROUP_STATE = """
mutation updateGroupState($groupID: ID!, $isActive: Boolean!) {
  groupUpdate(id: $groupID, isActive: $isActive) {
    ok
    error
    entity {
      id
      name
      isActive
      type
    }
  }
}
"""

SET_GROUP_USERS = """
mutation setGroupUsers($groupID: ID!, $userIDS: [ID!]!) {
  groupUpdate(id: $groupID, userIds: $userIDS) {
    ok
    error
    entity {
      id
      name
      users {
        edges {
          node {
            id
            email
          }
        }
      }
    }
  }
}
"""

SET_GROUP_RESOURCES = """
mutation setGroupResources($groupID: ID!, $resourceIDS: [ID!]!) {
  groupUpdate(id: $groupID, resourceIds: $resourceIDS) {
    ok
    error
    entity {
      id
      name
      resources {
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

UPDATE_GROUP = """
mutation updateGroup($groupID: ID!, $name: String, $isActive: Boolean, $securityPolicyId: ID) {
  groupUpdate(id: $groupID, name: $name, isActive: $isActive, securityPolicyId: $securityPolicyId) {
    ok
    error
    entity {
      id
      name
      isActive
      securityPolicy {
        id
        name
      }
    }
  }
}
"""

HEALTH_GROUPS = """
{ groups(first: null, after: "0") { totalCount edges { node { id type users { edges { node { id } } } } } } }
"""
