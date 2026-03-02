"""GraphQL queries and mutations for service accounts."""

from __future__ import annotations

LIST_ACCOUNTS = """
{
  serviceAccounts(after: null, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        createdAt
        updatedAt
        resources {
          edges {
            node {
              id
              name
            }
          }
        }
        keys {
          edges {
            node {
              id
              name
              createdAt
              expiresAt
              revokedAt
              updatedAt
              status
            }
          }
        }
      }
    }
  }
}
"""

SHOW_ACCOUNT = """
query getObj($itemID: ID!) {
  serviceAccount(id: $itemID) {
    id
    name
    createdAt
    updatedAt
    resources {
      edges {
        node {
          id
          name
        }
      }
    }
    keys {
      edges {
        node {
          id
          name
          createdAt
          expiresAt
          revokedAt
          updatedAt
          status
        }
      }
    }
  }
}
"""

CREATE_ACCOUNT = """
mutation ObjCreate($name: String!, $resourceIds: [ID!]) {
  serviceAccountCreate(name: $name, resourceIds: $resourceIds) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

DELETE_ACCOUNT = """
mutation ObjCreate($id: ID!) {
  serviceAccountDelete(id: $id) {
    ok
    error
  }
}
"""

ADD_RESOURCES_TO_ACCOUNT = """
mutation addResToSAccount($id: ID!, $resourceIDS: [ID!]) {
  serviceAccountUpdate(id: $id, addedResourceIds: $resourceIDS) {
    ok
    error
    entity {
      id
      name
      createdAt
      updatedAt
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

REMOVE_RESOURCES_FROM_ACCOUNT = """
mutation removeResToSAccount($id: ID!, $resourceIDS: [ID!]) {
  serviceAccountUpdate(id: $id, removedResourceIds: $resourceIDS) {
    ok
    error
    entity {
      id
      name
      createdAt
      updatedAt
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
