"""GraphQL queries for security policies."""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

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

# The API returns at most 50 items per page, so `policy show` follows each nested list to its end.
_NESTED = {"groups": "node { id name }"}

SHOW_POLICY = f"""
query getObj($itemID: ID!) {{
  securityPolicy(id: $itemID) {{
    id
    name
    updatedAt
    createdAt
    policyType
    {connection("groups", _NESTED["groups"])}
  }}
}}
"""

POLICY_CONTINUATIONS = {field: continuation("securityPolicy", field, edge) for field, edge in _NESTED.items()}

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
