"""GraphQL queries for security policies."""

from __future__ import annotations

LIST_POLICIES = """
query listObj($cursor: String!) {
  securityPolicies(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        updatedAt
        createdAt
        policyType
      }
    }
  }
}
"""

SHOW_POLICY = """
query getObj($itemID: ID!) {
  securityPolicy(id: $itemID) {
    id
    name
    updatedAt
    createdAt
    policyType
    groups {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
"""

UPDATE_POLICY_GROUPS = """
mutation updatePolicyGroups($id: ID!, $groupIds: [ID], $addedGroupIds: [ID], $removedGroupIds: [ID]) {
  securityPolicyUpdate(id: $id, groupIds: $groupIds, addedGroupIds: $addedGroupIds, removedGroupIds: $removedGroupIds) {
    ok
    error
    entity {
      id
      name
      policyType
      groups {
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
