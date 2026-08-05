"""GraphQL queries and mutations for service account keys."""

from __future__ import annotations

SHOW_KEY = """
query getSAK($itemID: ID!) {
  serviceAccountKey(id: $itemID) {
    id
    name
    createdAt
    expiresAt
    revokedAt
    updatedAt
    status
    serviceAccount {
      id
      name
    }
  }
}
"""

CREATE_KEY = """
mutation createServiceAccountKey($name: String!, $serviceAccountId: ID!, $expirationTime: Int!) {
  serviceAccountKeyCreate(
    name: $name
    serviceAccountId: $serviceAccountId
    expirationTime: $expirationTime
  ) {
    ok
    error
    token
    entity {
      id
      name
      expiresAt
      createdAt
      status
    }
  }
}
"""

DELETE_KEY = """
mutation deleteServiceAccountKey($id: ID!) {
  serviceAccountKeyDelete(id: $id) {
    ok
    error
  }
}
"""

REVOKE_KEY = """
mutation revokeServiceAccountKey($id: ID!) {
  serviceAccountKeyRevoke(id: $id) {
    ok
    error
  }
}
"""

RENAME_KEY = """
mutation renameServiceAccountKey($id: ID!, $name: String!) {
  serviceAccountKeyUpdate(id: $id, name: $name) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

LIST_KEYS = """
query ListKeys($cursor: String) {
  serviceAccounts(first: 100, after: $cursor) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        keys {
          edges {
            node {
              id
              name
              status
              createdAt
              expiresAt
              revokedAt
            }
          }
        }
      }
    }
  }
}
"""
