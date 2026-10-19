"""GraphQL queries and mutations for users."""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

# The API returns at most 50 items per page, so `user list` and `user show` follow each nested list to its end.
_LIST_NESTED = {"groups": "node { id }"}
_SHOW_NESTED = {"groups": "node { id name }"}

LIST_USERS = f"""
query listGroup($cursor: String!) {{
  users(after: $cursor, first: null) {{
    pageInfo {{
      endCursor
      hasNextPage
    }}
    edges {{
      node {{
        id
        state
        email
        role
        lastName
        firstName
        createdAt
        updatedAt
        {connection("groups", _LIST_NESTED["groups"])}
      }}
    }}
  }}
}}
"""

USER_LIST_CONTINUATIONS = {field: continuation("user", field, edge) for field, edge in _LIST_NESTED.items()}
USER_SHOW_CONTINUATIONS = {field: continuation("user", field, edge) for field, edge in _SHOW_NESTED.items()}

SHOW_USER = f"""
query getObj($itemID: ID!) {{
  user(id: $itemID) {{
    id
    state
    email
    role
    lastName
    firstName
    createdAt
    updatedAt
    {connection("groups", _SHOW_NESTED["groups"])}
  }}
}}
"""

CREATE_USER = """
mutation UserCreate(
  $email: String!
  $firstname: String!
  $lastname: String!
  $userRole: UserRole!
  $shouldsendinvite: Boolean!
) {
  userCreate(
    email: $email
    firstName: $firstname
    lastName: $lastname
    role: $userRole
    shouldSendInvite: $shouldsendinvite
  ) {
    ok
    error
    entity {
      id
      state
      email
      role
      lastName
      firstName
      createdAt
      updatedAt
    }
  }
}
"""

DELETE_USER = """
mutation userDelete($itemid: ID!) {
  userDelete(id: $itemid) {
    ok
    error
  }
}
"""

UPDATE_USER_ROLE = """
mutation updateUserRole($itemid: ID!, $userRole: UserRole!) {
  userRoleUpdate(id: $itemid, role: $userRole) {
    ok
    error
    entity {
      id
      state
      email
      role
      lastName
      firstName
      createdAt
      updatedAt
      groups {
        edges {
          node {
            id
          }
        }
      }
    }
  }
}
"""

UPDATE_USER_STATE = """
mutation userDetailsUpdate($userID: ID!, $state: UserStateUpdateInput!) {
  userDetailsUpdate(id: $userID, state: $state) {
    ok
    error
    entity {
      id
      state
      email
      role
      lastName
      firstName
      createdAt
      updatedAt
    }
  }
}
"""

RESET_USER_MFA = """
mutation userResetMfa($itemid: ID!) {
  userResetMfa(id: $itemid) {
    ok
    error
  }
}
"""
