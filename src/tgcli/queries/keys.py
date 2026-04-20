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
mutation ObjCreate($name: String!, $serviceAccountId: ID!, $expirationTime: Int!) {
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
mutation ObjCreate($id: ID!) {
  serviceAccountKeyDelete(id: $id) {
    ok
    error
  }
}
"""

REVOKE_KEY = """
mutation ObjCreate($id: ID!) {
  serviceAccountKeyRevoke(id: $id) {
    ok
    error
  }
}
"""

RENAME_KEY = """
mutation ObjRename($id: ID!, $name: String!) {
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
