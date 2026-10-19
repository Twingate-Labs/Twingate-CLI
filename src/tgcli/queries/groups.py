"""GraphQL queries and mutations for groups."""

from __future__ import annotations

def _nested(field: str, edge: str) -> str:
    """A nested list as the first page sees it: with the count and cursor needed to spot and finish truncation."""
    return f"{field} {{ totalCount pageInfo {{ hasNextPage endCursor }} edges {{ {edge} }} }}"


def _continuation(parent: str, field: str, edge: str) -> str:
    """The same nested list, fetched on its own so the pages after the first can be read."""
    return (
        f"query($id: ID!, $cursor: String) {{ {parent}(id: $id) {{ {field}(after: $cursor) {{ "
        f"pageInfo {{ hasNextPage endCursor }} edges {{ {edge} }} }} }} }}"
    )


# The API returns at most 50 items per page, so `group list` follows each nested list to its end.
_LIST_NESTED = {
    "users": "node { id email firstName lastName }",
    "resources": "node { id name address { type value } isActive }",
}

LIST_GROUPS = f"""
query listGroup($cursor: String!) {{
  groups(after: $cursor, first: null) {{
    pageInfo {{
      endCursor
      hasNextPage
    }}
    edges {{
      node {{
        id
        name
        createdAt
        updatedAt
        isActive
        type
        {_nested("users", _LIST_NESTED["users"])}
        {_nested("resources", _LIST_NESTED["resources"])}
      }}
    }}
  }}
}}
"""

LIST_GROUPS_CONTINUATIONS = {field: _continuation("group", field, edge) for field, edge in _LIST_NESTED.items()}

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
