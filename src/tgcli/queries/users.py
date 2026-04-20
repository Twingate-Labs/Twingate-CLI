"""GraphQL queries and mutations for users."""

from __future__ import annotations

LIST_USERS = """
query listGroup($cursor: String!) {
  users(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
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
}
"""

SHOW_USER = """
query getObj($itemID: ID!) {
  user(id: $itemID) {
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
          name
        }
      }
    }
  }
}
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
