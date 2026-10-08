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
