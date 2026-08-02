"""GraphQL queries and mutations for gateways."""

from __future__ import annotations

LIST_GATEWAYS = """
query listGateways($cursor: String!) {
  gateways(after: $cursor, first: null) {
    totalCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        address
        createdAt
        updatedAt
        remoteNetwork {
          id
          name
        }
      }
    }
  }
}
"""

SHOW_GATEWAY = """
query getGateway($itemID: ID!) {
  gateway(id: $itemID) {
    id
    name
    address
    createdAt
    updatedAt
    remoteNetwork {
      id
      name
    }
  }
}
"""

CREATE_GATEWAY = """
mutation createGateway($address: String!, $remoteNetworkId: ID!, $sshCAId: ID, $x509CAId: ID) {
  gatewayCreate(address: $address, remoteNetworkId: $remoteNetworkId, sshCAId: $sshCAId, x509CAId: $x509CAId) {
    ok
    error
    entity {
      id
      name
      address
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

DELETE_GATEWAY = """
mutation deleteGateway($id: ID!) {
  gatewayDelete(id: $id) {
    ok
    error
  }
}
"""

UPDATE_GATEWAY = """
mutation updateGateway($id: ID!, $address: String, $remoteNetworkId: ID, $sshCAId: ID, $x509CAId: ID) {
  gatewayUpdate(id: $id, address: $address, remoteNetworkId: $remoteNetworkId, sshCAId: $sshCAId, x509CAId: $x509CAId) {
    ok
    error
    entity {
      id
      name
      address
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""
