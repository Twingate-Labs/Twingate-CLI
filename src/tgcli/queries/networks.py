"""GraphQL queries and mutations for remote networks."""

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


# The API returns at most 50 items per page, so `network list` follows each nested list to its end.
_LIST_NESTED = {
    "connectors": "node { id name }",
    "resources": "node { id name }",
}

LIST_NETWORKS = f"""
query listGroup($cursor: String!) {{
  remoteNetworks(after: $cursor, first: null) {{
    pageInfo {{
      endCursor
      hasNextPage
    }}
    edges {{
      node {{
        id
        name
        updatedAt
        createdAt
        isActive
        {_nested("connectors", _LIST_NESTED["connectors"])}
        {_nested("resources", _LIST_NESTED["resources"])}
      }}
    }}
  }}
}}
"""

LIST_NETWORKS_CONTINUATIONS = {field: _continuation("remoteNetwork", field, edge) for field, edge in _LIST_NESTED.items()}

SHOW_NETWORK = """
query getObj($itemID: ID!) {
  remoteNetwork(id: $itemID) {
    id
    name
    updatedAt
    createdAt
    isActive
    connectors {
      edges {
        node {
          id
          name
        }
      }
    }
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
"""

CREATE_NETWORK = """
mutation ObjCreate($name: String!, $location: RemoteNetworkLocation!, $isactive: Boolean!) {
  remoteNetworkCreate(name: $name, location: $location, isActive: $isactive) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

DELETE_NETWORK = """
mutation ObjDelete($id: ID!) {
  remoteNetworkDelete(id: $id) {
    ok
    error
  }
}
"""

UPDATE_NETWORK_STATE = """
mutation PM_UpdateRemoteNetwork($rnID: ID!, $state: Boolean!) {
  remoteNetworkUpdate(id: $rnID, isActive: $state) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

UPDATE_NETWORK_NAME = """
mutation PM_UpdateRemoteNetwork($rnID: ID!, $name: String!) {
  remoteNetworkUpdate(id: $rnID, name: $name) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

UPDATE_NETWORK_LOCATION = """
mutation PM_UpdateRemoteNetwork($rnID: ID!, $location: RemoteNetworkLocation!) {
  remoteNetworkUpdate(id: $rnID, location: $location) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""
