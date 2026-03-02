"""GraphQL queries and mutations for remote networks."""

from __future__ import annotations

LIST_NETWORKS = """
query listGroup($cursor: String!) {
  remoteNetworks(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
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
  }
}
"""

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
