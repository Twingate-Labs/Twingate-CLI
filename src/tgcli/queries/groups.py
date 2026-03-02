"""GraphQL queries and mutations for groups."""

from __future__ import annotations

LIST_GROUPS = """
query listGroup($cursor: String!) {
  groups(after: $cursor, first: null) {
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
