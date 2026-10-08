"""GraphQL queries for gateways."""

from __future__ import annotations

LIST_GATEWAYS = """
query listGateways($cursor: String!) {
  gateways(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        address
        remoteNetwork {
          id
          name
        }
        x509CA {
          id
          name
          fingerprint
        }
        sshCA {
          id
          name
          fingerprint
        }
      }
    }
  }
}
"""

_GATEWAY_FIELDS = """
      id
      address
      remoteNetwork {
        id
        name
      }
      x509CA {
        id
        name
        fingerprint
      }
      sshCA {
        id
        name
        fingerprint
      }
"""

SHOW_GATEWAY = """
query getGateway($itemID: ID!) {
  gateway(id: $itemID) {""" + _GATEWAY_FIELDS + """  }
}
"""

CREATE_GATEWAY = """
mutation createGateway($address: String!, $remoteNetworkId: ID!, $x509CAId: ID!, $sshCAId: ID) {
  gatewayCreate(address: $address, remoteNetworkId: $remoteNetworkId, x509CAId: $x509CAId, sshCAId: $sshCAId) {
    ok
    error
    entity {""" + _GATEWAY_FIELDS + """    }
  }
}
"""

UPDATE_GATEWAY = """
mutation updateGateway($id: ID!, $address: String, $remoteNetworkId: ID, $x509CAId: ID, $sshCAId: ID) {
  gatewayUpdate(id: $id, address: $address, remoteNetworkId: $remoteNetworkId, x509CAId: $x509CAId, sshCAId: $sshCAId) {
    ok
    error
    entity {""" + _GATEWAY_FIELDS + """    }
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
