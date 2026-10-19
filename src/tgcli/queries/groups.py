"""GraphQL queries and mutations for groups."""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

# The API returns at most 50 items per page, so `group list` and `group show` follow each nested list to its end.
_NESTED = {
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
        {connection("users", _NESTED["users"])}
        {connection("resources", _NESTED["resources"])}
      }}
    }}
  }}
}}
"""

GROUP_CONTINUATIONS = {field: continuation("group", field, edge) for field, edge in _NESTED.items()}

# What a group write echoes back. add/removeResources echo a shorter resource than `group show` does.
_ECHO_RESOURCE_EDGE = "node { id name }"
GROUP_USERS_CONTINUATIONS = {"users": GROUP_CONTINUATIONS["users"]}
GROUP_RESOURCES_ECHO_CONTINUATIONS = {"resources": continuation("group", "resources", _ECHO_RESOURCE_EDGE)}

SHOW_GROUP = f"""
query getObj($itemID: ID!) {{
  group(id: $itemID) {{
    id
    name
    createdAt
    updatedAt
    isActive
    type
    {connection("users", _NESTED["users"])}
    {connection("resources", _NESTED["resources"])}
  }}
}}
"""

CREATE_GROUP = f"""
mutation createGroup(
  $groupName: String!
  $userIDS: [ID!]
  $resourceIDS: [ID!]
  $securityPolicyId: ID
) {{
  groupCreate(
    name: $groupName
    resourceIds: $resourceIDS
    userIds: $userIDS
    securityPolicyId: $securityPolicyId
  ) {{
    ok
    error
    entity {{
      id
      name
      isActive
      type
      createdAt
      updatedAt
      {connection("users", _NESTED["users"])}
      {connection("resources", _NESTED["resources"])}
    }}
  }}
}}
"""

DELETE_GROUP = """
mutation deleteGroup($groupId: ID!) {
  groupDelete(id: $groupId) {
    ok
    error
  }
}
"""

ADD_USERS_TO_GROUP = f"""
mutation addUsersToGroup($groupID: ID!, $userIDS: [ID!]) {{
  groupUpdate(id: $groupID, addedUserIds: $userIDS) {{
    ok
    error
    entity {{
      id
      name
      isActive
      createdAt
      updatedAt
      type
      {connection("users", _NESTED["users"])}
    }}
  }}
}}
"""

REMOVE_USERS_FROM_GROUP = f"""
mutation removeUsersFromGroup($groupID: ID!, $userIDS: [ID!]) {{
  groupUpdate(id: $groupID, removedUserIds: $userIDS) {{
    ok
    error
    entity {{
      id
      name
      isActive
      createdAt
      updatedAt
      type
      {connection("users", _NESTED["users"])}
    }}
  }}
}}
"""

ADD_RESOURCES_TO_GROUP = f"""
mutation addResToGroup($groupID: ID!, $resourceIDS: [ID!]) {{
  groupUpdate(id: $groupID, addedResourceIds: $resourceIDS) {{
    ok
    error
    entity {{
      id
      name
      isActive
      createdAt
      updatedAt
      type
      {connection("resources", _ECHO_RESOURCE_EDGE)}
    }}
  }}
}}
"""

REMOVE_RESOURCES_FROM_GROUP = f"""
mutation removeResToGroup($groupID: ID!, $resourceIDS: [ID!]) {{
  groupUpdate(id: $groupID, removedResourceIds: $resourceIDS) {{
    ok
    error
    entity {{
      id
      name
      isActive
      createdAt
      updatedAt
      type
      {connection("resources", _ECHO_RESOURCE_EDGE)}
    }}
  }}
}}
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

# `group migrate` reads each group's users and resources itself (LIST_GROUP_USERS / LIST_GROUP_RESOURCES), so
# this selects only the group, plus the security policy that migrate copies to the new group.
LIST_GROUPS_FOR_MIGRATE = """
query listGroupsForMigrate($cursor: String!) {
  groups(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        isActive
        type
        securityPolicy {
          id
          name
        }
      }
    }
  }
}
"""

ASSIGN_POLICY_TO_GROUP = f"""
mutation assignPolicyToGrp($groupID: ID!, $policyID: ID!) {{
  groupUpdate(id: $groupID, securityPolicyId: $policyID) {{
    ok
    error
    entity {{
      id
      name
      isActive
      securityPolicy {{ id name policyType }}
      type
      {connection("users", _NESTED["users"])}
    }}
  }}
}}
"""
