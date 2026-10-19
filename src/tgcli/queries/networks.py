"""GraphQL queries and mutations for remote networks."""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

# The API returns at most 50 items per page, so `network list` and `network show` follow each nested list to its end.
_NESTED = {
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
        {connection("connectors", _NESTED["connectors"])}
        {connection("resources", _NESTED["resources"])}
      }}
    }}
  }}
}}
"""

NETWORK_CONTINUATIONS = {field: continuation("remoteNetwork", field, edge) for field, edge in _NESTED.items()}

SHOW_NETWORK = f"""
query getObj($itemID: ID!) {{
  remoteNetwork(id: $itemID) {{
    id
    name
    updatedAt
    createdAt
    isActive
    {connection("connectors", _NESTED["connectors"])}
    {connection("resources", _NESTED["resources"])}
  }}
}}
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
