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

# Just the IDs of every group in a policy, one page at a time (see `policy update --clear-groups`).
POLICY_GROUP_IDS = """
query policyGroupIds($id: ID!, $cursor: String) {
  securityPolicy(id: $id) {
    groups(after: $cursor) {
      pageInfo { hasNextPage endCursor }
      edges { node { id } }
    }
  }
}
"""

UPDATE_POLICY_GROUPS = f"""
mutation updatePolicyGroups($id: ID!, $groupIds: [ID], $addedGroupIds: [ID], $removedGroupIds: [ID]) {{
  securityPolicyUpdate(id: $id, groupIds: $groupIds, addedGroupIds: $addedGroupIds, removedGroupIds: $removedGroupIds) {{
    ok
    error
    entity {{
      id
      name
      policyType
      {connection("groups", _NESTED["groups"])}
    }}
  }}
}}
"""
