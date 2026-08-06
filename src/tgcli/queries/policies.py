"""GraphQL queries for security policies."""

from __future__ import annotations

LIST_POLICIES = """
query listPolicies($cursor: String!, $filter: SecurityPolicyFilterField) {
  securityPolicies(after: $cursor, first: null, filter: $filter) {
    totalCount
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

SHOW_POLICY_BY_NAME = """
query getPolicyByName($name: String!) {
  securityPolicy(name: $name) {
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

UPDATE_POLICY_ADD_GROUPS = """
mutation addGroupsToPolicy($id: ID!, $addedGroupIds: [ID!]!) {
  securityPolicyUpdate(id: $id, addedGroupIds: $addedGroupIds) {
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

UPDATE_POLICY_REMOVE_GROUPS = """
mutation removeGroupsFromPolicy($id: ID!, $removedGroupIds: [ID!]!) {
  securityPolicyUpdate(id: $id, removedGroupIds: $removedGroupIds) {
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

HEALTH_POLICIES = """
{ securityPolicies(first: null, after: "0") { totalCount } }
"""
