"""GraphQL queries and mutations for service accounts."""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

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

# The API returns at most 50 items per page, so `account show` and `account listKeys` follow each nested list to its end.
_SHOW_NESTED = {
    "resources": "node { id name }",
    "keys": "node { id name createdAt expiresAt revokedAt updatedAt status }",
}
_KEYS_NESTED = {"keys": "node { id name status createdAt expiresAt revokedAt }"}

SHOW_ACCOUNT = f"""
query getObj($itemID: ID!) {{
  serviceAccount(id: $itemID) {{
    id
    name
    createdAt
    updatedAt
    {connection("resources", _SHOW_NESTED["resources"])}
    {connection("keys", _SHOW_NESTED["keys"])}
  }}
}}
"""

ACCOUNT_SHOW_CONTINUATIONS = {field: continuation("serviceAccount", field, edge) for field, edge in _SHOW_NESTED.items()}
ACCOUNT_RESOURCES_CONTINUATIONS = {"resources": ACCOUNT_SHOW_CONTINUATIONS["resources"]}  # echo of add/removeResources
ACCOUNT_KEYS_CONTINUATIONS = {field: continuation("serviceAccount", field, edge) for field, edge in _KEYS_NESTED.items()}

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

ADD_RESOURCES_TO_ACCOUNT = f"""
mutation addResToSAccount($id: ID!, $resourceIDS: [ID!]) {{
  serviceAccountUpdate(id: $id, addedResourceIds: $resourceIDS) {{
    ok
    error
    entity {{
      id
      name
      createdAt
      updatedAt
      {connection("resources", _SHOW_NESTED["resources"])}
    }}
  }}
}}
"""

REMOVE_RESOURCES_FROM_ACCOUNT = f"""
mutation removeResToSAccount($id: ID!, $resourceIDS: [ID!]) {{
  serviceAccountUpdate(id: $id, removedResourceIds: $resourceIDS) {{
    ok
    error
    entity {{
      id
      name
      createdAt
      updatedAt
      {connection("resources", _SHOW_NESTED["resources"])}
    }}
  }}
}}
"""

RENAME_ACCOUNT = """
mutation ObjRename($id: ID!, $name: String!) {
  serviceAccountUpdate(id: $id, name: $name) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

LIST_ACCOUNT_KEYS = f"""
query getObj($itemID: ID!) {{
  serviceAccount(id: $itemID) {{
    id
    name
    {connection("keys", _KEYS_NESTED["keys"])}
  }}
}}
"""
