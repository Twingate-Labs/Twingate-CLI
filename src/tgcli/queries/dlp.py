"""GraphQL queries for data loss prevention policies."""

from __future__ import annotations

LIST_DLP_POLICIES = """
query listDlpPolicies($cursor: String!) {
  dlpPolicies(after: $cursor, first: null) {
    totalCount
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
      }
    }
  }
}
"""

SHOW_DLP_POLICY = """
query getDlpPolicy($itemID: ID!) {
  dlpPolicy(id: $itemID) {
    id
    name
    createdAt
    updatedAt
  }
}
"""
